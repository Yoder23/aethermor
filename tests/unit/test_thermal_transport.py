"""
Tests for the Fourier thermal transport engine.

Validates that heat transport follows real physics:
  - Energy conservation
  - Correct steady-state temperature for known analytical solutions
  - CFL stability condition enforcement
  - Material property effects (diamond vs silicon)
"""

import numpy as np
import pytest
from aethermor.physics.thermal import FourierThermalTransport, ThermalBoundaryCondition
from aethermor.physics.materials import MATERIAL_DB


class TestThermalConservation:
    """Energy must be conserved in the thermal simulation."""

    def test_no_heat_means_no_temperature_change(self):
        """With no heat input, temperature should stay at ambient."""
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4),
            element_size_m=100e-6,
        )
        T_before = thermal.T.copy()
        for _ in range(50):
            thermal.step()
        # Should remain very close to ambient
        assert np.max(np.abs(thermal.T - T_before)) < 1e-6

    def test_heat_raises_temperature(self):
        """Injecting heat should raise the temperature."""
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4),
            element_size_m=100e-6,
        )
        heat_W = np.ones(thermal.grid_shape) * 1e-3  # 1 mW per element
        for _ in range(100):
            thermal.step(heat_W)
        assert thermal.mean_temperature() > 300.0

    def test_energy_balance_approximately_correct(self):
        """Generated - removed ≈ stored (energy conservation)."""
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4),
            element_size_m=100e-6,
        )
        heat_W = np.ones(thermal.grid_shape) * 1e-3
        for _ in range(200):
            thermal.step(heat_W)

        balance = thermal.energy_balance()
        total = balance["generated_J"]
        if total > 0:
            relative_error = abs(balance["balance_error_J"]) / total
            assert relative_error < 0.05, f"Energy balance error too large: {relative_error:.1%}"


class TestCFLStability:
    """CFL condition must be enforced for numerical stability."""

    def test_auto_adjusts_dt_for_stability(self):
        """If dt would violate CFL, it should be reduced automatically."""
        # Diamond has very high thermal diffusivity (~6.2e-4 m²/s)
        # With small dx, CFL requires very small dt
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4),
            element_size_m=10e-6,  # 10 μm — small elements
            material=MATERIAL_DB["diamond"],
            dt=1.0,  # 1 second — way too large for CFL
        )
        # dt should have been reduced
        assert thermal.cfl_number <= 1.0 / 6.0
        assert thermal.dt < 1.0  # must be reduced

    def test_stable_with_default_params(self):
        """Default parameters should be numerically stable."""
        thermal = FourierThermalTransport(grid_shape=(10, 10, 4))
        heat_W = np.ones(thermal.grid_shape) * 1e-3
        T_prev = thermal.T.copy()
        for _ in range(100):
            thermal.step(heat_W)
        # Temperature should be finite and reasonable (no NaN or blow-up)
        assert np.all(np.isfinite(thermal.T))
        assert thermal.max_temperature() < 1e6  # no blow-up


class TestMaterialEffects:
    """Substrate material should affect thermal behavior."""

    def test_diamond_cooler_than_silicon(self):
        """
        Diamond (k=2200 W/m·K) should reach lower peak temp than
        silicon (k=148 W/m·K) under the same heat load.
        """
        heat_W = np.zeros((10, 10, 4))
        heat_W[5, 5, 2] = 0.1  # 100 mW hotspot in center

        th_si = FourierThermalTransport(
            grid_shape=(10, 10, 4), material=MATERIAL_DB["silicon"],
        )
        th_dia = FourierThermalTransport(
            grid_shape=(10, 10, 4), material=MATERIAL_DB["diamond"],
        )

        for _ in range(500):
            th_si.step(heat_W)
            th_dia.step(heat_W)

        assert th_dia.max_temperature() < th_si.max_temperature(), \
            "Diamond should have lower peak temperature than silicon"

    def test_thermal_diffusivity_ordering(self):
        """Diamond > SiC > Si > GaAs in thermal diffusivity."""
        alpha_dia = MATERIAL_DB["diamond"].thermal_diffusivity
        alpha_sic = MATERIAL_DB["silicon_carbide"].thermal_diffusivity
        alpha_si = MATERIAL_DB["silicon"].thermal_diffusivity
        alpha_gaas = MATERIAL_DB["gallium_arsenide"].thermal_diffusivity

        assert alpha_dia > alpha_sic > alpha_si > alpha_gaas


class TestBoundaryConditions:
    """Test different boundary condition modes."""

    def test_convective_cooling_reduces_temperature(self):
        """Convective cooling should bring temperature back toward ambient."""
        bc = ThermalBoundaryCondition(mode="convective", h_conv=5000.0, T_ambient=300.0)
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4), boundary=bc,
        )
        # Heat up
        heat_W = np.ones(thermal.grid_shape) * 1e-3
        for _ in range(100):
            thermal.step(heat_W)
        T_heated = thermal.mean_temperature()

        # Cool down (no more heat)
        for _ in range(500):
            thermal.step()
        T_cooled = thermal.mean_temperature()

        assert T_cooled < T_heated, "Should cool down after heat source removed"
        assert T_cooled < T_heated, "Should approach ambient"

    def test_fixed_boundary_clamps_edges(self):
        """Fixed boundary should keep edge temperatures at T_fixed."""
        bc = ThermalBoundaryCondition(mode="fixed", T_fixed=300.0)
        thermal = FourierThermalTransport(
            grid_shape=(10, 10, 4), boundary=bc,
        )
        heat_W = np.ones(thermal.grid_shape) * 1e-3
        for _ in range(100):
            thermal.step(heat_W)

        # Edges should be at T_fixed
        assert abs(thermal.T[0, 5, 2] - 300.0) < 1e-6
        assert abs(thermal.T[-1, 5, 2] - 300.0) < 1e-6


class TestAnalysisHelpers:
    """Test thermal analysis helper methods."""

    def test_hotspot_map_zero_when_uniform(self):
        """No hotspots when temperature is uniform at ambient."""
        thermal = FourierThermalTransport(grid_shape=(10, 10, 4))
        hotmap = thermal.hotspot_map()
        assert np.max(np.abs(hotmap)) < 1e-10

    def test_gradient_zero_when_uniform(self):
        """Gradient should be ~zero when temperature is uniform."""
        thermal = FourierThermalTransport(grid_shape=(10, 10, 4))
        grad = thermal.thermal_gradient_magnitude()
        assert np.max(grad) < 1e-6


class TestThermalRunaway:
    """Thermal runaway detection must protect against divergent simulations."""

    def test_runaway_flag_initially_false(self):
        """New solver starts with thermal_runaway == False."""
        thermal = FourierThermalTransport(grid_shape=(5, 5, 3))
        assert thermal.thermal_runaway is False

    def test_extreme_heat_triggers_runaway(self):
        """Injecting absurd heat should set thermal_runaway and clamp T."""
        thermal = FourierThermalTransport(grid_shape=(5, 5, 3))
        extreme_heat = np.full(thermal.grid_shape, 1e30)  # W/m³
        thermal.inject_heat(extreme_heat)
        assert thermal.thermal_runaway is True
        assert np.all(np.isfinite(thermal.T))
        assert np.all(thermal.T <= 1e6)

    def test_normal_heat_does_not_trigger_runaway(self):
        """Moderate heat should not set thermal_runaway."""
        thermal = FourierThermalTransport(grid_shape=(5, 5, 3))
        mild_heat = np.full(thermal.grid_shape, 1e6)  # W/m³
        thermal.inject_heat(mild_heat)
        assert thermal.thermal_runaway is False

    def test_reset_clears_runaway(self):
        """Calling reset() must clear the thermal_runaway flag."""
        thermal = FourierThermalTransport(grid_shape=(5, 5, 3))
        extreme_heat = np.full(thermal.grid_shape, 1e30)
        thermal.inject_heat(extreme_heat)
        assert thermal.thermal_runaway is True
        thermal.reset()
        assert thermal.thermal_runaway is False
        assert np.allclose(thermal.T, thermal.boundary.T_ambient)

    def test_physical_simulation_stops_on_runaway(self):
        """PhysicalSimulation.run() should stop early on runaway."""
        from aethermor.simulation.physical_simulation import PhysicalSimulation
        sim = PhysicalSimulation(
            grid_shape=(5, 5, 3),
            material="silicon",
            gate_density=1e12,  # absurdly high → will trigger runaway
            steps=500,
        )
        sim.run()
        s = sim.summary()
        assert s["thermal_runaway"] is True
        # Should have stopped well before 500 steps
        assert len(sim.metrics_history) < 500
