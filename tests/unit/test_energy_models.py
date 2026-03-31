"""
Tests for gate energy models.

Validates that energy models produce physically reasonable values and
that the relationships between paradigms are correct. These tests ensure
the simulation gives hardware researchers trustworthy numbers.
"""

import math
import pytest
from aethermor.physics.constants import k_B, landauer_limit
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)


class TestCMOSGateEnergy:
    """Verify CMOS energy model produces realistic values."""

    def test_7nm_dynamic_energy_order_of_magnitude(self):
        """At 7 nm, dynamic energy should be ~10⁻¹⁶ J (sub-femtojoule)."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        E = cmos.dynamic_energy()
        assert 1e-17 < E < 1e-14  # reasonable range for 7 nm

    def test_energy_increases_with_node_size(self):
        """Larger technology nodes should use more energy per switch."""
        E_7nm = CMOSGateEnergy(tech_node_nm=7).dynamic_energy()
        E_45nm = CMOSGateEnergy(tech_node_nm=45).dynamic_energy()
        E_130nm = CMOSGateEnergy(tech_node_nm=130).dynamic_energy()
        assert E_7nm < E_45nm < E_130nm

    def test_leakage_increases_with_temperature(self):
        """Leakage power should increase exponentially with temperature."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        P_300 = cmos.leakage_power(300.0)
        P_400 = cmos.leakage_power(400.0)
        assert P_400 > P_300 * 2  # should be much more at +100 K

    def test_landauer_gap_well_above_1(self):
        """CMOS at 7 nm should be 10³-10⁶ × above Landauer limit."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        gap = cmos.landauer_gap(300.0, 1e9)
        assert gap > 1e3
        assert gap < 1e10  # shouldn't be astronomically high

    def test_total_energy_exceeds_dynamic_at_low_freq(self):
        """At low frequency, leakage should dominate over dynamic."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        E_low = cmos.energy_per_switch(frequency=1e6, T=300.0)  # 1 MHz
        E_dyn = cmos.dynamic_energy()
        assert E_low > E_dyn  # leakage dominates at low freq


class TestAdiabaticGateEnergy:
    """Verify adiabatic logic energy model."""

    def test_energy_decreases_with_lower_frequency(self):
        """Adiabatic energy should decrease as switching slows down."""
        adiab = AdiabaticGateEnergy(tech_node_nm=7)
        E_fast = adiab.energy_per_switch(frequency=1e10)
        E_slow = adiab.energy_per_switch(frequency=1e8)
        assert E_slow < E_fast

    def test_never_below_landauer(self):
        """Even at very low frequency, can't go below Landauer limit."""
        adiab = AdiabaticGateEnergy(tech_node_nm=7)
        E = adiab.energy_per_switch(frequency=1.0, T=300.0)  # 1 Hz
        E_min = landauer_limit(300.0)
        assert E >= E_min

    def test_crossover_frequency_exists(self):
        """There should be a frequency where adiabatic beats CMOS."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        adiab = AdiabaticGateEnergy(tech_node_nm=7)
        f_cross = adiab.crossover_frequency(cmos)
        assert f_cross > 0
        assert f_cross < 1e15  # should exist below petahertz

    def test_below_crossover_adiabatic_wins(self):
        """Below crossover frequency, adiabatic should use less energy."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        adiab = AdiabaticGateEnergy(tech_node_nm=7)
        f_cross = adiab.crossover_frequency(cmos)
        E_cmos = cmos.energy_per_switch(f_cross / 10)
        E_adiab = adiab.energy_per_switch(f_cross / 10)
        assert E_adiab < E_cmos


class TestReversibleGateEnergy:
    """Verify reversible computing energy model."""

    def test_energy_scales_with_temperature(self):
        """Reversible gate energy should scale linearly with T."""
        rev = ReversibleGateEnergy()
        E_300 = rev.energy_per_switch(T=300.0)
        E_600 = rev.energy_per_switch(T=600.0)
        # Not exactly 2× because of clock overhead, but should increase
        assert E_600 > E_300

    def test_frequency_independent(self):
        """Reversible gate energy should be roughly frequency-independent."""
        rev = ReversibleGateEnergy()
        E_1GHz = rev.energy_per_switch(frequency=1e9)
        E_1THz = rev.energy_per_switch(frequency=1e12)
        assert abs(E_1GHz - E_1THz) / E_1GHz < 0.01  # within 1%

    def test_gap_above_1(self):
        """Even reversible logic has overhead above Landauer minimum."""
        rev = ReversibleGateEnergy()
        gap = rev.landauer_gap(300.0)
        assert gap > 1.0  # overhead factor > 1

    def test_temperature_crossover_exists(self):
        """There should be a temperature where reversible beats CMOS."""
        cmos = CMOSGateEnergy(tech_node_nm=7)
        rev = ReversibleGateEnergy()
        T_cross = rev.temperature_crossover(cmos, frequency=1e9)
        # Reversible should beat CMOS at low temperatures
        assert T_cross > 0


class TestLandauerLimit:
    """Verify the Landauer limit reference model."""

    def test_gap_is_always_1(self):
        gap = LandauerLimitEnergy().landauer_gap(300.0)
        assert abs(gap - 1.0) < 1e-10

    def test_energy_matches_formula(self):
        E = LandauerLimitEnergy(bits_per_gate=1.0).energy_per_switch(T=300.0)
        expected = k_B * 300.0 * math.log(2.0)
        assert abs(E - expected) < 1e-30


class TestParadigmOrdering:
    """
    Verify the energy ordering between paradigms at typical operating points.

    At standard conditions (300 K, 1 GHz, 7 nm):
      Landauer < Reversible < Adiabatic (at low freq) < CMOS

    This ordering is fundamental to thermodynamic computing research.
    """

    def test_ordering_at_low_frequency(self):
        """At 100 MHz, the paradigm ordering should hold."""
        freq = 1e8
        T = 300.0
        E_landauer = LandauerLimitEnergy().energy_per_switch(freq, T)
        E_rev = ReversibleGateEnergy().energy_per_switch(freq, T)
        E_adiab = AdiabaticGateEnergy(tech_node_nm=7).energy_per_switch(freq, T)
        E_cmos = CMOSGateEnergy(tech_node_nm=7).energy_per_switch(freq, T)

        assert E_landauer < E_rev, "Reversible should exceed Landauer"
        assert E_landauer < E_cmos, "CMOS should exceed Landauer"
        # At low freq, adiabatic should beat CMOS
        assert E_adiab < E_cmos, "Adiabatic should beat CMOS at low frequency"
