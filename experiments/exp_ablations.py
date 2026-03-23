# experiments/exp_ablations.py
"""
Run real ON/OFF ablations across seeded benchmark executions.

This script does not use synthetic data. It launches benchmark scripts,
reads generated KPI JSON files, and computes statistical significance
from observed per-seed measurements. It reports both unpaired statistics
(Welch/Mann-Whitney) and paired-seed statistics (paired t-test/Wilcoxon).

Writes:
  artifacts/_report/ablations_runs.csv
  artifacts/_report/ablations_statistical.csv
  artifacts/_report/ablations_summary.md
  artifacts/_report/ablations_manifest.json
  artifacts/_report/ablations.log
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats


ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
REPORT_DIR = os.path.join(ART_ROOT, "_report")
os.makedirs(REPORT_DIR, exist_ok=True)


@dataclass(frozen=True)
class AblationSpec:
    name: str
    script: str
    env_var: str
    kpi_path: str
    metric_key: str


ABLATORS: List[AblationSpec] = [
    AblationSpec(
        name="morphogenesis",
        script="simulation.benchmark_morphogenesis",
        env_var="MORPHO_ENABLE",
        kpi_path=os.path.join(ART_ROOT, "morphogenesis", "kpis.json"),
        metric_key="uptime_gain_pct",
    ),
    AblationSpec(
        name="material_twin",
        script="simulation.benchmark_material_twin",
        env_var="TWIN_ENABLE",
        kpi_path=os.path.join(ART_ROOT, "material_twin", "kpis.json"),
        metric_key="roi_recovery_gain_pct",
    ),
    AblationSpec(
        name="metabolic_cluster",
        script="simulation.benchmark_metabolic_cluster",
        env_var="CLUSTER_ENABLE",
        kpi_path=os.path.join(ART_ROOT, "metabolic_cluster", "kpis.json"),
        metric_key="peak_temp_reduction_C",
    ),
]


def _safe_read_json(path: str) -> Dict[str, float]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return float("nan")
    var1 = np.var(group1, ddof=1)
    var2 = np.var(group2, ddof=1)
    pooled = (((n1 - 1) * var1) + ((n2 - 1) * var2)) / max(1, (n1 + n2 - 2))
    if pooled <= 0:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / math.sqrt(pooled))


def _cohens_dz(deltas: np.ndarray) -> float:
    if len(deltas) < 2:
        return float("nan")
    s = float(np.std(deltas, ddof=1))
    if s == 0.0:
        m = float(np.mean(deltas))
        return float("inf") if m > 0 else (float("-inf") if m < 0 else 0.0)
    return float(np.mean(deltas) / s)


def _bootstrap_ci_mean(values: np.ndarray, ci: float = 0.95, n_boot: int = 2000, seed: int = 12345) -> Tuple[float, float]:
    if len(values) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=float)
    n = len(values)
    for i in range(n_boot):
        sample = values[rng.integers(0, n, size=n)]
        means[i] = float(np.mean(sample))
    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(means, alpha))
    hi = float(np.quantile(means, 1.0 - alpha))
    return lo, hi


def _holm_bonferroni(pvals: Sequence[float]) -> List[float]:
    m = len(pvals)
    adj = [float("nan")] * m
    finite = [(i, float(p)) for i, p in enumerate(pvals) if np.isfinite(p)]
    if not finite:
        return adj

    finite_sorted = sorted(finite, key=lambda x: x[1])
    running_max = 0.0
    for rank, (idx, p) in enumerate(finite_sorted, start=1):
        factor = (m - rank + 1)
        value = min(1.0, p * factor)
        running_max = max(running_max, value)
        adj[idx] = running_max
    return adj


def _fdr_bh(pvals: Sequence[float]) -> List[float]:
    m = len(pvals)
    adj = [float("nan")] * m
    finite = [(i, float(p)) for i, p in enumerate(pvals) if np.isfinite(p)]
    if not finite:
        return adj

    finite_sorted = sorted(finite, key=lambda x: x[1])
    raw_adj = []
    for rank, (_, p) in enumerate(finite_sorted, start=1):
        raw_adj.append(min(1.0, p * m / rank))

    monotone = [0.0] * len(raw_adj)
    current = 1.0
    for i in range(len(raw_adj) - 1, -1, -1):
        current = min(current, raw_adj[i])
        monotone[i] = current

    for (idx, _), p_adj in zip(finite_sorted, monotone):
        adj[idx] = float(p_adj)
    return adj


def _safe_sha256(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_manifest(n_trials: int, seeds: List[int], bench_steps: int) -> Dict[str, object]:
    scripts = []
    for spec in ABLATORS:
        scripts.append(
            {
                "name": spec.name,
                "script": spec.script,
                "exists": os.path.isfile(spec.script),
                "sha256": _safe_sha256(spec.script),
                "env_toggle": spec.env_var,
                "metric_key": spec.metric_key,
            }
        )

    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "cwd": os.getcwd(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "controls": {
            "ABLATION_N": n_trials,
            "ABLATION_BASE_SEED": seeds[0] if seeds else None,
            "BENCH_STEPS": bench_steps,
            "BENCH_GRID": os.getenv("BENCH_GRID"),
            "BENCH_ARTIFACT_ROOT": ART_ROOT,
        },
        "seeds": seeds,
        "ablators": scripts,
    }


def _build_summary_markdown(summary_rows: List[dict], pass_count_raw: int, pass_count_holm: int) -> str:
    lines = []
    lines.append("# Aethermor Ablation Statistical Summary")
    lines.append("")
    lines.append(f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Significant at alpha=0.05 (raw): {pass_count_raw}/{len(summary_rows)}")
    lines.append(f"- Significant at alpha=0.05 (Holm corrected): {pass_count_holm}/{len(summary_rows)}")
    lines.append("")
    lines.append("| experiment | metric | mean_on | mean_off | mean_delta | delta_ci95_low | delta_ci95_high | paired_p | holm_p | fdr_bh_p |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary_rows:
        lines.append(
            "| {experiment} | {metric} | {mean_on:.6g} | {mean_off:.6g} | {mean_delta:.6g} | {delta_ci95_low:.6g} | {delta_ci95_high:.6g} | {paired_p_value:.6g} | {holm_p:.6g} | {fdr_bh_p:.6g} |".format(
                **row
            )
        )
    lines.append("")
    lines.append("Notes:")
    lines.append("- Primary inferential result is the paired test because runs are seed-paired ON/OFF.")
    lines.append("- Holm correction controls family-wise error across the ablation set.")
    lines.append("- FDR-BH values are included for discovery-oriented interpretation.")
    return "\n".join(lines)


def _run_condition(spec: AblationSpec, enabled: bool, seeds: List[int], bench_steps: int) -> Tuple[List[dict], List[str]]:
    cond_name = "on" if enabled else "off"
    rows: List[dict] = []
    logs: List[str] = []

    for seed in seeds:
        env = os.environ.copy()
        env[spec.env_var] = "1" if enabled else "0"
        env["AETHERMOR_SEED"] = str(seed)
        env["BENCH_STEPS"] = str(bench_steps)

        p = subprocess.run(
            [sys.executable, "-m", spec.script],
            env=env,
            capture_output=True,
            text=True,
        )
        logs.append(
            (
                f"[{spec.name}::{cond_name}] seed={seed} exit={p.returncode}\n"
                f"STDOUT:\n{(p.stdout or '').strip()}\n"
                f"STDERR:\n{(p.stderr or '').strip()}\n"
            )
        )

        kpi = _safe_read_json(spec.kpi_path)
        value = kpi.get(spec.metric_key)
        try:
            value = float(value)
        except Exception:
            value = float("nan")

        rows.append(
            {
                "experiment": spec.name,
                "condition": cond_name,
                "seed": seed,
                "metric": spec.metric_key,
                "value": value,
                "exit_code": int(p.returncode),
            }
        )

    return rows, logs


def _summarize_experiment(df: pd.DataFrame, spec: AblationSpec) -> dict:
    on_df = df[(df["experiment"] == spec.name) & (df["condition"] == "on")][["seed", "value"]].dropna()
    off_df = df[(df["experiment"] == spec.name) & (df["condition"] == "off")][["seed", "value"]].dropna()
    on = on_df["value"].to_numpy(dtype=float)
    off = off_df["value"].to_numpy(dtype=float)

    if len(on) < 2 or len(off) < 2:
        return {
            "experiment": spec.name,
            "metric": spec.metric_key,
            "n_on": int(len(on)),
            "n_off": int(len(off)),
            "n_on_valid": int(len(on_df)),
            "n_off_valid": int(len(off_df)),
            "mean_on": float(np.mean(on)) if len(on) else float("nan"),
            "std_on": float(np.std(on, ddof=1)) if len(on) > 1 else float("nan"),
            "mean_off": float(np.mean(off)) if len(off) else float("nan"),
            "std_off": float(np.std(off, ddof=1)) if len(off) > 1 else float("nan"),
            "t_stat": float("nan"),
            "p_value": float("nan"),
            "n_pairs": 0,
            "mean_delta": float("nan"),
            "std_delta": float("nan"),
            "delta_ci95_low": float("nan"),
            "delta_ci95_high": float("nan"),
            "paired_t_stat": float("nan"),
            "paired_p_value": float("nan"),
            "wilcoxon_p": float("nan"),
            "cohens_d": float("nan"),
            "cohens_dz": float("nan"),
            "significant_alpha_0_05": 0,
        }

    if np.std(on, ddof=1) == 0.0 and np.std(off, ddof=1) == 0.0:
        mean_diff = float(np.mean(on) - np.mean(off))
        t_stat = float("inf") if mean_diff != 0.0 else 0.0
        p_value = 0.0 if mean_diff != 0.0 else 1.0
    else:
        # Welch's t-test is safer under unequal variances.
        t_stat, p_value = stats.ttest_ind(on, off, equal_var=False)
    d = _cohens_d(on, off)
    try:
        _, mann_p = stats.mannwhitneyu(on, off, alternative="two-sided")
    except Exception:
        mann_p = float("nan")

    paired = pd.merge(on_df, off_df, on="seed", suffixes=("_on", "_off"))
    deltas = (paired["value_on"] - paired["value_off"]).to_numpy(dtype=float) if not paired.empty else np.array([])
    mean_delta = float(np.mean(deltas)) if len(deltas) else float("nan")
    std_delta = float(np.std(deltas, ddof=1)) if len(deltas) > 1 else float("nan")
    delta_ci95_low, delta_ci95_high = _bootstrap_ci_mean(deltas, ci=0.95, n_boot=2000, seed=12345)

    if len(deltas) >= 2:
        if np.std(deltas, ddof=1) == 0.0:
            paired_t = float("inf") if mean_delta != 0.0 else 0.0
            paired_p = 0.0 if mean_delta != 0.0 else 1.0
        else:
            paired_t, paired_p = stats.ttest_rel(paired["value_on"], paired["value_off"])
        try:
            _, wilcoxon_p = stats.wilcoxon(deltas)
        except Exception:
            wilcoxon_p = float("nan")
    else:
        paired_t = float("nan")
        paired_p = float("nan")
        wilcoxon_p = float("nan")

    dz = _cohens_dz(deltas)
    sig_p = paired_p if np.isfinite(paired_p) else p_value
    return {
        "experiment": spec.name,
        "metric": spec.metric_key,
        "n_on": int(len(on)),
        "n_off": int(len(off)),
        "n_on_valid": int(len(on_df)),
        "n_off_valid": int(len(off_df)),
        "mean_on": float(np.mean(on)),
        "std_on": float(np.std(on, ddof=1)),
        "mean_off": float(np.mean(off)),
        "std_off": float(np.std(off, ddof=1)),
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "mannwhitney_p": float(mann_p),
        "n_pairs": int(len(deltas)),
        "mean_delta": float(mean_delta),
        "std_delta": float(std_delta),
        "delta_ci95_low": float(delta_ci95_low),
        "delta_ci95_high": float(delta_ci95_high),
        "paired_t_stat": float(paired_t),
        "paired_p_value": float(paired_p),
        "wilcoxon_p": float(wilcoxon_p),
        "cohens_d": float(d),
        "cohens_dz": float(dz),
        "significant_alpha_0_05": int(float(sig_p) < 0.05),
    }


def main():
    n_trials = int(os.getenv("ABLATION_N", "5"))
    base_seed = int(os.getenv("ABLATION_BASE_SEED", "100"))
    bench_steps = int(os.getenv("BENCH_STEPS", "80"))
    seeds = [base_seed + i for i in range(n_trials)]
    manifest = _build_manifest(n_trials=n_trials, seeds=seeds, bench_steps=bench_steps)

    all_rows: List[dict] = []
    all_logs: List[str] = []

    for spec in ABLATORS:
        rows_on, logs_on = _run_condition(spec, enabled=True, seeds=seeds, bench_steps=bench_steps)
        rows_off, logs_off = _run_condition(spec, enabled=False, seeds=seeds, bench_steps=bench_steps)
        all_rows.extend(rows_on)
        all_rows.extend(rows_off)
        all_logs.extend(logs_on)
        all_logs.extend(logs_off)

    runs_df = pd.DataFrame(all_rows)
    runs_csv = os.path.join(REPORT_DIR, "ablations_runs.csv")
    runs_df.to_csv(runs_csv, index=False)

    summary_rows = [_summarize_experiment(runs_df, spec) for spec in ABLATORS]
    p_for_correction = []
    for row in summary_rows:
        p = row.get("paired_p_value")
        if not np.isfinite(p):
            p = row.get("p_value")
        try:
            p_for_correction.append(float(p))
        except Exception:
            p_for_correction.append(float("nan"))
    holm = _holm_bonferroni(p_for_correction)
    fdr = _fdr_bh(p_for_correction)
    for row, p_raw, p_holm, p_fdr in zip(summary_rows, p_for_correction, holm, fdr):
        row["p_value_for_correction"] = float(p_raw)
        row["holm_p"] = float(p_holm) if np.isfinite(p_holm) else float("nan")
        row["fdr_bh_p"] = float(p_fdr) if np.isfinite(p_fdr) else float("nan")
        row["significant_holm_alpha_0_05"] = int(float(row["holm_p"]) < 0.05) if np.isfinite(row["holm_p"]) else 0
        row["significant_fdr_bh_alpha_0_05"] = int(float(row["fdr_bh_p"]) < 0.05) if np.isfinite(row["fdr_bh_p"]) else 0

    summary_df = pd.DataFrame(summary_rows)
    summary_csv = os.path.join(REPORT_DIR, "ablations_statistical.csv")
    summary_df.to_csv(summary_csv, index=False)

    pass_count = int(summary_df["significant_alpha_0_05"].sum()) if not summary_df.empty else 0
    pass_count_holm = int(summary_df["significant_holm_alpha_0_05"].sum()) if not summary_df.empty else 0
    total = len(summary_df)

    log_lines = [
        "=" * 80,
        "AETHERMOR ABLATION TESTS (REAL BENCHMARK EXECUTION)",
        "=" * 80,
        f"Trials per condition: {n_trials}",
        f"Seed range: {seeds[0]}..{seeds[-1]}",
        f"BENCH_STEPS: {bench_steps}",
        f"Raw runs CSV: {runs_csv}",
        f"Stats CSV: {summary_csv}",
        f"Significant at alpha=0.05 (raw): {pass_count}/{total}",
        f"Significant at alpha=0.05 (Holm): {pass_count_holm}/{total}",
        "",
    ]

    for row in summary_rows:
        log_lines.extend(
            [
                f"[{row['experiment']}] metric={row['metric']}",
                f"  ON : mean={row['mean_on']:.6g} std={row['std_on']:.6g} n={row['n_on']}",
                f"  OFF: mean={row['mean_off']:.6g} std={row['std_off']:.6g} n={row['n_off']}",
                f"  Welch t={row['t_stat']:.6g}, p={row['p_value']:.6g}, d={row['cohens_d']:.6g}",
                f"  Mann-Whitney p={row['mannwhitney_p']:.6g}",
                f"  Paired delta mean={row['mean_delta']:.6g}, std={row['std_delta']:.6g}, n_pairs={row['n_pairs']}",
                f"  Paired delta CI95=[{row['delta_ci95_low']:.6g}, {row['delta_ci95_high']:.6g}]",
                f"  Paired t={row['paired_t_stat']:.6g}, p={row['paired_p_value']:.6g}",
                f"  Wilcoxon p={row['wilcoxon_p']:.6g}",
                f"  p_for_correction={row['p_value_for_correction']:.6g}, holm_p={row['holm_p']:.6g}, fdr_bh_p={row['fdr_bh_p']:.6g}",
                f"  cohens_d={row['cohens_d']:.6g}, cohens_dz={row['cohens_dz']:.6g}",
                f"  significant_alpha_0_05={row['significant_alpha_0_05']}",
                f"  significant_holm_alpha_0_05={row['significant_holm_alpha_0_05']}",
                "",
            ]
        )

    log_lines.append("-" * 80)
    log_lines.append("Per-run subprocess logs:")
    log_lines.append("-" * 80)
    log_lines.extend(all_logs)

    log_path = os.path.join(REPORT_DIR, "ablations.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    summary_md = os.path.join(REPORT_DIR, "ablations_summary.md")
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write(_build_summary_markdown(summary_rows, pass_count, pass_count_holm))

    manifest_path = os.path.join(REPORT_DIR, "ablations_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n".join(log_lines[:13]))
    print(f"Detailed log: {log_path}")
    print(f"Summary markdown: {summary_md}")
    print(f"Run manifest: {manifest_path}")


if __name__ == "__main__":
    main()
