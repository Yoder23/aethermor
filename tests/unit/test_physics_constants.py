"""
Tests for the physics constants module.

Validates that fundamental constants are correct and derived quantities
compute properly. These are basic sanity checks that the physics foundation
is sound.
"""

import math
import pytest
from aethermor.physics.constants import (
    k_B, h_PLANCK, h_BAR, E_CHARGE, LANDAUER_LIMIT,
    landauer_limit, thermal_noise_voltage, thermal_energy, bits_per_joule,
)


class TestPhysicalConstants:
    """Verify fundamental constants match CODATA values."""

    def test_boltzmann(self):
        assert abs(k_B - 1.380649e-23) < 1e-29

    def test_planck(self):
        assert abs(h_PLANCK - 6.62607015e-34) < 1e-40

    def test_hbar_is_h_over_2pi(self):
        assert abs(h_BAR - h_PLANCK / (2 * math.pi)) < 1e-45

    def test_elementary_charge(self):
        assert abs(E_CHARGE - 1.602176634e-19) < 1e-28


class TestLandauerLimit:
    """
    Verify the Landauer limit computation.

    The Landauer limit (k_B · T · ln 2) is the theoretical minimum energy
    to irreversibly erase one bit. Getting this right is foundational.
    """

    def test_at_300K(self):
        """At 300 K, Landauer limit should be ~2.85 × 10⁻²¹ J."""
        E = landauer_limit(300.0)
        expected = k_B * 300.0 * math.log(2.0)
        assert abs(E - expected) < 1e-30
        # ~2.87 × 10⁻²¹ J at 300 K — verify order of magnitude
        assert 2.8e-21 < E < 2.9e-21

    def test_scales_linearly_with_temperature(self):
        """Doubling temperature should double the limit."""
        E1 = landauer_limit(300.0)
        E2 = landauer_limit(600.0)
        assert abs(E2 / E1 - 2.0) < 1e-10

    def test_at_4K(self):
        """At 4 K (cryogenic), limit should be ~100× lower than 300 K."""
        E_cryo = landauer_limit(4.0)
        E_room = landauer_limit(300.0)
        assert abs(E_room / E_cryo - 75.0) < 0.01

    def test_precomputed_constant_matches(self):
        """LANDAUER_LIMIT constant should equal landauer_limit(300)."""
        assert abs(LANDAUER_LIMIT - landauer_limit(300.0)) < 1e-35


class TestThermalNoise:
    """Test Johnson-Nyquist noise voltage calculation."""

    def test_zero_at_zero_temperature(self):
        V = thermal_noise_voltage(0.0, 1000.0, 1e6)
        assert V == 0.0

    def test_scales_with_sqrt_T(self):
        V1 = thermal_noise_voltage(300.0, 1000.0, 1e6)
        V2 = thermal_noise_voltage(1200.0, 1000.0, 1e6)
        assert abs(V2 / V1 - 2.0) < 1e-10

    def test_reasonable_magnitude(self):
        """At 300 K, 1 kΩ, 1 MHz bandwidth: ~4 μV RMS."""
        V = thermal_noise_voltage(300.0, 1000.0, 1e6)
        assert 1e-6 < V < 10e-6  # should be ~4 μV


class TestDerivedQuantities:
    """Test derived quantities like bits_per_joule."""

    def test_bits_per_joule_inverse_of_landauer(self):
        bpj = bits_per_joule(300.0)
        E = landauer_limit(300.0)
        assert abs(bpj * E - 1.0) < 1e-10

    def test_thermal_energy(self):
        E = thermal_energy(300.0)
        assert abs(E - k_B * 300.0) < 1e-30
