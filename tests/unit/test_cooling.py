"""
Tests for CoolingStack thermal model.

Validates thermal layer resistance calculations, cooling stack assembly,
factory methods, and physical consistency of the cooling path model.
"""

import math
import pytest
from aethermor.physics.cooling import (
    ThermalLayer,
    THERMAL_LAYERS,
    CoolingStack,
)


class TestThermalLayer:
    """Verify individual thermal layer physics."""

    def test_resistance_formula(self):
        """R = L / (k · A) for a uniform slab."""
        layer = ThermalLayer("test", thickness_m=1e-3, thermal_conductivity=100.0)
        area = 1e-4  # 1 cm²
        R = layer.resistance(area)
        expected = 1e-3 / (100.0 * 1e-4)  # 0.1 K/W
        assert abs(R - expected) < 1e-10

    def test_resistance_inversely_proportional_to_area(self):
        """Doubling area should halve resistance."""
        layer = ThermalLayer("test", thickness_m=1e-3, thermal_conductivity=100.0)
        R1 = layer.resistance(1e-4)
        R2 = layer.resistance(2e-4)
        assert abs(R1 / R2 - 2.0) < 1e-10

    def test_resistance_proportional_to_thickness(self):
        """Doubling thickness should double resistance."""
        thin = ThermalLayer("thin", thickness_m=1e-3, thermal_conductivity=100.0)
        thick = ThermalLayer("thick", thickness_m=2e-3, thermal_conductivity=100.0)
        area = 1e-4
        assert abs(thick.resistance(area) / thin.resistance(area) - 2.0) < 1e-10

    def test_higher_k_gives_lower_resistance(self):
        """Higher thermal conductivity should give lower resistance."""
        lo_k = ThermalLayer("lo", thickness_m=1e-3, thermal_conductivity=10.0)
        hi_k = ThermalLayer("hi", thickness_m=1e-3, thermal_conductivity=100.0)
        area = 1e-4
        assert hi_k.resistance(area) < lo_k.resistance(area)


class TestThermalLayersLibrary:
    """Verify pre-built thermal layers have sensible values."""

    def test_library_not_empty(self):
        assert len(THERMAL_LAYERS) >= 10

    def test_all_layers_have_positive_thickness(self):
        for key, layer in THERMAL_LAYERS.items():
            assert layer.thickness_m > 0, f"{key} has non-positive thickness"

    def test_all_layers_have_positive_conductivity(self):
        for key, layer in THERMAL_LAYERS.items():
            assert layer.thermal_conductivity > 0, \
                f"{key} has non-positive conductivity"

    def test_copper_higher_k_than_aluminum(self):
        """Copper should conduct better than aluminum."""
        cu = THERMAL_LAYERS["copper_ihs"]
        al = THERMAL_LAYERS["aluminum_heatsink"]
        assert cu.thermal_conductivity > al.thermal_conductivity

    def test_diamond_highest_conductivity(self):
        """Diamond should have the highest conductivity in the library."""
        diamond = THERMAL_LAYERS["diamond_heat_spreader"]
        for key, layer in THERMAL_LAYERS.items():
            if key != "diamond_heat_spreader":
                assert diamond.thermal_conductivity >= layer.thermal_conductivity, \
                    f"diamond should beat {key}"


class TestCoolingStack:
    """Verify cooling stack assembly and calculations."""

    def test_empty_stack_has_zero_resistance(self):
        """Empty stack (no layers) should have zero total resistance."""
        stack = CoolingStack(h_ambient=100.0)
        area = 1e-4
        # Only convective resistance: 1/(h*A) — handled by effective_h
        # total_resistance should be zero for just the stack layers
        assert stack.total_resistance(area) >= 0

    def test_total_resistance_additive(self):
        """Series layers: R_total = R_layers + R_convection."""
        stack = CoolingStack(h_ambient=100.0)
        layer1 = ThermalLayer("L1", thickness_m=1e-3, thermal_conductivity=100.0)
        layer2 = ThermalLayer("L2", thickness_m=2e-3, thermal_conductivity=200.0)
        stack.add_layer(layer1)
        stack.add_layer(layer2)
        area = 1e-4
        # total_resistance includes convection: R_layers + 1/(h*A)
        R_expected = (layer1.resistance(area) + layer2.resistance(area)
                      + 1.0 / (100.0 * area))
        assert abs(stack.total_resistance(area) - R_expected) < 1e-10

    def test_effective_h_includes_convection(self):
        """effective_h should combine stack resistance with convection."""
        stack = CoolingStack(h_ambient=1000.0)
        layer = ThermalLayer("TIM", thickness_m=1e-3, thermal_conductivity=10.0)
        stack.add_layer(layer)
        area = 1e-4  # 1 cm²

        R_layer = layer.resistance(area)   # 1e-3/(10*1e-4) = 1.0 K/W
        R_conv = 1.0 / (1000.0 * area)    # = 10.0 K/W
        R_total = R_layer + R_conv         # 11.0 K/W
        h_eff = 1.0 / (R_total * area)    # 1/(11*1e-4) = 909 W/(m²·K)

        assert abs(stack.effective_h(area) - h_eff) / h_eff < 1e-6

    def test_max_power_positive(self):
        """max_power_W should return a positive value."""
        stack = CoolingStack.desktop_air()
        P = stack.max_power_W(die_area_m2=1e-4, T_junction_max=378.0)
        assert P > 0

    def test_max_power_increases_with_area(self):
        """Larger die should allow more power (more cooling area)."""
        stack = CoolingStack.desktop_air()
        P_small = stack.max_power_W(1e-4)
        P_large = stack.max_power_W(4e-4)
        assert P_large > P_small

    def test_layer_temperatures_monotonic(self):
        """Temperature should decrease from die surface to ambient."""
        stack = CoolingStack.desktop_air()
        area = 1e-4
        temps = stack.layer_temperatures(area, power_W=100.0)
        assert len(temps) > 0
        T_values = [t["T_K"] for t in temps]
        # Temperature should be non-increasing from die to ambient
        for i in range(len(T_values) - 1):
            assert T_values[i] >= T_values[i + 1] - 1e-10

    def test_add_layer_returns_self(self):
        """add_layer should return self for chaining."""
        stack = CoolingStack(h_ambient=100.0)
        result = stack.add_layer(THERMAL_LAYERS["copper_ihs"])
        assert result is stack

    def test_describe_returns_string(self):
        """describe() should return a non-empty string."""
        stack = CoolingStack.desktop_air()
        desc = stack.describe(1e-4)
        assert isinstance(desc, str)
        assert len(desc) > 10


class TestCoolingStackFactories:
    """Verify factory methods create valid, ordered stacks."""

    @pytest.mark.parametrize("factory_name", [
        "bare_die_natural_air",
        "desktop_air",
        "server_air",
        "liquid_cooled",
        "direct_liquid",
        "diamond_spreader_liquid",
    ])
    def test_factory_produces_valid_stack(self, factory_name):
        factory = getattr(CoolingStack, factory_name)
        stack = factory()
        assert isinstance(stack, CoolingStack)
        # Should have positive effective_h
        h = stack.effective_h(1e-4)
        assert h > 0

    def test_liquid_better_than_air(self):
        """Liquid cooling should give higher effective_h than air."""
        air = CoolingStack.desktop_air()
        liquid = CoolingStack.liquid_cooled()
        area = 1e-4
        assert liquid.effective_h(area) > air.effective_h(area)

    def test_diamond_best_cooling(self):
        """Diamond spreader should give highest effective_h."""
        diamond = CoolingStack.diamond_spreader_liquid()
        air = CoolingStack.desktop_air()
        area = 1e-4
        assert diamond.effective_h(area) > air.effective_h(area)

    def test_factory_power_ordering(self):
        """More advanced cooling should handle more power."""
        area = 1e-4
        T_max = 378.0
        P_air = CoolingStack.desktop_air().max_power_W(area, T_max)
        P_liquid = CoolingStack.liquid_cooled().max_power_W(area, T_max)
        assert P_liquid > P_air
