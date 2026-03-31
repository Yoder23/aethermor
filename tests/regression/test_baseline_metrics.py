import json
from aethermor.simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_baseline_metrics_consistency():
    sim = AethermorSimV2(grid_shape=(10,10,2), steps=20)
    sim.run()
    with open('data/golden_metrics.json') as f:
        golden = json.load(f)
    diffs = [abs(m['avg_energy'] - g['avg_energy']) for m, g in zip(sim.metrics, golden)]
    assert max(diffs) < 1e-6
