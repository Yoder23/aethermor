import json
import uuid
from aethermor.simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_param_loading_defaults():
    sim = AethermorSimV2(grid_shape=(1,1,1), steps=1, calibrated_params_file="nonexistent.json")
    assert sim.base_harvest == 1.0

def test_param_loading_valid():
    param_file = f"params_test_{uuid.uuid4().hex}.json"
    with open(param_file, 'w') as f:
        json.dump({"base_harvest": 1.23}, f)
    sim = AethermorSimV2(grid_shape=(1,1,1), steps=1, calibrated_params_file=str(param_file))
    assert sim.base_harvest == 1.23
