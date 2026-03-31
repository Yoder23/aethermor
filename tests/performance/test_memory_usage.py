import psutil, os
from aethermor.simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_memory_usage():
    process = psutil.Process(os.getpid())
    sim = AethermorSimV2(grid_shape=(60,60,10), steps=3)
    sim.run()
    mem_mb = process.memory_info().rss / (1024**2)
    assert mem_mb < 1000
