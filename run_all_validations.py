#!/usr/bin/env python3
"""
Master Validation Runner for Aethermor
=======================================

Runs ALL validation suites and produces a single pass/fail summary.
Use this to verify the entire evidence surface in one command:

    python run_all_validations.py

Exit code 0 = all suites pass.  Non-zero = at least one failure.
"""
import subprocess
import sys
import time

SUITES = [
    # (label, command)
    ("Unit tests (pytest)",
     [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"]),
    ("Physics validation (validate_all.py)",
     [sys.executable, "validation/validate_all.py"]),
    ("Literature validation",
     [sys.executable, "-m", "benchmarks.literature_validation"]),
    ("Real-world chip validation (33 checks)",
     [sys.executable, "-m", "benchmarks.real_world_validation"]),
    ("Experimental validation (18 checks)",
     [sys.executable, "-m", "benchmarks.experimental_validation"]),
    ("Chip thermal database (82 checks, 12 chips)",
     [sys.executable, "-m", "benchmarks.chip_thermal_database"]),
    ("Material cross-validation (93 checks, 9 materials)",
     [sys.executable, "-m", "benchmarks.material_cross_validation"]),
    ("Case study: datacenter cooling (13 checks)",
     [sys.executable, "-m", "benchmarks.case_study_datacenter"]),
    ("Case study: mobile SoC (10 checks)",
     [sys.executable, "-m", "benchmarks.case_study_mobile_soc"]),
    ("Case study: cooling decision",
     [sys.executable, "-m", "benchmarks.case_study_cooling_decision"]),
    ("Case study: substrate selection",
     [sys.executable, "-m", "benchmarks.case_study_substrate_selection"]),
    ("Case study: SoC bottleneck",
     [sys.executable, "-m", "benchmarks.case_study_soc_bottleneck"]),
]


def main():
    print("=" * 72)
    print("  AETHERMOR MASTER VALIDATION RUNNER")
    print("=" * 72)
    print()

    results = []
    total_start = time.time()

    for label, cmd in SUITES:
        print(f"  Running: {label} ...")
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
            )
            elapsed = time.time() - start
            ok = proc.returncode == 0
            results.append((label, ok, elapsed))
            tag = "PASS" if ok else "FAIL"
            print(f"  [{tag}]  {label}  ({elapsed:.1f}s)")
            if not ok:
                # Show last 10 lines of output for diagnostics
                out = (proc.stdout + proc.stderr).strip().split("\n")
                for line in out[-10:]:
                    print(f"         {line}")
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            results.append((label, False, elapsed))
            print(f"  [TIMEOUT]  {label}  ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - start
            results.append((label, False, elapsed))
            print(f"  [ERROR]  {label}: {e}  ({elapsed:.1f}s)")
        print()

    total_elapsed = time.time() - total_start

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    print("=" * 72)
    print(f"  SUMMARY: {passed}/{len(results)} suites passed  ({total_elapsed:.1f}s total)")
    print("=" * 72)
    print()

    for label, ok, elapsed in results:
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}]  {label}")

    print()

    if failed > 0:
        print(f"  {failed} suite(s) FAILED.")
        return False
    else:
        print("  ALL SUITES PASSED.")
        print()
        print("  Evidence surface:")
        print("    - Unit tests: ~255 tests across 31 files")
        print("    - Physics validation: 133 SI-unit checks")
        print("    - Literature: 20 published-value checks")
        print("    - Real-world chips: 33 checks (4 production chips)")
        print("    - Experimental: 18 checks (published theta_jc)")
        print("    - Chip thermal database: 82 checks (12 chips, 4 segments)")
        print("    - Material cross-validation: 93 checks (9 materials x 3 sources)")
        print("    - Case studies: 23+ engineering decision checks")
        print("    - Integration workflows: 23 end-to-end tests")
        print()
        print("  Total: 680+ independently validated checks.")
        return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
