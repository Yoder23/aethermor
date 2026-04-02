"""Numerical robustness tests.

Tests that models handle edge cases, bad inputs, extreme ranges, unit
mistakes, and missing parameters gracefully.
"""

import math
import pytest
import numpy as np

from aethermor.physics.cooling import (
    CoolingStack, PackageStack, ThermalLayer, THERMAL_LAYERS,
)
from aethermor.physics.materials import get_material
from aethermor.physics.constants import landauer_limit


# ═══════════════════════════════════════════════════════════
# Edge-case inputs
# ═══════════════════════════════════════════════════════════

class TestZeroPower:
    """Zero power → T_j == T_ambient, no errors."""

    def test_cooling_stack_zero_power(self):
        stack = CoolingStack.desktop_air()
        A = 150e-6
        R = stack.total_resistance(A)
        T_j = stack.T_ambient + 0.0 * R
        assert T_j == stack.T_ambient

    def test_package_stack_zero_power(self):
        pkg = PackageStack.desktop_cpu()
        A = 257e-6
        T_j = pkg.junction_temperature(A, 0.0)
        assert T_j == pkg.T_ambient


class TestVerySmallPower:
    """Tiny power should give near-ambient temperature."""

    def test_micropower(self):
        pkg = PackageStack.desktop_cpu()
        A = 257e-6
        T_j = pkg.junction_temperature(A, 1e-9)
        assert abs(T_j - pkg.T_ambient) < 1e-6


class TestVeryHighPower:
    """Extreme power should not cause NaN/Inf."""

    def test_kilowatt_power(self):
        stack = CoolingStack.liquid_cooled()
        A = 800e-6
        R = stack.total_resistance(A)
        T_j = stack.T_ambient + 10_000.0 * R
        assert math.isfinite(T_j)
        assert T_j > stack.T_ambient


class TestExtremeAreas:
    """Very small and very large die areas."""

    def test_tiny_die(self):
        """1 mm² die — should still compute."""
        stack = CoolingStack.desktop_air()
        A = 1e-6
        R = stack.total_resistance(A)
        assert math.isfinite(R)
        assert R > 0

    def test_huge_die(self):
        """10000 mm² die — wafer-scale."""
        stack = CoolingStack.desktop_air()
        A = 10000e-6  # 100 cm²
        R = stack.total_resistance(A)
        assert math.isfinite(R)
        assert R > 0

    def test_package_stack_tiny_die(self):
        pkg = PackageStack.server_gpu()
        A = 1e-6
        theta = pkg.theta_jc(A)
        assert math.isfinite(theta)
        assert theta > 0


class TestExtremeTemperatures:
    """Very low and very high ambient temperatures."""

    def test_cryogenic_ambient(self):
        """77 K liquid nitrogen cooling."""
        stack = CoolingStack(h_ambient=200.0, T_ambient=77.0)
        stack.add_layer(THERMAL_LAYERS["copper_heatsink"])
        R = stack.total_resistance(200e-6)
        T_j = 77.0 + 100.0 * R
        assert math.isfinite(T_j)
        assert T_j > 77.0

    def test_high_ambient(self):
        """Military spec: 85°C ambient."""
        pkg = PackageStack.desktop_cpu()
        pkg_high = PackageStack(
            die_thickness_m=pkg.die_thickness_m,
            die_conductivity=pkg.die_conductivity,
            tim=pkg.tim, ihs=pkg.ihs, heatsink=pkg.heatsink,
            contact_die_tim=pkg.contact_die_tim,
            contact_tim_ihs=pkg.contact_tim_ihs,
            contact_ihs_heatsink=pkg.contact_ihs_heatsink,
            h_ambient=pkg.h_ambient,
            T_ambient=358.15,  # 85°C
        )
        T_j = pkg_high.junction_temperature(257e-6, 125.0)
        assert T_j > 358.15


# ═══════════════════════════════════════════════════════════
# Nonsensical / bad inputs
# ═══════════════════════════════════════════════════════════

class TestNegativeInputs:
    """Negative values should not crash the model."""

    def test_negative_power_cooling_stack(self):
        """Negative power → below-ambient temperature (physically: cooling)."""
        stack = CoolingStack.desktop_air()
        A = 150e-6
        R = stack.total_resistance(A)
        T_j = stack.T_ambient + (-50.0) * R
        assert T_j < stack.T_ambient

    def test_negative_power_package_stack(self):
        pkg = PackageStack.desktop_cpu()
        T_j = pkg.junction_temperature(257e-6, -50.0)
        assert T_j < pkg.T_ambient


class TestZeroThickness:
    """Zero-thickness layer should contribute zero resistance."""

    def test_zero_layer(self):
        layer = ThermalLayer("zero", 0.0, 148.0)
        R = layer.resistance(100e-6)
        assert R == 0.0


class TestZeroArea:
    """Zero area should raise or give inf (division by zero), not crash silently."""

    def test_resistance_zero_area(self):
        layer = ThermalLayer("die", 0.5e-3, 148.0)
        with pytest.raises((ZeroDivisionError, ValueError)):
            layer.resistance(0.0)

    def test_cooling_stack_zero_area(self):
        stack = CoolingStack.desktop_air()
        with pytest.raises((ZeroDivisionError, ValueError)):
            stack.total_resistance(0.0)


# ═══════════════════════════════════════════════════════════
# Unit-mistake detection (order-of-magnitude guards)
# ═══════════════════════════════════════════════════════════

class TestUnitSanity:
    """Detect common unit mistakes by checking result magnitude."""

    def test_area_in_m2_not_mm2(self):
        """If user passes 150 (mm² value) instead of 150e-6 (m²),
        resistance will be absurdly small."""
        stack = CoolingStack.desktop_air()
        R_correct = stack.total_resistance(150e-6)
        R_wrong = stack.total_resistance(150.0)  # mm² mistake
        # Wrong area gives ~1e6 times smaller resistance
        assert R_correct / R_wrong > 1e5

    def test_power_in_watts(self):
        """Sanity: 100W into liquid-cooled stack gives T_j < 1000 K."""
        pkg = PackageStack.server_gpu()
        T_j = pkg.junction_temperature(800e-6, 100.0)
        assert T_j < 1000.0  # server GPU: high h, large die


# ═══════════════════════════════════════════════════════════
# Monotonicity
# ═══════════════════════════════════════════════════════════

class TestMonotonicity:
    """Physical monotonicity: more power → hotter, more area → less resistance."""

    def test_more_power_is_hotter(self):
        pkg = PackageStack.desktop_cpu()
        A = 257e-6
        T_low = pkg.junction_temperature(A, 50.0)
        T_high = pkg.junction_temperature(A, 200.0)
        assert T_high > T_low

    def test_larger_area_less_resistance(self):
        stack = CoolingStack.desktop_air()
        R_small = stack.total_resistance(50e-6)
        R_large = stack.total_resistance(500e-6)
        assert R_small > R_large

    def test_higher_h_less_resistance(self):
        A = 200e-6
        stack_low = CoolingStack(h_ambient=50.0)
        stack_high = CoolingStack(h_ambient=5000.0)
        assert stack_low.total_resistance(A) > stack_high.total_resistance(A)

    def test_thicker_layer_more_resistance(self):
        A = 200e-6
        thin = ThermalLayer("thin", 0.1e-3, 148.0)
        thick = ThermalLayer("thick", 1.0e-3, 148.0)
        assert thick.resistance(A) > thin.resistance(A)


# ═══════════════════════════════════════════════════════════
# Landauer limit edge cases
# ═══════════════════════════════════════════════════════════

class TestLandauerEdgeCases:
    """Landauer limit at edge temperatures."""

    def test_zero_kelvin(self):
        E = landauer_limit(0.0)
        assert E == 0.0

    def test_near_zero_kelvin(self):
        E = landauer_limit(1e-10)
        assert E >= 0.0
        assert math.isfinite(E)

    def test_negative_temperature(self):
        """Negative T is unphysical but should not crash."""
        E = landauer_limit(-1.0)
        # Returns negative — mathematically valid, physically meaningless
        assert math.isfinite(E)


# ═══════════════════════════════════════════════════════════
# PackageStack factory completeness
# ═══════════════════════════════════════════════════════════

class TestFactoryCompleteness:
    """All factory methods produce functional PackageStack objects."""

    @pytest.mark.parametrize("factory", ["desktop_cpu", "server_gpu", "mobile_soc"])
    def test_factory_produces_valid_stack(self, factory):
        pkg = getattr(PackageStack, factory)()
        A = 200e-6
        assert pkg.total_resistance(A) > 0
        assert pkg.effective_h(A) > 0
        T_j = pkg.junction_temperature(A, 100.0)
        assert math.isfinite(T_j)
        assert T_j > pkg.T_ambient

    @pytest.mark.parametrize("factory", [
        "bare_die_natural_air", "desktop_air", "server_air", "liquid_cooled",
    ])
    def test_cooling_stack_factory(self, factory):
        stack = getattr(CoolingStack, factory)()
        A = 200e-6
        assert stack.total_resistance(A) > 0
        assert stack.effective_h(A) > 0


# ═══════════════════════════════════════════════════════════
# Serialization round-trip
# ═══════════════════════════════════════════════════════════

class TestPackageStackRoundTrip:
    """to_dict / from_dict preserves all parameters."""

    def test_desktop_roundtrip(self):
        pkg = PackageStack.desktop_cpu()
        d = pkg.to_dict()
        pkg2 = PackageStack.from_dict(d)
        A = 257e-6
        assert abs(pkg.total_resistance(A) - pkg2.total_resistance(A)) < 1e-12
        assert abs(pkg.theta_jc(A) - pkg2.theta_jc(A)) < 1e-12
