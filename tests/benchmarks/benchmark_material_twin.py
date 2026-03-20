# benchmark_material_twin.py
"""
Material-twin benchmark

Goal:
- Compare a passive Aethermor lattice (open-loop) to a simple
  closed-loop "material twin" controller that watches a damaged
  region (ROI) and actively pushes energy back into it.

Outputs:
- artifacts/material_twin/open_loop_timeseries.csv
- artifacts/material_twin/closed_loop_timeseries.csv
- artifacts/material_twin/roi_recovery.png
- artifacts/material_twin/kpis.json
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from aethermor_full_simulation_v2 import AethermorSimV2

ARTS = "artifacts/material_twin"
os.makedirs(ARTS, exist_ok=True)

TOTAL_STEPS = 80
FAULT_STEP = 30

# ROI: a small cube near the center
ROI_SLICE = (slice(10, 20), slice(10, 20), slice(0, 2))


def _measure(sim):
    roi = sim.energy_field[ROI_SLICE]
    roi_mean = float(roi.mean())
    global_mean = float(sim.energy_field.mean())
    return roi_mean, global_mean


def _run_open_loop(seed: int = 0):
    """Passive recovery: no twin, only natural diffusion + healing."""
    sim = AethermorSimV2(grid_shape=(32, 32, 4), steps=TOTAL_STEPS, seed=seed)
    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # At FAULT_STEP, simulate a crack / damage in the ROI
        if t == FAULT_STEP:
            sim.energy_field[ROI_SLICE] *= 0.1
            # Also drain node energies in ROI
            for (x, y, z), node in sim.nodes.items():
                if 10 <= x < 20 and 10 <= y < 20 and z < 2:
                    node["energy"] *= 0.1
                    node["buffer"] *= 0.1

        roi_mean, global_mean = _measure(sim)
        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "roi_mean_energy": roi_mean,
                "global_mean_energy": global_mean,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "open_loop_timeseries.csv"), index=False)
    return df


def _run_closed_loop(seed: int = 1):
    """
    Closed-loop twin:
    - Observes ROI vs global energy every step.
    - If ROI lags far behind, injects energy from the rest of the lattice
      into the ROI (as if commanding actuators to heal the crack).
    """
    sim = AethermorSimV2(grid_shape=(32, 32, 4), steps=TOTAL_STEPS, seed=seed)
    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        if t == FAULT_STEP:
            sim.energy_field[ROI_SLICE] *= 0.1
            for (x, y, z), node in sim.nodes.items():
                if 10 <= x < 20 and 10 <= y < 20 and z < 2:
                    node["energy"] *= 0.1
                    node["buffer"] *= 0.1

        roi_mean, global_mean = _measure(sim)

        # Twin controller: if ROI energy is less than 80% of global,
        # move some energy from outside ROI into ROI.
        if roi_mean < 0.8 * global_mean:
            outside_mask = np.ones(sim.grid_shape, dtype=bool)
            outside_mask[ROI_SLICE] = False

            # Take a stronger fraction of energy from outside and push to ROI
            fraction = 0.10
            donation = sim.energy_field[outside_mask] * fraction
            total_donation = float(donation.sum())

            sim.energy_field[outside_mask] *= (1.0 - fraction)
            sim.energy_field[ROI_SLICE] += total_donation / max(1, sim.energy_field[ROI_SLICE].size)

            # Directly boost node energies in ROI as if actuators are present
            for (x, y, z), node in sim.nodes.items():
                if 10 <= x < 20 and 10 <= y < 20 and z < 2:
                    node["energy"] *= 1.05

            sim.energy_field = np.clip(sim.energy_field, 0.0, None)

        # Measure after control
        roi_mean, global_mean = _measure(sim)
        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "roi_mean_energy": roi_mean,
                "global_mean_energy": global_mean,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "closed_loop_timeseries.csv"), index=False)
    return df


def main():
    # Clean old artifacts
    for fname in ["open_loop_timeseries.csv", "closed_loop_timeseries.csv",
                  "roi_recovery.png", "kpis.json"]:
        path = os.path.join(ARTS, fname)
        if os.path.isfile(path):
            os.remove(path)

    df_open = _run_open_loop(seed=0)
    df_closed = _run_closed_loop(seed=1)

    # Plot ROI recovery trajectories
    plt.figure(figsize=(8, 4))
    plt.plot(df_open["step"], df_open["roi_mean_energy"], label="Open-loop (passive)")
    plt.plot(df_closed["step"], df_closed["roi_mean_energy"], label="Closed-loop twin")
    plt.axvline(FAULT_STEP, color="red", linestyle=":", alpha=0.5)
    plt.xlabel("Step")
    plt.ylabel("ROI mean energy")
    plt.title("Material Twin: ROI Recovery vs Passive")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(ARTS, "roi_recovery.png"))
    plt.close()

    # KPIs: compare ROI recovery over the second half of the run
    tail = slice(TOTAL_STEPS // 2, None)
    roi_open = float(df_open["roi_mean_energy"].iloc[tail].mean())
    roi_closed = float(df_closed["roi_mean_energy"].iloc[tail].mean())
    roi_recovery_gain_pct = 100.0 * (roi_closed - roi_open) / max(1e-6, roi_open)

    kpis = {
        "roi_recovery_gain_pct": roi_recovery_gain_pct,
    }
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Material Twin KPIs:", kpis)


if __name__ == "__main__":
    main()
