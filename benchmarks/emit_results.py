#!/usr/bin/env python3
"""Machine-readable validation result artifacts.

Wraps existing validation suites and emits structured JSON/CSV outputs
with version stamps, environment metadata, and pass/fail summaries.

Usage:
    python -m benchmarks.emit_results                # JSON to stdout
    python -m benchmarks.emit_results --csv           # CSV to stdout
    python -m benchmarks.emit_results --out results/  # write to directory
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def _env_metadata() -> dict:
    """Collect environment metadata for reproducibility."""
    try:
        import aethermor
        version = getattr(aethermor, "__version__", "unknown")
    except Exception:
        version = "unknown"
    return {
        "tool": "aethermor",
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def _run_pytest() -> dict:
    """Run pytest and capture structured results."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
        timeout=120,
    )
    # Parse last line like "308 passed, 1 skipped in 5.23s"
    lines = proc.stdout.strip().splitlines()
    summary_line = lines[-1] if lines else ""
    return {
        "suite": "pytest",
        "returncode": proc.returncode,
        "pass": proc.returncode == 0,
        "summary": summary_line,
    }


def _run_validation_suite() -> dict:
    """Run aethermor validate and capture count."""
    proc = subprocess.run(
        [sys.executable, "-m", "aethermor.validation.validate_all"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=60,
    )
    lines = proc.stdout.strip().splitlines()
    summary_line = ""
    for line in lines:
        if "RESULTS:" in line:
            summary_line = line.strip()
            break
    return {
        "suite": "physics_validation",
        "returncode": proc.returncode,
        "pass": proc.returncode == 0,
        "summary": summary_line,
    }


def _run_benchmark_pack() -> dict:
    """Run external benchmark pack."""
    proc = subprocess.run(
        [sys.executable, "-m", "benchmarks.external_benchmark_pack", "--json"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=30,
    )
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            return {
                "suite": "external_benchmarks",
                "returncode": 0,
                "pass": data.get("failed", 1) == 0,
                "summary": f"{data['passed']}/{data['total_cases']} passed",
                "details": data.get("cases", []),
            }
        except json.JSONDecodeError:
            pass
    return {
        "suite": "external_benchmarks",
        "returncode": proc.returncode,
        "pass": False,
        "summary": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "error",
    }


def _run_hardware_correlation() -> dict:
    """Run hardware correlation script."""
    proc = subprocess.run(
        [sys.executable, "-m", "benchmarks.hardware_correlation", "--json"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parent.parent,
        timeout=30,
    )
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            return {
                "suite": "hardware_correlation",
                "returncode": 0,
                "pass": True,
                "summary": f"{len(data.get('cases', []))} cases evaluated",
                "details": data.get("cases", []),
            }
        except json.JSONDecodeError:
            pass
    return {
        "suite": "hardware_correlation",
        "returncode": proc.returncode,
        "pass": proc.returncode == 0,
        "summary": "completed" if proc.returncode == 0 else "error",
    }


def collect_all() -> dict:
    """Run all validation suites and collect results."""
    meta = _env_metadata()
    t0 = time.time()

    suites = [
        _run_pytest(),
        _run_validation_suite(),
        _run_benchmark_pack(),
        _run_hardware_correlation(),
    ]

    elapsed = time.time() - t0
    all_pass = all(s["pass"] for s in suites)

    return {
        **meta,
        "elapsed_s": round(elapsed, 1),
        "overall_pass": all_pass,
        "suites": suites,
    }


def to_csv(report: dict) -> str:
    """Convert report to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["suite", "pass", "returncode", "summary"])
    for s in report["suites"]:
        writer.writerow([s["suite"], s["pass"], s["returncode"], s["summary"]])
    writer.writerow([])
    writer.writerow(["tool", report["tool"]])
    writer.writerow(["version", report["version"]])
    writer.writerow(["timestamp", report["timestamp"]])
    writer.writerow(["python_version", report["python_version"]])
    writer.writerow(["overall_pass", report["overall_pass"]])
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Emit machine-readable validation results")
    parser.add_argument("--csv", action="store_true", help="Output CSV instead of JSON")
    parser.add_argument("--out", type=str, help="Write to directory instead of stdout")
    args = parser.parse_args()

    report = collect_all()

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        json_path = out_dir / f"validation_{ts}.json"
        json_path.write_text(json.dumps(report, indent=2))
        print(f"Wrote {json_path}")

        csv_path = out_dir / f"validation_{ts}.csv"
        csv_path.write_text(to_csv(report))
        print(f"Wrote {csv_path}")
    elif args.csv:
        print(to_csv(report))
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
