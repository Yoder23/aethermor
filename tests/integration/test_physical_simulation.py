"""
Integration test for the physically-grounded simulation.

Validates that PhysicalSimulation produces physically meaningful results
when combining the physics package, thermal transport, and energy models.
"""

import numpy as np
import pytest
from simulation.physical_simulation import PhysicalSimulation, PhysicalSimConfig


class TestPhysicalSimulationBasic:
    """Basic correctness tests for the physical simulation."""

    def test_runs_without_error(self):
        """Simulation should complete without exceptions."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=20,
            tech_node_nm=7,
        )
        sim.run()
        assert len(sim.metrics_history) == 20

    def test_temperature_increases_from_computing(self):
        """Computing should generate heat and raise temperature."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=50,
            gate_density=1e5,
            frequency_Hz=1e9,
        )
        sim.run()
        last = sim.metrics_history[-1]
        assert last["T_mean_K"] > 300.0, "Computing should raise temperature"

    def test_energy_is_positive(self):
        """Total energy should be positive after running."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=20,
        )
        sim.run()
        assert sim.total_energy_J > 0

    def test_landauer_gap_above_1(self):
        """Landauer gap should be > 1 for any physical system."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=20,
        )
        sim.run()
        last = sim.metrics_history[-1]
        assert last["landauer_gap"] > 1.0

    def test_summary_contains_key_fields(self):
        """Summary should have all fields researchers need."""
        sim = PhysicalSimulation(grid_shape=(10, 10, 4), steps=10)
        sim.run()
        s = sim.summary()

        required = [
            "material", "tech_node_nm", "frequency_GHz",
            "T_max_K", "T_mean_K", "landauer_gap",
            "energy_per_gate_switch_J", "landauer_limit_J",
            "total_power_W", "power_density_W_cm2",
        ]
        for key in required:
            assert key in s, f"Missing key in summary: {key}"


class TestMaterialComparison:
    """Test that material choice affects thermal behavior correctly."""

    def test_diamond_runs_cooler(self):
        """Diamond substrate should produce lower peak temperature."""
        cfg_base = dict(grid_shape=(10, 10, 4), steps=50,
                        gate_density=1e5, frequency_Hz=1e9)

        sim_si = PhysicalSimulation(material="silicon", **cfg_base)
        sim_dia = PhysicalSimulation(material="diamond", **cfg_base)

        sim_si.run()
        sim_dia.run()

        T_max_si = sim_si.metrics_history[-1]["T_max_K"]
        T_max_dia = sim_dia.metrics_history[-1]["T_max_K"]

        assert T_max_dia < T_max_si, \
            "Diamond should run cooler than silicon"


class TestParadigmComparison:
    """Test that energy paradigm affects results correctly."""

    def test_adiabatic_uses_less_energy_at_low_freq(self):
        """Adiabatic logic should use less energy at low frequencies."""
        cfg_base = dict(grid_shape=(10, 10, 4), steps=20,
                        frequency_Hz=1e8)  # 100 MHz (low)

        sim_cmos = PhysicalSimulation(energy_paradigm="cmos", **cfg_base)
        sim_adiab = PhysicalSimulation(energy_paradigm="adiabatic", **cfg_base)

        sim_cmos.run()
        sim_adiab.run()

        E_cmos = sim_cmos.total_energy_J
        E_adiab = sim_adiab.total_energy_J

        assert E_adiab < E_cmos, \
            "Adiabatic should use less energy at low frequency"


class TestFaultInjection:
    """Test temperature-dependent fault injection."""

    def test_faults_accumulate(self):
        """With fault injection enabled, faults should accumulate."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=100,
            fault_injection=True,
            fault_rate=0.05,  # high rate for testing
        )
        sim.run()
        last = sim.metrics_history[-1]
        assert last["faulted_fraction"] > 0, "Some faults should have occurred"

    def test_no_faults_when_disabled(self):
        """Without fault injection, no faults should occur."""
        sim = PhysicalSimulation(
            grid_shape=(10, 10, 4),
            steps=50,
            fault_injection=False,
        )
        sim.run()
        last = sim.metrics_history[-1]
        assert last["faulted_fraction"] == 0.0
