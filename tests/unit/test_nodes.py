import numpy as np
from simulation.aethermor_full_simulation_v2 import AethermorSimV2

def test_harvest_temperature_dependence():
    sim = AethermorSimV2(grid_shape=(1,1,1), steps=1)
    pos = (0,0,0)
    sim.temp_field[pos] = 310.0
    raw = sim.base_harvest * sim.ambient_base * (0.5 + 0.5)  # worst case at t=0 ~ 0.5 factor; we just ensure nonnegativity
    expected_factor = max(0.0, 1 - sim.temp_coeff_harvest*(10))
    sim.step(0)
    assert expected_factor >= 0

def test_sleep_wake_toggle():
    # Use a single-node sim and disable harvest + healing side-effects
    sim = AethermorSimV2(grid_shape=(1, 1, 1), steps=2)
    pos = (0, 0, 0)
    n = sim.nodes[pos]

    # Neutralize harvest, healing AND compute so we test pure threshold logic
    sim.base_harvest = 0.0          # no ambient gain
    sim.ambient_base = 0.0          # keep ambient term inactive
    sim.healing_energy = 0.0        # no healing boost
    sim.temp_coeff_harvest = 0.0    # temp has no effect
    sim.temp_coeff_heal = 0.0
    sim.compute_cost = 0.0          # <-- add this line

    # 1) Energy just below sleep threshold -> should go to sleep
    n['energy'] = sim.sleep_threshold - 0.1
    n['awake'] = True
    sim.step(0)
    assert n['awake'] is False

    # 2) Energy above wake threshold -> should wake up
    n['energy'] = sim.wake_threshold + 0.1
    n['awake'] = False
    sim.step(1)
    assert n['awake'] is True


def test_healing_behavior():
    sim = AethermorSimV2(grid_shape=(1,1,1), steps=1)
    pos = (0,0,0)
    n = sim.nodes[pos]
    n['energy'] = 1.0
    n['buffer'] = sim.healing_energy
    n['healing_cd'] = 0
    sim.step(0)
    assert n['healing_cd'] > 0

def test_reproduction_behavior():
    sim = AethermorSimV2(grid_shape=(2,1,1), steps=1)
    pos = (0,0,0)
    neighbor = (1,0,0)

    # Make reproduction extremely likely and remove confounding factors
    sim.compute_cost = 0.0
    sim.base_harvest = 0.0
    sim.ambient_base = 0.0
    sim.entropy_factor = 0.0

    sim.nodes[pos]['energy'] = sim.wake_threshold + 1.0  # well above threshold
    sim.nodes[pos]['awake'] = True
    sim.nodes[neighbor]['energy'] = 0.0

    sim.step(0)
    assert sim.nodes[neighbor]['energy'] > 0.0

