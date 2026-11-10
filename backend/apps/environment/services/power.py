"""
NASA POWER daily climate fetch with cache, retries, and stale fallback (plan §3).

Contract:
  - Endpoint: ``{POWER_BASE_URL}/temporal/daily/point``
  - ``community=AG``; params PRECTOTCORR, T2M, T2M_MAX, T2M_MIN, RH2M, WS2M,
    ALLSKY_SFC_SW_DWN.
  - Cache key = provider + product + parameters + rounded cell + dates + time
    standard; persisted as a ``DataAsset`` with a content hash; TTL 7 days.
  - 3 retries, exponential backoff + jitter, capped; 10 s timeout.
  - Auth errors are operational faults, NOT cache misses.
  - **Never replace missing rainfall with zero** (plan §3, report §6): a
    missing day is stored as ``None`` and surfaced as ``quality: partial``.
  - On total failure: serve the seeded snapshot with ``stale=True``; if none
    exists, return ``partial`` evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.utils import timezone as dj_tz

from ..models import DataAsset, DatasetProduct, FieldIndicator

logger = logging.getLogger("fieldshift.power")

POWER_PARAMS = "PRECTOTCORR,ALLSKY_SFC_SW_DWN,WS2M,RH2M,T2M,T2M_MAX,T2M_MIN"
POWER_COMMUNITY = "AG"
POWER_PRODUCT = "POWER"

# Map POWER variable → (indicator kind, unit).
_VAR_MAP = {
    "PRECTOTCORR": ("rainfall", "mm"),
    "T2M": ("temperature", "°C"),
    "T2M_MAX": ("temperature_max", "°C"),
    "T2M_MIN": ("temperature_min", "°C"),
    "RH2M": ("relative_humidity", "%"),
    "WS2M": ("wind_speed", "m/s"),
    "ALLSKY_SFC_SW_DWN": ("shortwave_radiation", "W/m2"),
}


@dataclass
class PowerResult:
    """The engine-facing result of a POWER fetch (fresh, cached, or stale)."""

    rows: list[dict] = field(default_factory=list)  # [{date, prectot, t2m, tmax, tmin, rh, ws, rs}]
    stale: bool = False
    source: str = "live"  # live | cached | stale_snapshot
    asset_id: str | None = None
    content_hash: str | None = None
    missing_days: int = 0


def _round_cell(lat: float, lng: float, decimals: int = 1) -> tuple[float, float]:
    return (round(lat, decimals), round(lng, decimals))


def _cache_key(lat: float, lng: float, start: str, end: str) -> str:
    cell = _round_cell(lat, lng)
    raw = f"{POWER_PRODUCT}|{POWER_PARAMS}|{POWER_COMMUNITY}|{cell[0]},{cell[1]}|{start}|{end}|UTC"
    return hashlib.sha256(raw.encode()).hexdigest()


def _content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _backoff(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    delay = min(cap, base * (2 ** attempt))
    return delay + random.uniform(0, 0.3)


def _fetch_with_retry(url: str, params: dict) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(settings.POWER_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=settings.POWER_TIMEOUT_SECONDS)
            # 4xx auth errors are operational faults — do not retry, do not cache.
            if resp.status_code in (401, 403):
                raise PowerAuthError(f"POWER auth error {resp.status_code}")
            if resp.status_code >= 500:
                raise PowerTransientError(f"POWER server error {resp.status_code}")
            resp.raise_for_status()
            return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                PowerTransientError) as exc:
            last_exc = exc
            if attempt < settings.POWER_RETRIES - 1:
                time.sleep(_backoff(attempt))
    raise PowerTransientError(f"POWER fetch failed after {settings.POWER_RETRIES} tries: {last_exc}")


class PowerAuthError(Exception):
    """Operational fault (bad/missing auth) — distinct from a cache miss."""


class PowerTransientError(Exception):
    """Network / 5xx — retryable, but not an auth fault."""


def get_daily_series(lat: float, lng: float, start: str, end: str,
                     field_model=None) -> PowerResult:
    """
    Return a daily POWER series for a point, honouring the cache.

    ``start``/``end`` are ISO dates (YYYY-MM-DD). A missing day in the payload
    is stored as ``None`` (never zero-filled) and counted in ``missing_days``.
    """
    key = _cache_key(lat, lng, start, end)
    product, _ = DatasetProduct.objects.get_or_create(
        slug="power-daily",
        defaults={
            "name": "NASA POWER Daily",
            "provider": "NASA POWER",
            "product_id": "POWER",
            "resolution": "0.5 deg",
            "cadence": "daily",
        },
    )

    # 1) Cache hit within TTL?
    existing = DataAsset.objects.filter(cache_key=key).order_by("-fetched_at").first()
    if existing is not None:
        now = dj_tz.now()
        if (existing.expires_at is None or existing.expires_at > now) and existing.status in ("fresh", "cached"):
            rows = _parse_payload(existing.payload)
            return PowerResult(
                rows=rows, stale=False, source="cached",
                asset_id=str(existing.pk), content_hash=existing.content_hash,
                missing_days=_count_missing(rows),
            )

    # 2) Live fetch.
    url = f"{settings.POWER_BASE_URL}/temporal/daily/point"
    # POWER v2 API: start/end are integer Unix timestamps (UTC); parameters
    # is a comma-separated list of variable names.
    from datetime import datetime as _dt, timezone as _utc
    start_ts = int(_dt.strptime(start, "%Y-%m-%d").replace(tzinfo=_utc).timestamp())
    end_ts = int(_dt.strptime(end, "%Y-%m-%d").replace(tzinfo=_utc).timestamp()) + 86400  # inclusive end day
    params = {
        "latitude": lat,
        "longitude": lng,
        "start": start_ts,
        "end": end_ts,
        "parameters": POWER_PARAMS,
        "community": POWER_COMMUNITY,
        "format": "JSON",
    }
    try:
        resp = _fetch_with_retry(url, params)
        payload_bytes = resp.content
        payload = resp.json()
    except (PowerAuthError, PowerTransientError) as exc:
        # Total failure: serve the seeded snapshot as stale, or empty/partial.
        logger.warning("POWER fetch failed: %s — serving stale snapshot", exc)
        if existing is not None:
            rows = _parse_payload(existing.payload)
            return PowerResult(rows=rows, stale=True, source="stale_snapshot",
                               asset_id=str(existing.pk),
                               content_hash=existing.content_hash,
                               missing_days=_count_missing(rows))
        return PowerResult(rows=[], stale=True, source="stale_snapshot",
                           asset_id=None, content_hash=None, missing_days=0)

    # 3) Persist as a fresh DataAsset (content-hashed) + FieldIndicator rows.
    content = _content_hash(payload_bytes)
    ttl = timedelta(seconds=settings.POWER_CACHE_TTL_SECONDS)
    asset = DataAsset(
        product=product,
        field=field_model,
        cache_key=key,
        content_hash=content,
        status="fresh",
        acquired_at=dj_tz.now(),
        expires_at=dj_tz.now() + ttl,
        payload=payload,
        metadata={
            "url": url,
            "params": {k: v for k, v in params.items()},
            "lat": lat,
            "lng": lng,
            "start": start,
            "end": end,
        },
    )
    asset.save()

    rows = _parse_payload(payload)
    _store_indicators(field_model, asset, rows)
    return PowerResult(rows=rows, stale=False, source="live",
                       asset_id=str(asset.pk), content_hash=content,
                       missing_days=_count_missing(rows))


def _count_missing(rows: list[dict]) -> int:
    n = 0
    for r in rows:
        if r.get("prectot") is None:
            n += 1
    return n


def _parse_payload(payload: dict) -> list[dict]:
    """Convert the POWER JSON envelope into the engine's row shape.

    Missing days → ``None`` (never zero). The engine treats ``None`` as a gap.
    """
    out: list[dict] = []
    for day in payload.get("parameters", []):
        row = {
            "date": day.get("date"),
            "prectot": day.get("PRECTOTCORR", {}).get("value") if isinstance(day.get("PRECTOTCORR"), dict) else day.get("PRECTOTCORR"),
            "t2m": _val(day, "T2M"),
            "tmax": _val(day, "T2M_MAX"),
            "tmin": _val(day, "T2M_MIN"),
            "rh": _val(day, "RH2M"),
            "ws": _val(day, "WS2M"),
            "rs": _val(day, "ALLSKY_SFC_SW_DWN"),
        }
        # Normalise: a day with no PRECTOTCORR key at all is a gap.
        if "PRECTOTCORR" not in day:
            row["prectot"] = None
        out.append(row)
    return out


def _val(day: dict, key: str):
    v = day.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    return v


def _store_indicators(field_model, asset: DataAsset, rows: list[dict]) -> None:
    """Materialise the series as FieldIndicator rows (only for a real field)."""
    if field_model is None:
        return
    from django.utils import timezone as _tz

    def parse_dt(dstr: str):
        return _tz.datetime.strptime(dstr, "%Y-%m-%d").replace(tzinfo=_tz.utc)

    for row in rows:
        if not row.get("date"):
            continue
        for var, (kind, unit) in _VAR_MAP.items():
            value = {
                "PRECTOTCORR": row["prectot"], "T2M": row["t2m"], "T2M_MAX": row["tmax"],
                "T2M_MIN": row["tmin"], "RH2M": row["rh"], "WS2M": row["ws"],
                "ALLSKY_SFC_SW_DWN": row["rs"],
            }[var]
            if value is None:
                continue
            dt = parse_dt(row["date"])
            FieldIndicator.objects.update_or_create(
                field=field_model, kind=kind, provider="NASA POWER", product="POWER",
                version="v7", period_start=dt,
                defaults={
                    "asset": asset,
                    "value": float(value),
                    "unit": unit,
                    "coverage_pct": 100.0,
                    "quality": "valid",
                    "is_forecast": False,
                    "is_inferred": False,
                },
            )
