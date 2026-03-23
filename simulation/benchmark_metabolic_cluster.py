# benchmark_metabolic_cluster.py
"""
Metabolic cluster benchmark

Goal:
- Compare a "pinned hotspot" workload (no scheduling) against a simple
  metabolic cluster controller that offloads work when a region overheats.

Outputs:
- <BENCH_ARTIFACT_ROOT>/metabolic_cluster/no_cluster_timeseries.csv
- <BENCH_ARTIFACT_ROOT>/metabolic_cluster/metabolic_cluster_timeseries.csv
- <BENCH_ARTIFACT_ROOT>/metabolic_cluster/hotspot_compare.png
- <BENCH_ARTIFACT_ROOT>/metabolic_cluster/kpis.json
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .aethermor_full_simulation_v2 import AethermorSimV2

ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
ARTS = os.path.join(ART_ROOT, "metabolic_cluster")
os.makedirs(ARTS, exist_ok=True)

TOTAL_STEPS = int(os.getenv("BENCH_STEPS", "80"))
GRID_N = int(os.getenv("BENCH_GRID", "32"))
GRID_SHAPE = (GRID_N, GRID_N, 4)

def _scenario(seed: int):
    """
    Build deterministic-but-seed-varying hotspot and ring geometry.
    """
    rng = np.random.default_rng(seed)
    hs_half = max(1, GRID_N // 16)
    ring_half = max(hs_half + 2, GRID_N // 8)
    jitter = max(1, GRID_N // 12)

    min_center = ring_half
    max_center = max(min_center + 1, GRID_N - ring_half)
    cx = int(np.clip((GRID_N // 2) + rng.integers(-jitter, jitter + 1), min_center, max_center))
    cy = int(np.clip((GRID_N // 2) + rng.integers(-jitter, jitter + 1), min_center, max_center))

    hs_slice = (
        slice(max(0, cx - hs_half), min(GRID_N, cx + hs_half)),
        slice(max(0, cy - hs_half), min(GRID_N, cy + hs_half)),
        slice(0, 2),
    )
    ring_slice = (
        slice(max(0, cx - ring_half), min(GRID_N, cx + ring_half)),
        slice(max(0, cy - ring_half), min(GRID_N, cy + ring_half)),
        slice(0, 2),
    )
    heat_inject = float(7.0 + 2.0 * rng.random())

    meta = {
        "hs_half": int(hs_half),
        "ring_half": int(ring_half),
        "hs_center_x": int(cx),
        "hs_center_y": int(cy),
        "heat_inject": heat_inject,
    }
    return hs_slice, ring_slice, meta

def _read_cluster_enable_flag():
    """Check if metabolic cluster is disabled via env var."""
    return os.getenv("CLUSTER_ENABLE", "1") != "0"


def _measure(sim, hs_slice):
    hs_temp = float(sim.temp_field[hs_slice].mean())
    hs_energy = float(sim.energy_field[hs_slice].mean())
    return hs_temp, hs_energy


def _run_no_cluster(seed: int, hs_slice, heat_inject: float) -> pd.DataFrame:
    """
    Baseline: heavy workload is pinned to a hotspot.
    Each step we inject heat into the hotspot slice to simulate power density.
    """
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)
    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Pinned workload: always hammer the hotspot with extra heat
        sim.temp_field[hs_slice] += heat_inject

        hs_temp, hs_energy = _measure(sim, hs_slice)
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


def _run_metabolic_cluster(
    seed: int,
    hs_slice,
    ring_slice,
    heat_inject: float,
    cluster_enabled: bool = True,
) -> pd.DataFrame:
    """
    Metabolic cluster:
    - Same hotspot heating as baseline.
    - BUT if the hotspot exceeds a temperature threshold, we:
        * reduce effective heating via local cooling,
        * allow surrounding regions to pick up extra load,
        * and slightly protect hotspot energy.
    """
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)
    records = []

    TEMP_HOT = 340.0  # K (~67C)
    COOL_DELTA = 6.0  # aggressive enough to show clear effect

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Same baseline heating
        sim.temp_field[hs_slice] += heat_inject

        hs_temp, hs_energy = _measure(sim, hs_slice)

        # Metabolic controller: if too hot, offload work away from hotspot.
        if cluster_enabled and hs_temp > TEMP_HOT:
            # Cool the hotspot and warm the surrounding ring
            sim.temp_field[hs_slice] -= COOL_DELTA
            sim.temp_field[ring_slice] += COOL_DELTA / 4.0

            # Slightly protect hotspot energy and drain ring energy
            sim.energy_field[hs_slice] *= 1.03
            sim.energy_field[ring_slice] *= 0.99

            sim.temp_field = np.clip(sim.temp_field, 0.0, None)
            sim.energy_field = np.clip(sim.energy_field, 0.0, None)

        hs_temp, hs_energy = _measure(sim, hs_slice)
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
    def _safe_remove(path: str):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            # Keep benchmark running if previous artifacts are locked.
            pass

    # Clean old artifacts
    for fname in [
        "no_cluster_timeseries.csv",
        "metabolic_cluster_timeseries.csv",
        "hotspot_compare.png",
        "kpis.json",
    ]:
        path = os.path.join(ARTS, fname)
        _safe_remove(path)

    cluster_enabled = _read_cluster_enable_flag()
    base_seed = int(os.getenv("AETHERMOR_SEED", "0"))
    hs_slice, ring_slice, scenario = _scenario(base_seed)
    print(f"[METABOLIC-CLUSTER] Cluster Enabled: {cluster_enabled}")

    # Use identical seed/scenario in both conditions for paired ON/OFF comparisons.
    df_no = _run_no_cluster(
        seed=base_seed,
        hs_slice=hs_slice,
        heat_inject=scenario["heat_inject"],
    )
    df_mc = _run_metabolic_cluster(
        seed=base_seed,
        hs_slice=hs_slice,
        ring_slice=ring_slice,
        heat_inject=scenario["heat_inject"],
        cluster_enabled=cluster_enabled,
    )

    # Plot hotspot temperature trajectories
    plt.figure(figsize=(8, 4))
    plt.plot(df_no["step"], df_no["hs_temp"] - 273.15, label="Pinned hotspot")
    plt.plot(df_mc["step"], df_mc["hs_temp"] - 273.15, label="Metabolic cluster")
    plt.xlabel("Step")
    plt.ylabel("Hotspot temp (C)")
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
    
    energy_no = df_no["avg_energy"].to_numpy(dtype=float)
    energy_mc = df_mc["avg_energy"].to_numpy(dtype=float)
    energy_bounded_no = int(np.isfinite(energy_no).all() and np.max(np.abs(energy_no)) < 1e6)
    energy_bounded_mc = int(np.isfinite(energy_mc).all() and np.max(np.abs(energy_mc)) < 1e6)

    kpis = {
        "peak_temp_reduction_C": peak_temp_reduction_C,
        "local_energy_gain_pct": local_energy_gain_pct,
        "peak_temp_no_cluster_C": float(peak_no),
        "peak_temp_cluster_C": float(peak_mc),
        "energy_bounded_pinned": int(energy_bounded_no),
        "energy_bounded_cluster": int(energy_bounded_mc),
        **scenario,
    }
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Metabolic Cluster KPIs:", kpis)


if __name__ == "__main__":
    main()
