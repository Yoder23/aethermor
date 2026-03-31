from aethermor.simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_neighbor_generation_edges():
    sim = AethermorSimV2(grid_shape=(2,2,2), steps=1)
    neighbors = list(sim.neighbors((0,0,0)))
    assert (1,0,0) in neighbors
    assert (0,1,0) in neighbors
    assert (0,0,1) in neighbors
