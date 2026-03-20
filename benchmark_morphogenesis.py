# benchmark_morphogenesis.py
"""
Morphogenesis benchmark (tuned)

Goal:
- Compare a "plain" AethermorSimV2 lattice under repeated localized faults
  to a version with:
    * coarse-grained module specialization (left=energy, right=compute)
    * a simple morphogenesis-inspired + healing controller that:
        - reallocates energy between modules when one is weak
        - marks a damaged ROI as faulted and raises its repair_priority
          so AethermorSimV2's material-twin hooks boost it.

Outputs:
- artifacts/morphogenesis/baseline_timeseries.csv
- artifacts/morphogenesis/morphogenesis_timeseries.csv
- artifacts/morphogenesis/resilience_compare.png
- artifacts/morphogenesis/kpis.json
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from aethermor_full_simulation_v2 import AethermorSimV2

ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
ARTS = os.path.join(ART_ROOT, "morphogenesis")
os.makedirs(ARTS, exist_ok=True)

def _read_morpho_enable_flag():
    """Check if morphogenesis is disabled via env var."""
    return os.getenv("MORPHO_ENABLE", "1") != "0"

GRID_N = int(os.getenv("BENCH_GRID", "40"))
GRID_SHAPE = (GRID_N, GRID_N, 4)
TOTAL_STEPS = int(os.getenv("BENCH_STEPS", "100"))
FAULT_MULT = float(np.clip(float(os.getenv("FAULT_SEVERITY", "0.4")), 0.0, 1.0))
FAULT_COUNT = max(1, int(os.getenv("FAULT_COUNT", "3")))


def _fault_steps(total_steps: int, fault_count: int):
    start = max(5, total_steps // 3)
    end = max(start + 1, total_steps - 5)
    return sorted(set(np.linspace(start, end, num=fault_count, dtype=int).tolist()))


FAULT_STEPS = _fault_steps(TOTAL_STEPS, FAULT_COUNT)

# ROI for damage inside the left module
roi_start = max(1, GRID_N // 8)
roi_stop = max(roi_start + 2, GRID_N // 2)
ROI_X = slice(roi_start, roi_stop)
ROI_Y = slice(roi_start, roi_stop)
ROI_Z = slice(0, min(3, GRID_SHAPE[2]))


def _roi_mask(sim):
    mask = np.zeros(sim.grid_shape, dtype=bool)
    mask[ROI_X, ROI_Y, ROI_Z] = True
    return mask


def _run_baseline(seed: int = 0):
    """Run Aethermor with no external controller; only built-in dynamics."""
    seed = int(os.getenv("AETHERMOR_SEED", seed))
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)

    records = []
    X, Y, Z = sim.grid_shape
    mid_x = X // 2

    roi_mask = _roi_mask(sim)

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Inject localized faults into the left half at specified steps
        if t in FAULT_STEPS:
            sim.energy_field[roi_mask] *= FAULT_MULT

        # Coarse modules: A (left) and B (right)
        modA_mask = np.zeros(sim.grid_shape, dtype=bool)
        modA_mask[:mid_x, :, :] = True
        modB_mask = ~modA_mask

        eA = float(sim.energy_field[modA_mask].mean())
        eB = float(sim.energy_field[modB_mask].mean())

        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "modA_mean_energy": eA,
                "modB_mean_energy": eB,
                # no explicit specialization controller in baseline
                "module_gini": 0.0,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "baseline_timeseries.csv"), index=False)
    return df


def _gini_two(p_a: float, p_b: float) -> float:
    vals = np.array([max(p_a, 0.0), max(p_b, 0.0)], dtype=float)
    if vals.sum() <= 0:
        return 0.0
    mean = vals.mean()
    return 0.5 * abs(vals[0] - vals[1]) / mean


def _run_morphogenesis(seed: int = 1, morpho_enabled: bool = True):
    """
    Morphogenesis + healing controller:

    - Specialize roles spatially:
        * left half: 'energy' nodes
        * right half: 'compute' nodes
    - On each step:
        * respond to the same faults as baseline
        * if a module is too weak vs the other, shift some energy
        * mark the damaged ROI as faulted and increase repair_priority
          over time so the sim's internal material-twin hook aids recovery
    """
    seed = int(os.getenv("AETHERMOR_SEED", seed))
    sim = AethermorSimV2(grid_shape=GRID_SHAPE, steps=TOTAL_STEPS, seed=seed)

    X, Y, Z = sim.grid_shape
    mid_x = X // 2
    roi_mask = _roi_mask(sim)

    if morpho_enabled:
        # Hard specialization: left = energy, right = compute
        for (x, y, z), node in sim.nodes.items():
            if x < mid_x:
                node["role"] = "energy"
            else:
                node["role"] = "compute"

        # Pre-mark ROI nodes as "faultable" so healing hook can act post-damage
        for (x, y, z), node in sim.nodes.items():
            if roi_mask[x, y, z]:
                node["faulted"] = False
                node["repair_priority"] = 0.0

    records = []

    for t in range(TOTAL_STEPS):
        sim.step(t)

        # Same faults as baseline
        if t in FAULT_STEPS:
            sim.energy_field[roi_mask] *= FAULT_MULT
            # When a fault occurs, mark ROI nodes as damaged
            if morpho_enabled:
                for (x, y, z), node in sim.nodes.items():
                    if roi_mask[x, y, z]:
                        node["faulted"] = True

        # After each fault, ramp up repair_priority in ROI gradually
        if morpho_enabled and t > FAULT_STEPS[0]:
            for (x, y, z), node in sim.nodes.items():
                if roi_mask[x, y, z] and node.get("faulted", False):
                    node["repair_priority"] = min(
                        1.0, node.get("repair_priority", 0.0) + 0.05
                    )

        # Coarse modules
        modA_mask = np.zeros(sim.grid_shape, dtype=bool)
        modA_mask[:mid_x, :, :] = True
        modB_mask = ~modA_mask

        eA = float(sim.energy_field[modA_mask].mean())
        eB = float(sim.energy_field[modB_mask].mean())

        # Morphogenesis-style module rebalancing:
        # if one side is significantly weaker, move some energy across.
        diff = eA - eB
        mean_e = max(1.0, 0.5 * (eA + eB))
        if morpho_enabled and abs(diff) > 0.15 * mean_e:
            frac = 0.08  # smaller fraction to avoid over-damping
            if diff < 0:  # A weaker than B -> move from B to A
                delta = frac * (eB - eA)
                sim.energy_field[modB_mask] *= (1.0 - frac)
                sim.energy_field[modA_mask] += delta
            else:  # B weaker than A
                delta = frac * (eA - eB)
                sim.energy_field[modA_mask] *= (1.0 - frac)
                sim.energy_field[modB_mask] += delta
            sim.energy_field = np.clip(sim.energy_field, 0.0, None)

        # Specialization score = gini of "compute" role distribution in the two modules
        if morpho_enabled:
            totalA = totalB = 0
            compA = compB = 0
            for (x, y, z), node in sim.nodes.items():
                if x < mid_x:
                    totalA += 1
                    if node["role"] == "compute":
                        compA += 1
                else:
                    totalB += 1
                    if node["role"] == "compute":
                        compB += 1
            pA = compA / max(1, totalA)
            pB = compB / max(1, totalB)
            module_gini = _gini_two(pA, pB)
        else:
            module_gini = 0.0

        m = sim.metrics[-1]
        records.append(
            {
                "step": t,
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
                "modA_mean_energy": eA,
                "modB_mean_energy": eB,
                "module_gini": module_gini,
            }
        )

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(ARTS, "morphogenesis_timeseries.csv"), index=False)
    return df


def main():
    def _safe_remove(path: str):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            # Keep benchmark running if previous artifacts are locked.
            pass

    # Clean any old artifacts
    for fname in [
        "baseline_timeseries.csv",
        "morphogenesis_timeseries.csv",
        "resilience_compare.png",
        "kpis.json",
    ]:
        path = os.path.join(ARTS, fname)
        _safe_remove(path)

    morpho_enabled = _read_morpho_enable_flag()
    print(f"[MORPHOGENESIS] Morpho Enabled: {morpho_enabled}")
    
    df_base = _run_baseline(seed=0)
    df_morph = _run_morphogenesis(seed=1, morpho_enabled=morpho_enabled)

    # Plot alive nodes under repeated faults
    plt.figure(figsize=(8, 4))
    plt.plot(df_base["step"], df_base["alive"], label="Baseline (no morph)", linestyle="--")
    plt.plot(df_morph["step"], df_morph["alive"], label="Morphogenesis + healing")
    for fs in FAULT_STEPS:
        plt.axvline(fs, color="red", alpha=0.25, linestyle=":")
    plt.xlabel("Step")
    plt.ylabel("Alive nodes")
    plt.title("Morphogenesis vs Baseline under Repeated Faults")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(ARTS, "resilience_compare.png"))
    plt.close()

    # --- KPIs with Energy Balance Validation ---------------------------------
    
    # Use full-run average alive nodes (AUC-style uptime proxy).
    uptime_base = float(df_base["alive"].mean())
    uptime_morph = float(df_morph["alive"].mean())
    total_nodes = float(np.prod(GRID_SHAPE))
    uptime_gain_nodes = float(uptime_morph - uptime_base)
    # Normalize by population to avoid inflated percentages when baseline is tiny.
    uptime_gain_pct = float(100.0 * uptime_gain_nodes / max(1.0, total_nodes))

    spec_base = float(df_base["module_gini"].mean())
    spec_morph = float(df_morph["module_gini"].mean())
    specialization_gain = float(max(0.0, spec_morph - spec_base))

    modules_mean_with_morph = float(2.0)  # two coarse modules A/B by design
    
    # Boundedness checks (open system, so strict conservation is not expected)
    energy_base = df_base["avg_energy"].to_numpy(dtype=float)
    energy_morph = df_morph["avg_energy"].to_numpy(dtype=float)
    energy_bounded_baseline = int(np.isfinite(energy_base).all() and np.max(np.abs(energy_base)) < 1e6)
    energy_bounded_morphogenesis = int(np.isfinite(energy_morph).all() and np.max(np.abs(energy_morph)) < 1e6)

    kpis = {
        "uptime_gain_pct": float(uptime_gain_pct),
        "uptime_gain_nodes": float(uptime_gain_nodes),
        "specialization_gain": float(specialization_gain),
        "modules_mean_with_morph": float(modules_mean_with_morph),
        "energy_bounded_baseline": int(energy_bounded_baseline),
        "energy_bounded_morphogenesis": int(energy_bounded_morphogenesis),
        "mean_alive_baseline": float(uptime_base),
        "mean_alive_morphogenesis": float(uptime_morph),
    }
    with open(os.path.join(ARTS, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)
    print("Morphogenesis KPIs:", kpis)


if __name__ == "__main__":
    main()
