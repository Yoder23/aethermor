import numpy as np
from scipy.ndimage import convolve
from aethermor_full_simulation_v2 import AethermorSimV2

def test_field_diffusion_and_decay():
    sim = AethermorSimV2(grid_shape=(3,3,3), steps=1)
    sim.energy_field[:] = 0
    sim.energy_field[1,1,1] = 10
    before = sim.energy_field.copy()
    expected = before + convolve(before, sim.laplacian, mode='constant')*0.1
    expected = np.clip(expected * (1 - sim.entropy_factor), 0.0, None)
    sim.step(0)
    np.testing.assert_allclose(sim.energy_field, expected, rtol=1e-5)

def test_entropy_factor_removal():
    sim = AethermorSimV2(grid_shape=(2,2,2), steps=1)
    sim.energy_field[:] = 5.0
    sim.energy_field = np.clip(sim.energy_field * (1 - sim.entropy_factor), 0.0, None)
    np.testing.assert_allclose(sim.energy_field, np.ones((2,2,2))*5.0*(1 - sim.entropy_factor))
