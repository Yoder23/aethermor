#!/usr/bin/env python3
"""
Publication readiness gate for Aethermor artifacts.

This script validates that generated benchmark artifacts meet a minimum
publication-quality standard before claims are made.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np
import pandas as pd


ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
REPORT_DIR = os.path.join(ART_ROOT, "_report")


def _check(name: str, ok: bool, details: str) -> Dict[str, Any]:
    return {"name": name, "ok": int(bool(ok)), "details": details}


def evaluate_publication_gate(
    report_dir: str,
    min_pairs: int = 5,
    max_peak_temp_k: float = 500.0,
    require_robustness: bool = False,
    min_robust_scenarios: int = 3,
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    stats_path = os.path.join(report_dir, "ablations_statistical.csv")
    manifest_path = os.path.join(report_dir, "ablations_manifest.json")
    stability_path = os.path.join(report_dir, "test_long_horizon_stability.json")
    robustness_path = os.path.join(report_dir, "robustness_publication_summary.json")

    checks.append(_check("ablations_stats_exists", os.path.isfile(stats_path), stats_path))
    checks.append(_check("ablations_manifest_exists", os.path.isfile(manifest_path), manifest_path))
    checks.append(_check("stability_report_exists", os.path.isfile(stability_path), stability_path))

    if os.path.isfile(stats_path):
        df = pd.read_csv(stats_path)
        required_cols = [
            "experiment",
            "n_pairs",
            "mean_delta",
            "delta_ci95_low",
            "paired_p_value",
            "significant_holm_alpha_0_05",
            "holm_p",
        ]
        missing = [c for c in required_cols if c not in df.columns]
        checks.append(_check("ablations_required_columns", len(missing) == 0, ",".join(missing) if missing else "ok"))

        if not missing and not df.empty:
            n_pairs_ok = bool((df["n_pairs"] >= min_pairs).all())
            checks.append(_check("ablations_min_pairs", n_pairs_ok, f"min_pairs={min_pairs}"))

            holm_ok = bool((df["significant_holm_alpha_0_05"] == 1).all())
            checks.append(_check("ablations_holm_significance", holm_ok, "all mechanisms must pass Holm alpha=0.05"))

            ci_positive_ok = bool((df["delta_ci95_low"] > 0.0).all())
            checks.append(_check("ablations_positive_ci", ci_positive_ok, "all paired delta CI lower bounds must be > 0"))

            paired_p_ok = bool((df["paired_p_value"] < 0.05).all())
            checks.append(_check("ablations_paired_p", paired_p_ok, "all paired p-values must be < 0.05"))

            finite_ok = bool(np.isfinite(df["mean_delta"]).all() and np.isfinite(df["holm_p"]).all())
            checks.append(_check("ablations_finite_metrics", finite_ok, "mean_delta and holm_p must be finite"))
        else:
            checks.append(_check("ablations_non_empty", False, "ablations_statistical.csv is empty"))

    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        seeds = manifest.get("seeds", [])
        checks.append(_check("manifest_seed_count", len(seeds) >= min_pairs, f"seed_count={len(seeds)}, min_pairs={min_pairs}"))

        ablator_rows = manifest.get("ablators", [])
        hash_ok = True
        for row in ablator_rows:
            sha = str(row.get("sha256", ""))
            exists = bool(row.get("exists", False))
            if not exists or len(sha) != 64:
                hash_ok = False
                break
        checks.append(_check("manifest_script_hashes", hash_ok, "all ablator scripts must exist with SHA-256"))

    if os.path.isfile(stability_path):
        with open(stability_path, "r", encoding="utf-8") as f:
            stability = json.load(f)

        checks.append(_check("stability_status", stability.get("status") == "PASS", f"status={stability.get('status')}"))
        checks.append(
            _check(
                "stability_energy_bounds",
                int(stability.get("energy_finite", 0)) == 1 and int(stability.get("energy_bounded", 0)) == 1,
                f"energy_finite={stability.get('energy_finite')} energy_bounded={stability.get('energy_bounded')}",
            )
        )
        peak_temp = float(stability.get("peak_temp_max_K", float("nan")))
        checks.append(_check("stability_peak_temp", np.isfinite(peak_temp) and peak_temp <= max_peak_temp_k, f"peak_temp_max_K={peak_temp}"))

    if require_robustness:
        checks.append(_check("robustness_summary_exists", os.path.isfile(robustness_path), robustness_path))
        if os.path.isfile(robustness_path):
            with open(robustness_path, "r", encoding="utf-8") as f:
                robustness = json.load(f)
            n_scenarios = int(robustness.get("n_scenarios", 0))
            overall_pass = int(robustness.get("overall_pass", 0))
            checks.append(
                _check(
                    "robustness_scenario_count",
                    n_scenarios >= min_robust_scenarios,
                    f"n_scenarios={n_scenarios}, min={min_robust_scenarios}",
                )
            )
            checks.append(_check("robustness_overall_pass", overall_pass == 1, f"overall_pass={overall_pass}"))

    passed = bool(all(c["ok"] == 1 for c in checks))
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": report_dir,
        "criteria": {
            "min_pairs": min_pairs,
            "max_peak_temp_k": max_peak_temp_k,
            "require_robustness": int(require_robustness),
            "min_robust_scenarios": min_robust_scenarios,
        },
        "checks": checks,
        "pass": int(passed),
    }


def _to_markdown(result: Dict[str, Any]) -> str:
    lines = []
    lines.append("# Publication Gate Report")
    lines.append("")
    lines.append(f"- Generated (UTC): {result.get('created_utc')}")
    lines.append(f"- Report dir: `{result.get('report_dir')}`")
    lines.append(f"- PASS: {'YES' if result.get('pass') else 'NO'}")
    lines.append("")
    lines.append("| check | ok | details |")
    lines.append("|---|---:|---|")
    for row in result.get("checks", []):
        lines.append(f"| {row.get('name')} | {row.get('ok')} | {row.get('details')} |")
    return "\n".join(lines)


def main() -> int:
    min_pairs = int(os.getenv("PUB_MIN_PAIRS", os.getenv("ABLATION_N", "5")))
    max_peak_temp_k = float(os.getenv("PUB_MAX_PEAK_TEMP_K", "500"))
    require_robustness = os.getenv("PUB_REQUIRE_ROBUSTNESS", "0") == "1"
    min_robust_scenarios = int(os.getenv("PUB_MIN_ROBUST_SCENARIOS", "3"))

    os.makedirs(REPORT_DIR, exist_ok=True)
    result = evaluate_publication_gate(
        report_dir=REPORT_DIR,
        min_pairs=min_pairs,
        max_peak_temp_k=max_peak_temp_k,
        require_robustness=require_robustness,
        min_robust_scenarios=min_robust_scenarios,
    )

    out_json = os.path.join(REPORT_DIR, "publication_gate.json")
    out_md = os.path.join(REPORT_DIR, "publication_gate.md")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(_to_markdown(result))

    print(f"Publication gate PASS={bool(result['pass'])}")
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")
    return 0 if result["pass"] == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
