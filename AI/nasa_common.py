"""Shared helpers for the NASA supplementary-data downloads.

Everything here is dependency-light (requests + stdlib) so it runs in the
existing API_NASA_POWER virtualenv. Dataset-specific scripts import
`regions`, `load_earthdata_token`, `make_session`, `date_range` and
`write_csv` from this module.

The region list is the same one used by
API_NASA_POWER/src/data_accusition/download_weather.py so every dataset
lines up row-for-row with the already-downloaded POWER weather CSVs.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DATA_DIR = Path(__file__).resolve().parent
ENV_FILE = DATA_DIR / ".env"

# Representative point per region - identical to download_weather.py.
# Format: region name: (latitude, longitude)
regions: dict[str, tuple[float, float]] = {
    "North_Rangpur": (25.75, 89.25),
    "Northwest_Rajshahi": (24.37, 88.60),
    "Central_Dhaka": (23.81, 90.41),
    "Northeast_Sylhet": (24.89, 91.87),
    "Southwest_Khulna": (22.85, 89.54),
    "South_Barishal": (22.70, 90.35),
    "Southeast_Chattogram": (22.36, 91.78),
}

# Bounding box covering all regions, with a small margin. Useful for
# products that must be subset as a box rather than sampled at a point.
def region_bbox(margin: float = 0.25) -> tuple[float, float, float, float]:
    lats = [lat for lat, _ in regions.values()]
    lons = [lon for _, lon in regions.values()]
    return (
        min(lons) - margin,  # west
        min(lats) - margin,  # south
        max(lons) + margin,  # east
        max(lats) + margin,  # north
    )


DEFAULT_START = "2022-01-01"


def today() -> date:
    """Today in Bangladesh local time."""
    return datetime.now(ZoneInfo("Asia/Dhaka")).date()


def date_range(start: str = DEFAULT_START, end: str | None = None) -> list[date]:
    """Inclusive list of dates from `start` (YYYY-MM-DD or YYYYMMDD) to `end`."""
    start_d = _parse_date(start)
    end_d = _parse_date(end) if end else today()
    if end_d < start_d:
        raise ValueError(f"end {end_d} is before start {start_d}")
    return [start_d + timedelta(days=i) for i in range((end_d - start_d).days + 1)]


def _parse_date(value: str) -> date:
    value = value.strip()
    fmt = "%Y%m%d" if len(value) == 8 and value.isdigit() else "%Y-%m-%d"
    return datetime.strptime(value, fmt).date()


def load_earthdata_token(env_file: Path = ENV_FILE) -> str:
    """Read the Earthdata Login bearer token from Data/.env.

    Accepts `api_token="..."`, `EARTHDATA_TOKEN=...`, or any line whose key
    contains 'token'. Falls back to the process environment.
    """
    token = os.environ.get("EARTHDATA_TOKEN") or os.environ.get("api_token")
    if token:
        return token.strip().strip('"').strip("'")

    if not env_file.exists():
        raise FileNotFoundError(
            f"No Earthdata token found: {env_file} is missing and "
            "EARTHDATA_TOKEN is not set."
        )

    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if "token" in key.strip().lower():
            value = value.strip().strip('"').strip("'")
            if value:
                return value

    raise ValueError(f"No token-like key found in {env_file}")


def make_session(token: str | None = None, *, earthdata: bool = True) -> requests.Session:
    """Session with retries, and the Earthdata bearer token when needed."""
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers.setdefault(
        "User-Agent",
        "fieldshift-nasa-data/1.0 (Bangladesh pilot; python-requests)",
    )
    return session


def write_csv(df: pd.DataFrame, path: Path, *, index: bool = False) -> Path:
    """Write a dataframe to CSV, creating parent folders, UTF-8 without BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index, encoding="utf-8")
    return path


def slug_dates(start: date, end: date) -> str:
    return f"{start:%Y%m%d}_to_{end:%Y%m%d}"


def log(message: str) -> None:
    print(message, flush=True)


def chunked(items: Iterable, size: int):
    """Yield lists of at most `size` items."""
    batch: list = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
