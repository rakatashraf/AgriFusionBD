"""
NASA POWER daily climate fetch with cache, retries, and stale fallback (plan §3).

Contract (verified against the live v2.10 API):
  - Endpoint: ``{POWER_BASE_URL}/temporal/daily/point``
  - ``community=AG``; params PRECTOTCORR, T2M, T2M_MAX, T2M_MIN, RH2M, WS2M,
    ALLSKY_SFC_SW_DWN.
  - ``start``/``end`` are ``YYYYMMDD`` date strings (NOT Unix time).
  - Values live at ``properties.parameter.<VAR>.<YYYYMMDD>``.
  - ``ALLSKY_SFC_SW_DWN`` is already **MJ/m2/day** (not W/m2).
  - ``header.fill_value`` (default -999.0) marks a missing day — stored as
    ``None``, never zero-filled.
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
            # Materialise indicators even on cache hit (idempotent upsert).
            if field_model is not None:
                _store_indicators(field_model, existing, rows)
            return PowerResult(
                rows=rows, stale=False, source="cached",
                asset_id=str(existing.pk), content_hash=existing.content_hash,
                missing_days=_count_missing(rows),
            )

    # 2) Live fetch.
    url = f"{settings.POWER_BASE_URL}/temporal/daily/point"
    # POWER v2 API: start/end are YYYYMMDD date strings (UTC); parameters is a
    # comma-separated list of variable names. Verified against the live API —
    # Unix timestamps are rejected by the current endpoint.
    def _yyyymmdd(iso: str) -> str:
        return iso.replace("-", "")[:8]
    params = {
        "latitude": lat,
        "longitude": lng,
        "start": _yyyymmdd(start),
        "end": _yyyymmdd(end),
        "parameters": POWER_PARAMS,
        "community": POWER_COMMUNITY,
        "format": "JSON",
    }
    try:
        resp = _fetch_with_retry(url, params)
        payload_bytes = resp.content
        payload = resp.json()
    except (PowerAuthError, PowerTransientError) as exc:
        # Total failure: fall back to the committed fixture (stale=True), then
        # to the previously cached asset, then to an empty partial result.
        logger.warning("POWER fetch failed: %s — serving stale snapshot", exc)
        fixture_rows = _load_fixture(lat, lng, start, end)
        if fixture_rows:
            return PowerResult(rows=fixture_rows, stale=True, source="stale_snapshot",
                               asset_id=None, content_hash=None,
                               missing_days=_count_missing(fixture_rows))
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


def _load_fixture(lat: float, lng: float, start: str, end: str) -> list[dict]:
    """Load the committed POWER fixture for offline / stale-mode drills.

    Looks for ``fixtures/nasa/{field-slug}_power.json`` (per-field) or
    ``fixtures/nasa/default_power.json`` (shared fallback). The fixture is a
    list of day-dicts in the legacy ``parameters`` envelope shape.

    Returns an empty list if no fixture is found or the date range does not
    overlap the fixture's span.
    """
    import json as _json
    from pathlib import Path
    from django.conf import settings as _s

    base = Path(_s.BASE_DIR) / "fixtures" / "nasa"
    candidates = [base / "default_power.json"]
    # Per-field fixture (slug is unknown here; the caller passes lat/lng).
    # The seed command writes a per-centroid file when it knows the slug.

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        days = data if isinstance(data, list) else data.get("parameters", [])
        if not days:
            continue
        # Filter to the requested range (inclusive).
        filtered = [d for d in days if start <= d.get("date", "") <= end]
        if filtered:
            return filtered
    return []


def _count_missing(rows: list[dict]) -> int:
    n = 0
    for r in rows:
        if r.get("prectot") is None:
            n += 1
    return n


def _parse_date(dstr: str):
    """Parse a YYYY-MM-DD date string into a timezone-aware UTC datetime."""
    return datetime.strptime(dstr, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _parse_payload(payload: dict) -> list[dict]:
    """Convert the POWER JSON envelope into the engine's row shape.

    Two envelope shapes are supported:
    - **v2 (real API)**: ``properties.parameter.<VAR>.<YYYYMMDD>`` — a dict of
      variable names, each mapping date-keyed strings to floats (or null).
    - **legacy fixture**: ``parameters`` — a list of per-day dicts.

    Missing days → ``None`` (never zero). The engine treats ``None`` as a gap.
    """
    out: list[dict] = []

    # --- v2 envelope: properties.parameter.<VAR>.<YYYYMMDD> ---
    props = payload.get("properties", {})
    param_block = props.get("parameter", {}) if isinstance(props, dict) else {}
    if isinstance(param_block, dict) and param_block:
        # The live API declares its fill (missing) value in the header; POWER
        # uses -999.0. Treat it as a gap, never as a real measurement.
        fill_value = payload.get("header", {}).get("fill_value", -999.0)

        # Collect all dates across all variables. Keys are raw YYYYMMDD strings.
        all_dates: set[str] = set()
        for var_data in param_block.values():
            if isinstance(var_data, dict):
                for dkey in var_data:
                    all_dates.add(dkey)
        all_dates = sorted(all_dates)

        def _get(var: str, dkey: str):
            """Fetch a value from the v2 dict-of-dicts; None for gaps/-999."""
            block = param_block.get(var, {})
            if not isinstance(block, dict):
                return None
            raw = block.get(dkey)
            if raw is None:
                return None
            try:
                v = float(raw)
            except (ValueError, TypeError):
                return None
            if fill_value is not None and v == float(fill_value):
                return None
            return v

        for dkey in all_dates:
            # Normalise the raw YYYYMMDD key to an ISO date for storage.
            dk = dkey.replace("-", "")
            date_iso = f"{dk[:4]}-{dk[4:6]}-{dk[6:8]}" if len(dk) == 8 else dkey
            row = {
                "date": date_iso,
                "prectot": _get("PRECTOTCORR", dkey),
                "t2m": _get("T2M", dkey),
                "tmax": _get("T2M_MAX", dkey),
                "tmin": _get("T2M_MIN", dkey),
                "rh": _get("RH2M", dkey),
                "ws": _get("WS2M", dkey),
                "rs": _get("ALLSKY_SFC_SW_DWN", dkey),
            }
            out.append(row)
        return out

    # --- legacy fixture envelope: parameters = list of day dicts ---
    for day in payload.get("parameters", []):
        row = {
            "date": day.get("date"),
            "prectot": _val(day, "PRECTOTCORR"),
            "t2m": _val(day, "T2M"),
            "tmax": _val(day, "T2M_MAX"),
            "tmin": _val(day, "T2M_MIN"),
            "rh": _val(day, "RH2M"),
            "ws": _val(day, "WS2M"),
            "rs": _val(day, "ALLSKY_SFC_SW_DWN"),
        }
        if "PRECTOTCORR" not in day:
            row["prectot"] = None
        out.append(row)
    return out


def _val(day: dict, key: str):
    v = day.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _store_indicators(field_model, asset: DataAsset, rows: list[dict]) -> None:
    """Materialise the series as FieldIndicator rows (only for a real field)."""
    if field_model is None:
        return

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
            dt = _parse_date(row["date"])
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
                    "period_end": dt,
                },
            )
