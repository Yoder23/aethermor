# benchmark_thermodynamic_core.py
import os
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from aethermor_full_simulation_v2 import AethermorSimV2
from thermodynamic_core import ThermodynamicAICore

ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
ARTS = os.path.join(ART_ROOT, "thermo_core")
os.makedirs(ARTS, exist_ok=True)


def _run_sim(label: str, compute_cost: float, steps: int = 150) -> pd.DataFrame:
    """
    Run AethermorSimV2 with thermodynamic accounting enabled.
    """
    seed = int(os.getenv("AETHERMOR_SEED", "42"))
    sim = AethermorSimV2(steps=steps, seed=seed)
    sim.compute_cost = compute_cost
    sim.ai_core = ThermodynamicAICore()
    sim.run()
    df = pd.DataFrame(sim.metrics)
    df["label"] = label
    return df


def _useful_bits(df: pd.DataFrame) -> np.ndarray:
    """
    Useful output proxy: positive change in total knowledge.
    """
    total_k = df["total_knowledge"].values.astype(float)
    return np.clip(np.diff(total_k, prepend=0.0), 0.0, None)


def _landauer_step_energy(df: pd.DataFrame) -> np.ndarray:
    """
    Convert cumulative Landauer lower-bound Joules into stepwise Joules.
    """
    cumulative = df["landauer_J"].values.astype(float)
    stepwise = np.diff(cumulative, prepend=0.0)
    stepwise = np.clip(stepwise, 0.0, None)
    return np.where(stepwise <= 1e-30, 1e-30, stepwise)


def _compute_step_energy(df: pd.DataFrame) -> np.ndarray:
    """
    Use simulator compute-energy bookkeeping as the primary energy proxy.
    Landauer is retained as a lower-bound diagnostic metric.
    """
    if "compute_energy_step" in df.columns:
        e = df["compute_energy_step"].to_numpy(dtype=float)
    else:
        # Backward-compatible fallback
        e = np.full(len(df), 1e-12, dtype=float)
    e = np.clip(e, 1e-12, None)
    return e


def _efficiency(df: pd.DataFrame):
    useful_bits = _useful_bits(df)
    compute_e = _compute_step_energy(df)
    landauer_J = _landauer_step_energy(df)
    return useful_bits, compute_e, landauer_J, useful_bits / compute_e


def main():
    # --- 1. Two regimes: "naive" vs "thermodynamic" -------------------------
    # Naive: higher compute cost (burns more energy per step)
    # Thermodynamic-ish: lower compute cost (gates computation more gently)
    base_sim = AethermorSimV2(steps=1)
    base_cost = base_sim.compute_cost

    df_naive = _run_sim("naive", compute_cost=base_cost * 1.5)
    df_opt   = _run_sim("thermo_core", compute_cost=base_cost * 0.75)

    # Optional "none" regime: almost no compute (shows lower bound)
    df_none = _run_sim("none", compute_cost=base_cost * 0.05)

    # --- 2. Derive useful-bits / Landauer-J efficiency ----------------------
    bits_na, energy_na, landauer_na, eff_na = _efficiency(df_naive)
    bits_op, energy_op, landauer_op, eff_op = _efficiency(df_opt)
    bits_no, energy_no, landauer_no, eff_no = _efficiency(df_none)

    # --- 3. Aggregate KPIs ---------------------------------------------------
    mean_eff_na = float(np.nanmean(eff_na))
    mean_eff_op = float(np.nanmean(eff_op))
    mean_eff_no = float(np.nanmean(eff_no))

    bits_per_joule_gain_vs_naive = float(100.0 * (mean_eff_op - mean_eff_na) / max(1e-30, mean_eff_na))
    bits_per_joule_gain_vs_none  = float(100.0 * (mean_eff_op - mean_eff_no) / max(1e-30, mean_eff_no))

    # Bookkeeping sanity checks
    mono_naive = int(np.all(np.diff(df_naive["landauer_J"].values.astype(float)) >= -1e-18))
    mono_opt = int(np.all(np.diff(df_opt["landauer_J"].values.astype(float)) >= -1e-18))
    mono_none = int(np.all(np.diff(df_none["landauer_J"].values.astype(float)) >= -1e-18))

    kpis = {
        "mean_useful_bits_naive": float(np.nanmean(bits_na)),
        "mean_useful_bits_thermo": float(np.nanmean(bits_op)),
        "mean_compute_energy_naive": float(np.nanmean(energy_na)),
        "mean_compute_energy_thermo": float(np.nanmean(energy_op)),
        "mean_landauer_J_naive": float(np.nanmean(landauer_na)),
        "mean_landauer_J_thermo": float(np.nanmean(landauer_op)),
        "mean_eff_naive_bits_per_unit": float(mean_eff_na),
        "mean_eff_thermo_bits_per_unit": float(mean_eff_op),
        "bits_per_joule_gain_vs_naive_pct": float(bits_per_joule_gain_vs_naive),
        "bits_per_joule_gain_vs_none_pct": float(bits_per_joule_gain_vs_none),
        "landauer_monotonic_naive": mono_naive,
        "landauer_monotonic_optimized": mono_opt,
        "landauer_monotonic_none": mono_none,
        "mean_temp_naive_K": float(df_naive["mean_temp"].mean()),
        "mean_temp_thermo_K": float(df_opt["mean_temp"].mean()),
    }

    os.makedirs(ARTS, exist_ok=True)
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Thermo Core KPIs:", kpis)

    # --- 4. Visualization ---------------------------------------------------
    steps = df_naive["step"].values

    plt.figure(figsize=(10, 4))
    plt.plot(steps, eff_na, label="Naive (high cost)", alpha=0.7)
    plt.plot(steps, eff_op, label="Thermo core (lower cost)", alpha=0.7)
    plt.xlabel("Step")
    plt.ylabel("Useful bits per Landauer-J")
    plt.title("Thermodynamic Efficiency: Naive vs Thermo Policy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(ARTS, "eff_compare.png"))
    plt.close()


if __name__ == "__main__":
    main()
