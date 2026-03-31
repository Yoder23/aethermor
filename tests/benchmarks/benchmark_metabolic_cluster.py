# benchmark_metabolic_cluster.py
"""
Metabolic cluster benchmark

Goal:
- Compare a "pinned hotspot" workload (no scheduling) against a simple
  metabolic cluster controller that offloads work when a region overheats.

Outputs:
- artifacts/metabolic_cluster/no_cluster_timeseries.csv
- artifacts/metabolic_cluster/metabolic_cluster_timeseries.csv
- artifacts/metabolic_cluster/hotspot_compare.png
- artifacts/metabolic_cluster/kpis.json
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from aethermor.simulation.aethermor_full_simulation_v2 import AethermorSimV2

ARTS = "artifacts/metabolic_cluster"
os.makedirs(ARTS, exist_ok=True)

TOTAL_STEPS = 80

# Hotspot: a small region near center
HS_SLICE = (slice(14, 18), slice(14, 18), slice(0, 2))


def _measure(sim):
    hs_temp = float(sim.temp_field[HS_SLICE].mean())
    hs_energy = float(sim.energy_field[HS_SLICE].mean())
    return hs_temp, hs_energy


def _run_no_cluster(seed: int = 0):
    """
    Baseline: heavy workload is pinned to a hotspot.
    Each step we inject heat into HS_SLICE to simulate power density.
    """
    sim = AethermorSimV2(grid_shape=(32, 32, 4), steps=TOTAL_STEPS, seed=seed)
    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Pinned workload: always hammer the hotspot with extra heat
        sim.temp_field[HS_SLICE] += 8.0  # strong local heating

        hs_temp, hs_energy = _measure(sim)
        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "hs_temp": hs_temp,
                "hs_energy": hs_energy,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "no_cluster_timeseries.csv"), index=False)
    return df


def _run_metabolic_cluster(seed: int = 1):
    """
    Metabolic cluster:
    - Same hotspot heating as baseline.
    - BUT if the hotspot exceeds a temperature threshold, we:
        * reduce local heating (simulating workload migration),
        * slightly cool the hotspot region (simulating throttling / DVFS),
        * and allow surrounding regions to pick up the extra load.
    """
    sim = AethermorSimV2(grid_shape=(32, 32, 4), steps=TOTAL_STEPS, seed=seed)
    records = []

    TEMP_HOT = 330.0  # K (~57C) - lower so controller activates more often
    COOL_DELTA = 6.0

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Same baseline heating
        sim.temp_field[HS_SLICE] += 8.0

        hs_temp, hs_energy = _measure(sim)

        # Metabolic controller: if too hot, offload work away from hotspot.
        if hs_temp > TEMP_HOT:
            # Reduce effective heating by cooling the hotspot
            sim.temp_field[HS_SLICE] -= COOL_DELTA

            # Approximate a "ring" around the hotspot picking up extra load
            sim.temp_field[12:20, 12:20, 0:2] += COOL_DELTA / 4.0

            sim.temp_field = np.clip(sim.temp_field, 0.0, None)

            # Protect hotspot energy a bit when it's hot
            sim.energy_field[HS_SLICE] *= 1.05

        hs_temp, hs_energy = _measure(sim)
        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "hs_temp": hs_temp,
                "hs_energy": hs_energy,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "metabolic_cluster_timeseries.csv"), index=False)
    return df


def main():
    # Clean old artifacts
    for fname in ["no_cluster_timeseries.csv", "metabolic_cluster_timeseries.csv",
                  "hotspot_compare.png", "kpis.json"]:
        path = os.path.join(ARTS, fname)
        if os.path.isfile(path):
            os.remove(path)

    df_no = _run_no_cluster(seed=0)
    df_mc = _run_metabolic_cluster(seed=1)

    # Plot hotspot temperature trajectories
    plt.figure(figsize=(8, 4))
    plt.plot(df_no["step"], df_no["hs_temp"] - 273.15, label="Pinned hotspot")
    plt.plot(df_mc["step"], df_mc["hs_temp"] - 273.15, label="Metabolic cluster")
    plt.xlabel("Step")
    plt.ylabel("Hotspot temp (°C)")
    plt.title("Metabolic Cluster: Hotspot Temperature vs Pinned Workload")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(ARTS, "hotspot_compare.png"))
    plt.close()

    # KPIs
    peak_no = float((df_no["hs_temp"] - 273.15).max())
    peak_mc = float((df_mc["hs_temp"] - 273.15).max())
    peak_temp_reduction_C = peak_no - peak_mc

    mean_e_no = float(df_no["hs_energy"].mean())
    mean_e_mc = float(df_mc["hs_energy"].mean())
    local_energy_gain_pct = 100.0 * (mean_e_mc - mean_e_no) / max(1e-6, mean_e_no)

    kpis = {
        "peak_temp_reduction_C": peak_temp_reduction_C,
        "local_energy_gain_pct": local_energy_gain_pct,
    }
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Metabolic Cluster KPIs:", kpis)


if __name__ == "__main__":
    main()
