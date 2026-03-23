from simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_full_simulation_run():
    sim = AethermorSimV2(grid_shape=(5,5,3), steps=10)
    sim.run()
    assert len(sim.energy_field_history) == 10
    assert len(sim.metrics) == 10
    for m in sim.metrics:
        assert 'step' in m and 'alive' in m and 'avg_energy' in m and 'total_knowledge' in m
