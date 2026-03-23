import json
import os
import shutil

import pandas as pd

from simulation.publication_gate import evaluate_publication_gate


def _mkdir_clean(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


def test_publication_gate_passes_with_valid_inputs():
    report_dir = f"pub_gate_report_pass_{os.getpid()}"
    _mkdir_clean(report_dir)

    stats = pd.DataFrame(
        [
            {
                "experiment": "morphogenesis",
                "n_pairs": 5,
                "mean_delta": 1.0,
                "delta_ci95_low": 0.2,
                "paired_p_value": 0.001,
                "significant_holm_alpha_0_05": 1,
                "holm_p": 0.003,
            },
            {
                "experiment": "material_twin",
                "n_pairs": 5,
                "mean_delta": 2.0,
                "delta_ci95_low": 0.4,
                "paired_p_value": 0.002,
                "significant_holm_alpha_0_05": 1,
                "holm_p": 0.004,
            },
        ]
    )
    stats.to_csv(os.path.join(report_dir, "ablations_statistical.csv"), index=False)

    manifest = {
        "seeds": [100, 101, 102, 103, 104],
        "ablators": [
            {"exists": True, "sha256": "a" * 64},
            {"exists": True, "sha256": "b" * 64},
        ],
    }
    with open(os.path.join(report_dir, "ablations_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    stability = {
        "status": "PASS",
        "energy_finite": 1,
        "energy_bounded": 1,
        "peak_temp_max_K": 320.0,
    }
    with open(os.path.join(report_dir, "test_long_horizon_stability.json"), "w", encoding="utf-8") as f:
        json.dump(stability, f)

    result = evaluate_publication_gate(report_dir=report_dir, min_pairs=5, max_peak_temp_k=500.0)
    assert result["pass"] == 1


def test_publication_gate_fails_on_low_pairs():
    report_dir = f"pub_gate_report_fail_{os.getpid()}"
    _mkdir_clean(report_dir)

    stats = pd.DataFrame(
        [
            {
                "experiment": "metabolic_cluster",
                "n_pairs": 3,
                "mean_delta": 1.0,
                "delta_ci95_low": 0.1,
                "paired_p_value": 0.001,
                "significant_holm_alpha_0_05": 1,
                "holm_p": 0.002,
            }
        ]
    )
    stats.to_csv(os.path.join(report_dir, "ablations_statistical.csv"), index=False)

    manifest = {"seeds": [1, 2, 3], "ablators": [{"exists": True, "sha256": "c" * 64}]}
    with open(os.path.join(report_dir, "ablations_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    stability = {
        "status": "PASS",
        "energy_finite": 1,
        "energy_bounded": 1,
        "peak_temp_max_K": 320.0,
    }
    with open(os.path.join(report_dir, "test_long_horizon_stability.json"), "w", encoding="utf-8") as f:
        json.dump(stability, f)

    result = evaluate_publication_gate(report_dir=report_dir, min_pairs=5, max_peak_temp_k=500.0)
    assert result["pass"] == 0
    names = {c["name"]: c for c in result["checks"]}
    assert names["ablations_min_pairs"]["ok"] == 0


def test_publication_gate_requires_robustness_when_enabled():
    report_dir = f"pub_gate_report_robust_{os.getpid()}"
    _mkdir_clean(report_dir)

    stats = pd.DataFrame(
        [
            {
                "experiment": "morphogenesis",
                "n_pairs": 5,
                "mean_delta": 1.0,
                "delta_ci95_low": 0.2,
                "paired_p_value": 0.001,
                "significant_holm_alpha_0_05": 1,
                "holm_p": 0.003,
            }
        ]
    )
    stats.to_csv(os.path.join(report_dir, "ablations_statistical.csv"), index=False)

    manifest = {"seeds": [1, 2, 3, 4, 5], "ablators": [{"exists": True, "sha256": "d" * 64}]}
    with open(os.path.join(report_dir, "ablations_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    stability = {
        "status": "PASS",
        "energy_finite": 1,
        "energy_bounded": 1,
        "peak_temp_max_K": 320.0,
    }
    with open(os.path.join(report_dir, "test_long_horizon_stability.json"), "w", encoding="utf-8") as f:
        json.dump(stability, f)

    robustness = {"overall_pass": 1, "n_scenarios": 3}
    with open(os.path.join(report_dir, "robustness_publication_summary.json"), "w", encoding="utf-8") as f:
        json.dump(robustness, f)

    ok = evaluate_publication_gate(
        report_dir=report_dir,
        min_pairs=5,
        max_peak_temp_k=500.0,
        require_robustness=True,
        min_robust_scenarios=3,
    )
    assert ok["pass"] == 1

    bad = evaluate_publication_gate(
        report_dir=report_dir,
        min_pairs=5,
        max_peak_temp_k=500.0,
        require_robustness=True,
        min_robust_scenarios=4,
    )
    assert bad["pass"] == 0
