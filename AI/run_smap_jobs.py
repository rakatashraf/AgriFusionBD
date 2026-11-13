"""Drive the SMAP Harmony jobs to completion, one job at a time.

Harmony pauses a request when a user has too many granules in flight, so the
jobs are advanced sequentially: resume when paused, download each subset as
soon as it appears, and move on when the job finishes.
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import download_smap as smap  # noqa: E402
from nasa_common import DEFAULT_START, load_earthdata_token, log, make_session, today  # noqa: E402

HARMONY = "https://harmony.earthdata.nasa.gov"


def list_jobs(session) -> list:
    jobs = session.get(f"{HARMONY}/jobs", params={"limit": 50}, timeout=120).json()
    return jobs.get("jobs", [])


def month_of_job(job) -> str:
    return (job.get("createdAt") or "")[:19]


def download_new(session, job_id: str) -> set:
    """Pull every result link the job currently exposes; return saved names."""
    detail = session.get(
        f"{HARMONY}/jobs/{job_id}", params={"page": 1, "limit": 2000}, timeout=180
    ).json()
    saved = set()
    for link in detail.get("links", []):
        if link.get("rel") != "data":
            continue
        href = link["href"]
        name = href.split("/")[-1].split("?")[0]
        path = smap.RAW / name
        if path.exists() and path.stat().st_size > 10_000:
            saved.add(name)
            continue
        r = session.get(href, timeout=300)
        if r.status_code == 200:
            smap.RAW.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            saved.add(name)
    return saved


def advance(session, job_id: str, quiet_polls: int = 6) -> str:
    """Run one job to completion, resuming whenever Harmony pauses it."""
    idle = 0
    last_saved = 0
    jobs = {j["jobID"]: j for j in list_jobs(session)}
    job = jobs.get(job_id, {})
    target = job.get("numInputGranules") or 0
    log(f"  job {job_id[:8]} ({target} granules)")

    while True:
        detail = session.get(
            f"{HARMONY}/jobs/{job_id}", params={"page": 1, "limit": 2000}, timeout=180
        ).json()
        status = detail.get("status")
        saved = download_new(session, job_id)
        if len(saved) > last_saved:
            log(f"    {status} {detail.get('progress')}% - {len(saved)}/{target} subset files")
            last_saved = len(saved)
            idle = 0
        else:
            idle += 1

        if status == "successful":
            log(f"    finished: {len(saved)}/{target} files")
            return "successful"
        if status in ("failed", "canceled"):
            log(f"    {status}: {detail.get('message')}")
            return status
        if status == "paused":
            session.get(f"{HARMONY}/jobs/{job_id}/resume", timeout=120)
            log("    resumed")
            idle = 0
        if idle >= quiet_polls * 30:
            log("    giving up after prolonged inactivity")
            return status
        time.sleep(20)


def main() -> int:
    start = date.fromisoformat(DEFAULT_START)
    end = today()
    session = make_session(load_earthdata_token())

    jobs = [j for j in list_jobs(session) if "SPL3SMP_E" in (j.get("collectionId") or "")]
    pending = [j for j in jobs if j.get("status") in ("paused", "running")]
    log(f"{len(jobs)} SMAP jobs known, {len(pending)} still open")

    covered_years = set()
    for job in jobs:
        if job.get("status") == "successful":
            covered_years.add((job.get("createdAt") or "")[:4])

    for job in sorted(pending, key=lambda j: j.get("createdAt") or ""):
        advance(session, job["jobID"])

    for year in range(start.year, end.year + 1):
        if any(
            j.get("status") == "successful" and str(year) in (j.get("createdAt") or "")
            for j in list_jobs(session)
        ):
            continue
        ys = max(date(year, 1, 1), start)
        ye = min(date(year, 12, 31), end)
        if ys > ye:
            continue
        log(f"  submitting {year}: {ys} -> {ye}")
        try:
            job_id = smap.submit(session, ys, ye)
        except Exception as exc:  # noqa: BLE001
            log(f"    submit failed: {exc}")
            continue
        advance(session, job_id)

    session.close()
    files = sorted(smap.RAW.glob("*_subsetted.nc4"))
    log(f"\n{len(files)} subset files on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
