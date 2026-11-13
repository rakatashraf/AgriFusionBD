"""Execute every notebook against a named kernel, with diagnostics on failure.

Usage:
    python run_all_notebooks.py [kernel]     # default kernel: bh6

On error it prints the failing cell, the traceback, and an environment probe,
so a failure is diagnosable from the log alone.
"""

from __future__ import annotations

import platform
import sys
import time
import traceback
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

BASE = Path(__file__).resolve().parent
NB_DIR = BASE / "notebooks"
KERNEL = sys.argv[1] if len(sys.argv) > 1 else "bh6"


def environment_probe() -> str:
    lines = [
        f"python      {sys.version.split()[0]}  ({sys.executable})",
        f"platform    {platform.platform()}",
    ]
    for mod in ("pandas", "numpy", "sklearn", "matplotlib", "ipykernel"):
        try:
            m = __import__(mod)
            lines.append(f"{mod:12s}{getattr(m, '__version__', '?')}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{mod:12s}MISSING ({exc})")
    lines.append(f"panels      {(BASE / 'model_ready' / 'daily_panel.csv').exists()}")
    return "\n".join(lines)


def run_one(path: Path) -> dict:
    nb = nbf.read(path, as_version=4)
    started = time.time()
    record = {"notebook": path.name, "status": "ok", "seconds": 0, "cells": 0, "error": ""}
    client = NotebookClient(
        nb,
        timeout=1800,
        kernel_name=KERNEL,
        resources={"metadata": {"path": str(NB_DIR)}},
        allow_errors=False,
    )
    try:
        client.execute()
        record["cells"] = sum(1 for c in nb.cells if c.cell_type == "code")
        nbf.write(nb, path)
    except CellExecutionError as exc:
        record["status"] = "ERROR"
        record["error"] = str(exc)[-2500:]
    except Exception as exc:  # noqa: BLE001  (kernel died, timeout, ...)
        record["status"] = "ERROR"
        record["error"] = "".join(traceback.format_exception_only(type(exc), exc)) + \
                          "\n" + traceback.format_exc()[-1500:]
    record["seconds"] = round(time.time() - started, 1)
    return record


def main() -> int:
    print(f"kernel: {KERNEL}\n")
    print(environment_probe())
    print()

    paths = sorted(NB_DIR.glob("*.ipynb"))
    if not paths:
        print("no notebooks found")
        return 1

    results = []
    for path in paths:
        print(f"running {path.name} ...", flush=True)
        rec = run_one(path)
        results.append(rec)
        print(f"  {rec['status']:<5} {rec['seconds']:>6.1f}s  {rec['cells']} code cells")

    print("\n" + "=" * 72)
    print(f"{'notebook':38s} {'status':8s} {'time':>8s} {'cells':>6s}")
    for r in results:
        print(f"{r['notebook']:38s} {r['status']:8s} {r['seconds']:>7.1f}s {r['cells']:>6d}")

    failures = [r for r in results if r["status"] != "ok"]
    if failures:
        print("\n" + "=" * 72)
        print("DIAGNOSTICS")
        for r in failures:
            print(f"\n--- {r['notebook']} ---")
            print(r["error"])
        return 1

    print(f"\nAll {len(results)} notebooks executed without error.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
