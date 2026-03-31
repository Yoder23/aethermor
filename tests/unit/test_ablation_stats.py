import pandas as pd

from experiments.exp_ablations import AblationSpec, _fdr_bh, _holm_bonferroni, _summarize_experiment


def test_summarize_experiment_reports_paired_statistics():
    spec = AblationSpec(
        name="metabolic_cluster",
        script="aethermor.simulation.benchmark_metabolic_cluster",
        env_var="CLUSTER_ENABLE",
        kpi_path="unused.json",
        metric_key="peak_temp_reduction_C",
    )
    df = pd.DataFrame(
        [
            {"experiment": "metabolic_cluster", "condition": "on", "seed": 100, "value": 10.0},
            {"experiment": "metabolic_cluster", "condition": "off", "seed": 100, "value": 0.0},
            {"experiment": "metabolic_cluster", "condition": "on", "seed": 101, "value": 11.0},
            {"experiment": "metabolic_cluster", "condition": "off", "seed": 101, "value": 0.0},
            {"experiment": "metabolic_cluster", "condition": "on", "seed": 102, "value": 12.0},
            {"experiment": "metabolic_cluster", "condition": "off", "seed": 102, "value": 0.0},
        ]
    )

    row = _summarize_experiment(df, spec)

    assert row["n_on"] == 3
    assert row["n_off"] == 3
    assert row["n_pairs"] == 3
    assert row["mean_delta"] > 0.0
    assert row["delta_ci95_low"] <= row["mean_delta"] <= row["delta_ci95_high"]
    assert row["paired_p_value"] < 0.05
    assert row["significant_alpha_0_05"] == 1


def test_multiple_testing_corrections_are_monotone_and_bounded():
    pvals = [0.001, 0.01, 0.04, 0.2]
    holm = _holm_bonferroni(pvals)
    fdr = _fdr_bh(pvals)

    assert len(holm) == len(pvals)
    assert len(fdr) == len(pvals)
    assert all(0.0 <= p <= 1.0 for p in holm)
    assert all(0.0 <= p <= 1.0 for p in fdr)

    # The strongest signal should remain strongest after correction.
    assert holm[0] <= holm[1] <= holm[2] <= holm[3]
    assert fdr[0] <= fdr[1] <= fdr[2] <= fdr[3]
