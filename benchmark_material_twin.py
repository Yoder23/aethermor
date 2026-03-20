# benchmark_material_twin.py
"""
Material-twin benchmark

Goal:
- Compare a passive Aethermor lattice (open-loop) to a simple
  closed-loop "material twin" controller that watches a damaged
  region (ROI) and actively pushes energy back into it using the
  built-in material twin hooks (faulted, repair_priority, actuation_field).

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

ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
ARTS = os.path.join(ART_ROOT, "material_twin")
os.makedirs(ARTS, exist_ok=True)

TOTAL_STEPS = int(os.getenv("BENCH_STEPS", "80"))
GRID_N = int(os.getenv("BENCH_GRID", "32"))
GRID_SHAPE = (GRID_N, GRID_N, 4)
FAULT_MULT = float(np.clip(float(os.getenv("FAULT_SEVERITY", "0.3")), 0.0, 1.0))

def _scenario(seed: int):
    """
    Build deterministic-but-seed-varying ROI and fault timing.
    """
    rng = np.random.default_rng(seed)
    roi_half = max(2, GRID_N // 8)
    jitter = max(1, GRID_N // 10)
    cx = int(np.clip((GRID_N // 2) + rng.integers(-jitter, jitter + 1), roi_half, GRID_N - roi_half))
    cy = int(np.clip((GRID_N // 2) + rng.integers(-jitter, jitter + 1), roi_half, GRID_N - roi_half))
    roi_slice = (
        slice(max(0, cx - roi_half), min(GRID_N, cx + roi_half)),
        slice(max(0, cy - roi_half), min(GRID_N, cy + roi_half)),
        slice(0, 2),
    )
    fault_step = max(5, min(TOTAL_STEPS - 5, int(0.4 * TOTAL_STEPS) + int(rng.integers(-2, 3))))
    return roi_slice, fault_step

def _read_twin_enable_flag():
    """Check if material twin is disabled via env var."""
    return os.getenv("TWIN_ENABLE", "1") != "0"


def _measure(sim, roi_slice):
    roi = sim.energy_field[roi_slice]
    roi_mean = float(roi.mean())
    global_mean = float(sim.energy_field.mean())
    return roi_mean, global_mean


def _run_open_loop(seed: int, roi_slice, fault_step: int) -> pd.DataFrame:
    """Passive recovery: no twin, only natural diffusion + healing."""
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)
    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        if t == fault_step:
            # Simulate crack/damage in ROI
            sim.energy_field[roi_slice] *= FAULT_MULT

        roi_mean, global_mean = _measure(sim, roi_slice)
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


def _run_closed_loop(seed: int, roi_slice, fault_step: int, twin_enabled: bool = True) -> pd.DataFrame:
    """
    Closed-loop twin:
    - At FAULT_STEP, mark ROI nodes as faulted.
    - After fault, if ROI lags behind global, increase repair_priority.
    - The sim's internal _material_healing_boost uses these to inject
      extra energy and actuation into the ROI.
    - If twin_enabled=False, skip the twin controller logic.
    """
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)
    records = []

    # Precompute which node positions lie inside ROI
    roi_positions = []
    for (x, y, z), node in sim.nodes.items():
        if (roi_slice[0].start <= x < roi_slice[0].stop and
            roi_slice[1].start <= y < roi_slice[1].stop and
            roi_slice[2].start <= z < roi_slice[2].stop):
            roi_positions.append((x, y, z))

    for t in range(TOTAL_STEPS):
        sim.step(t)

        if t == fault_step:
            sim.energy_field[roi_slice] *= FAULT_MULT
            # Mark ROI nodes as faulted once the crack appears
            for pos in roi_positions:
                sim.nodes[pos]["faulted"] = True
                sim.nodes[pos]["repair_priority"] = 0.0

        roi_mean, global_mean = _measure(sim, roi_slice)

        # Twin controller: ONLY runs if enabled
        if twin_enabled and t >= fault_step:
            if roi_mean < 0.8 * global_mean:
                boost = min(1.0, (global_mean - roi_mean) / max(1e-6, global_mean))
                for pos in roi_positions:
                    node = sim.nodes[pos]
                    node["faulted"] = True
                    # Gradually ramp repair priority; bounded for stability
                    node["repair_priority"] = min(1.0, node.get("repair_priority", 0.0) + 0.1 * boost)

        # After controller updates, we measure again (effect shows in next step)
        roi_mean, global_mean = _measure(sim, roi_slice)
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
    def _safe_remove(path: str):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            # Keep benchmark running if previous artifacts are locked.
            pass

    # Clean old artifacts
    for fname in [
        "open_loop_timeseries.csv",
        "closed_loop_timeseries.csv",
        "roi_recovery.png",
        "kpis.json",
    ]:
        path = os.path.join(ARTS, fname)
        _safe_remove(path)

    twin_enabled = _read_twin_enable_flag()
    base_seed = int(os.getenv("AETHERMOR_SEED", "0"))
    roi_slice, fault_step = _scenario(base_seed)
    print(f"[MATERIAL-TWIN] Twin Enabled: {twin_enabled}")
    
    df_open = _run_open_loop(seed=base_seed, roi_slice=roi_slice, fault_step=fault_step)
    df_closed = _run_closed_loop(
        seed=base_seed,
        roi_slice=roi_slice,
        fault_step=fault_step,
        twin_enabled=twin_enabled,
    )

    # Plot ROI recovery trajectories
    plt.figure(figsize=(8, 4))
    plt.plot(df_open["step"], df_open["roi_mean_energy"], label="Open-loop (passive)")
    plt.plot(df_closed["step"], df_closed["roi_mean_energy"], label="Closed-loop twin")
    plt.axvline(fault_step, color="red", linestyle=":", alpha=0.5)
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
    roi_recovery_gain_pct = float(100.0 * (roi_closed - roi_open) / max(1e-6, roi_open))
    
    energy_open = df_open["avg_energy"].to_numpy(dtype=float)
    energy_closed = df_closed["avg_energy"].to_numpy(dtype=float)
    energy_bounded_open = int(np.isfinite(energy_open).all() and np.max(np.abs(energy_open)) < 1e6)
    energy_bounded_closed = int(np.isfinite(energy_closed).all() and np.max(np.abs(energy_closed)) < 1e6)

    kpis = {
        "roi_recovery_gain_pct": float(roi_recovery_gain_pct),
        "roi_recovery_delta": float(roi_closed - roi_open),
        "energy_bounded_open_loop": int(energy_bounded_open),
        "energy_bounded_closed_loop": int(energy_bounded_closed),
        "roi_open_tail_mean": float(roi_open),
        "roi_closed_tail_mean": float(roi_closed),
    }
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Material Twin KPIs:", kpis)


if __name__ == "__main__":
    main()
