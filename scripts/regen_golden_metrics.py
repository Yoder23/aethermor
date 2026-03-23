# regen_golden_metrics.py
"""
Regenerate golden_metrics.json for the current AethermorSimV2.

This is used by tests/regression/test_baseline_metrics.py to ensure
that changes to the core simulation are intentional and tracked.

Run once after updating AethermorSimV2:

    python regen_golden_metrics.py
"""

import os
import json
from simulation.aethermor_full_simulation_v2 import AethermorSimV2

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
GOLDEN_PATH = os.path.join(DATA_DIR, "golden_metrics.json")


def main():
    # Use the same configuration as the regression test
    sim = AethermorSimV2(grid_shape=(10, 10, 2), steps=20, seed=123)
    sim.run()

    # Only keep fields the tests actually care about (and a few extras)
    golden = []
    for m in sim.metrics:
        golden.append(
            {
                "step": m["step"],
                "alive": m["alive"],
                "avg_energy": m["avg_energy"],
                "total_knowledge": m["total_knowledge"],
            }
        )

    with open(GOLDEN_PATH, "w") as f:
        json.dump(golden, f, indent=2)
    print(f"Regenerated {GOLDEN_PATH} with {len(golden)} entries.")


if __name__ == "__main__":
    main()
