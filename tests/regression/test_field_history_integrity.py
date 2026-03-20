from aethermor_full_simulation_v2 import AethermorSimV2

def test_field_history_integrity():
    sim = AethermorSimV2(grid_shape=(4,4,2), steps=5)
    sim.run()
    assert sim.energy_field_history[0].shape == (4,4,2)
    assert sim.energy_field_history[-1].shape == (4,4,2)
