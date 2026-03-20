import time
from aethermor_full_simulation_v2 import AethermorSimV2

def test_runtime_scaling():
    sim = AethermorSimV2(grid_shape=(60,60,10), steps=5)
    start = time.time()
    sim.run()
    elapsed = time.time() - start
    assert elapsed < 5.0
