"""Re-fetch GPM IMERG days that failed on transient errors.

Reads the combined CSV, finds dates missing from the requested range, retries
just those days, and rewrites the per-region and combined files.
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import download_gpm_imerg as g  # noqa: E402
from nasa_common import DEFAULT_START, date_range, load_earthdata_token, log, make_session, today  # noqa: E402


def main() -> int:
    start = date.fromisoformat(DEFAULT_START)
    end = today()
    existing = sorted(g.OUT.glob("GPM_IMERG_all_regions_daily_*.csv"))
    if not existing:
        log("No existing GPM output to repair.")
        return 1

    df = pd.read_csv(existing[-1], parse_dates=["date"])
    have = set(df["date"].dt.date.unique())
    missing = [d for d in date_range(DEFAULT_START, end.isoformat()) if d not in have]
    log(f"Missing dates: {len(missing)}")
    if not missing:
        log("Nothing to repair.")
        return 0

    session = make_session(load_earthdata_token())
    catalogs = {"final": {}, "late": {}}
    for day in missing:
        for run in ("final", "late"):
            if not catalogs[run].get(day):
                catalogs[run].update(g.month_catalog(session, run, day.year, day.month))

    new_rows = []
    for day in missing:
        run = "final" if day in catalogs["final"] else ("late" if day in catalogs["late"] else None)
        if run is None:
            log(f"  {day}: no granule published")
            continue
        for attempt in range(4):
            try:
                new_rows.extend(g.fetch_day(session, day, run, catalogs[run][day]))
                log(f"  {day}: recovered ({run})")
                break
            except Exception as exc:  # noqa: BLE001
                log(f"  {day}: attempt {attempt + 1} failed: {exc}")
                time.sleep(5 * (attempt + 1))
    session.close()

    if not new_rows:
        log("No days recovered.")
        return 1

    add = pd.DataFrame(new_rows)
    add["date"] = pd.to_datetime(add["date"])
    combined = pd.concat([df, add], ignore_index=True)
    combined = combined.drop_duplicates(subset=["region", "date"], keep="last")
    combined = combined.sort_values(["region", "date"]).reset_index(drop=True)

    for region, part in combined.groupby("region"):
        part.to_csv(g.OUT / f"{region}_GPM_IMERG_daily_{g.slug_dates(start, end)}.csv", index=False)
    out = g.OUT / f"GPM_IMERG_all_regions_daily_{g.slug_dates(start, end)}.csv"
    combined.to_csv(out, index=False)
    log(f"Now {combined['date'].nunique()} days across {combined['region'].nunique()} regions -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
