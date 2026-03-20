"""
Run cross-configuration ablation robustness checks for publication mode.

For each scenario (grid/fault regime), this script runs exp_ablations.py and
collects corrected significance and CI metrics across mechanisms.

Writes:
  <BENCH_ARTIFACT_ROOT>/_report/robustness_publication.csv
  <BENCH_ARTIFACT_ROOT>/_report/robustness_publication_summary.json
"""

import json
import os
import subprocess
import sys
from typing import Dict, List

import pandas as pd


ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
REPORT_DIR = os.path.join(ART_ROOT, "_report")
os.makedirs(REPORT_DIR, exist_ok=True)


def _default_scenarios() -> List[Dict[str, float]]:
    # Balanced runtime vs coverage.
    return [
        {"name": "g24_f20_c2", "grid": 24, "fault_severity": 0.20, "fault_count": 2},
        {"name": "g32_f30_c3", "grid": 32, "fault_severity": 0.30, "fault_count": 3},
        {"name": "g40_f45_c4", "grid": 40, "fault_severity": 0.45, "fault_count": 4},
    ]


def _scenario_root(name: str) -> str:
    return os.path.join(ART_ROOT, "_robustness", name)


def _run_ablation_for_scenario(scn: Dict[str, float], base_seed: int, n_trials: int, bench_steps: int):
    env = os.environ.copy()
    env["BENCH_GRID"] = str(int(scn["grid"]))
    env["FAULT_SEVERITY"] = str(float(scn["fault_severity"]))
    env["FAULT_COUNT"] = str(int(scn["fault_count"]))
    env["ABLATION_N"] = str(int(n_trials))
    env["ABLATION_BASE_SEED"] = str(int(base_seed))
    env["BENCH_STEPS"] = str(int(bench_steps))
    env["BENCH_ARTIFACT_ROOT"] = _scenario_root(scn["name"])

    p = subprocess.run(
        [sys.executable, os.path.join("experiments", "exp_ablations.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    return p


def _read_stats(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def main():
    n_trials = int(os.getenv("PUB_SWEEP_N", os.getenv("ABLATION_N", "6")))
    bench_steps = int(os.getenv("PUB_SWEEP_STEPS", os.getenv("BENCH_STEPS", "80")))
    base_seed = int(os.getenv("PUB_SWEEP_BASE_SEED", "2000"))
    min_pairs = int(os.getenv("PUB_MIN_PAIRS", str(n_trials)))

    scenarios = _default_scenarios()
    rows = []
    run_logs = []

    for i, scn in enumerate(scenarios):
        scn_seed = base_seed + (i * 100)
        p = _run_ablation_for_scenario(
            scn=scn,
            base_seed=scn_seed,
            n_trials=n_trials,
            bench_steps=bench_steps,
        )
        run_logs.append(
            {
                "scenario": scn["name"],
                "exit_code": int(p.returncode),
                "stdout": (p.stdout or "").strip(),
                "stderr": (p.stderr or "").strip(),
            }
        )

        stats_path = os.path.join(_scenario_root(scn["name"]), "_report", "ablations_statistical.csv")
        df = _read_stats(stats_path)
        if p.returncode != 0 or df.empty:
            rows.append(
                {
                    "scenario": scn["name"],
                    "grid": int(scn["grid"]),
                    "fault_severity": float(scn["fault_severity"]),
                    "fault_count": int(scn["fault_count"]),
                    "experiment": "ALL",
                    "n_pairs": 0,
                    "mean_delta": float("nan"),
                    "delta_ci95_low": float("nan"),
                    "paired_p_value": float("nan"),
                    "holm_p": float("nan"),
                    "significant_holm_alpha_0_05": 0,
                    "scenario_pass": 0,
                    "stats_path": stats_path,
                }
            )
            continue

        # Ensure expected numeric columns exist even if older schema is present.
        if "n_pairs" not in df.columns:
            df["n_pairs"] = 0
        if "delta_ci95_low" not in df.columns:
            df["delta_ci95_low"] = float("nan")
        if "paired_p_value" not in df.columns:
            df["paired_p_value"] = float("nan")
        if "holm_p" not in df.columns:
            df["holm_p"] = float("nan")
        if "significant_holm_alpha_0_05" not in df.columns:
            df["significant_holm_alpha_0_05"] = 0

        scenario_pass = int(
            (df["n_pairs"] >= min_pairs).all()
            and (df["significant_holm_alpha_0_05"] == 1).all()
            and (df["delta_ci95_low"] > 0.0).all()
        )
        for _, row in df.iterrows():
            rows.append(
                {
                    "scenario": scn["name"],
                    "grid": int(scn["grid"]),
                    "fault_severity": float(scn["fault_severity"]),
                    "fault_count": int(scn["fault_count"]),
                    "experiment": row.get("experiment"),
                    "n_pairs": int(row.get("n_pairs", 0)),
                    "mean_delta": float(row.get("mean_delta", float("nan"))),
                    "delta_ci95_low": float(row.get("delta_ci95_low", float("nan"))),
                    "paired_p_value": float(row.get("paired_p_value", float("nan"))),
                    "holm_p": float(row.get("holm_p", float("nan"))),
                    "significant_holm_alpha_0_05": int(row.get("significant_holm_alpha_0_05", 0)),
                    "scenario_pass": scenario_pass,
                    "stats_path": stats_path,
                }
            )

    out_csv = os.path.join(REPORT_DIR, "robustness_publication.csv")
    df_all = pd.DataFrame(rows)
    df_all.to_csv(out_csv, index=False)

    scenario_passes = (
        df_all.groupby("scenario")["scenario_pass"].max().to_dict()
        if not df_all.empty and "scenario" in df_all.columns
        else {}
    )
    overall_pass = int(bool(scenario_passes) and all(v == 1 for v in scenario_passes.values()))

    summary = {
        "overall_pass": overall_pass,
        "n_scenarios": len(scenarios),
        "scenario_passes": scenario_passes,
        "n_trials_per_condition": n_trials,
        "bench_steps": bench_steps,
        "min_pairs_required": min_pairs,
        "base_seed": base_seed,
        "rows_csv": out_csv,
        "runs": run_logs,
    }

    out_json = os.path.join(REPORT_DIR, "robustness_publication_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Robustness sweep PASS={bool(overall_pass)}")
    print(f"CSV:  {out_csv}")
    print(f"JSON: {out_json}")
    return 0 if overall_pass == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
