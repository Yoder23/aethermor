"""
Tests for the extensibility registries (materials, paradigms, cooling layers).

These tests verify that engineers can:
  - Register custom materials with validation
  - Register custom computing paradigms
  - Register custom cooling layers
  - Use all custom components through the full pipeline
  - Save and load custom configurations as JSON
"""

import json
import math
import os
import tempfile
import warnings
from dataclasses import dataclass

import pytest

from aethermor.physics.constants import landauer_limit
from aethermor.physics.materials import (
    Material,
    MaterialRegistry,
    registry,
    get_material,
    list_materials,
    validate_material,
    material_from_dict,
    material_to_dict,
    register_material,
    unregister_material,
    MATERIAL_DB,
)
from aethermor.physics.energy_models import (
    EnergyModel,
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
    ParadigmRegistry,
    paradigm_registry,
    register_paradigm,
)
from aethermor.physics.cooling import (
    ThermalLayer,
    CoolingStack,
    CoolingRegistry,
    cooling_registry,
    register_cooling_layer,
    validate_layer,
    layer_from_dict,
    layer_to_dict,
    THERMAL_LAYERS,
)
from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from aethermor.analysis.thermal_optimizer import ThermalOptimizer


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registries():
    """Reset all registries after each test to avoid cross-contamination."""
    yield
    registry.reset()
    # paradigm registry has no reset — custom paradigms persist, which is fine


@pytest.fixture
def sample_material():
    return Material(
        name="Test Material",
        thermal_conductivity=200.0,
        specific_heat=500.0,
        density=3000.0,
        electrical_resistivity=1e8,
        max_operating_temp=800.0,
        bandgap_eV=2.5,
        notes="Test material for unit tests.",
    )


# ══════════════════════════════════════════════════════════════════════
#  Material Registry Tests
# ══════════════════════════════════════════════════════════════════════

class TestMaterialRegistry:
    """Tests for custom material registration, validation, and lookup."""

    def test_builtin_materials_available(self):
        """All 9 built-in materials should be accessible."""
        assert len(registry.list_builtins()) == 9
        assert "silicon" in registry
        assert "diamond" in registry
        assert "gallium_arsenide" in registry

    def test_register_custom_material(self, sample_material):
        """Register and retrieve a custom material."""
        registry.register("test_mat", sample_material)
        assert "test_mat" in registry
        m = registry.get("test_mat")
        assert m.name == "Test Material"
        assert m.thermal_conductivity == 200.0

    def test_register_from_dict(self):
        """Register a material from a dictionary."""
        registry.register("from_dict", {
            "name": "Dict Material",
            "thermal_conductivity": 150.0,
            "specific_heat": 400.0,
            "density": 2500.0,
            "electrical_resistivity": 1e6,
            "max_operating_temp": 700.0,
        })
        m = get_material("from_dict")
        assert m.name == "Dict Material"
        assert m.bandgap_eV == 0.0  # default

    def test_get_material_uses_registry(self, sample_material):
        """get_material() should find custom materials."""
        registry.register("custom_test", sample_material)
        m = get_material("custom_test")
        assert m.name == "Test Material"

    def test_list_materials_includes_custom(self, sample_material):
        """list_materials() should include custom materials."""
        registry.register("custom_test", sample_material)
        all_mats = list_materials()
        assert "custom_test" in all_mats
        assert "silicon" in all_mats  # built-in still there

    def test_unregister_custom(self, sample_material):
        """Unregister a custom material."""
        registry.register("temp", sample_material)
        assert "temp" in registry
        registry.unregister("temp")
        assert "temp" not in registry

    def test_cannot_unregister_builtin(self):
        """Cannot remove built-in materials."""
        with pytest.raises(KeyError, match="built-in"):
            registry.unregister("silicon")

    def test_cannot_overwrite_builtin_without_force(self, sample_material):
        """Overwriting a built-in requires force=True."""
        with pytest.raises(KeyError, match="built-in"):
            registry.register("silicon", sample_material)

    def test_overwrite_builtin_with_force(self, sample_material):
        """force=True allows overwriting built-ins."""
        registry.register("silicon", sample_material, force=True)
        m = get_material("silicon")
        assert m.name == "Test Material"

    def test_key_normalization(self, sample_material):
        """Keys are normalized: lowercase, underscores for spaces/hyphens."""
        registry.register("My-Custom Material", sample_material)
        assert "my_custom_material" in registry
        m = get_material("My Custom Material")
        assert m.name == "Test Material"

    def test_reset_clears_custom_only(self, sample_material):
        """reset() removes custom materials but keeps built-ins."""
        registry.register("custom1", sample_material)
        registry.reset()
        assert "custom1" not in registry
        assert "silicon" in registry  # built-in preserved

    def test_len(self, sample_material):
        """__len__ counts both built-in and custom."""
        n_before = len(registry)
        registry.register("new_mat", sample_material)
        assert len(registry) == n_before + 1

    def test_iter(self, sample_material):
        """Can iterate over all material keys."""
        registry.register("iter_test", sample_material)
        keys = list(registry)
        assert "iter_test" in keys
        assert "silicon" in keys


class TestMaterialValidation:
    """Tests for material property validation."""

    def test_valid_material_passes(self):
        """Built-in materials should pass validation cleanly."""
        issues = validate_material(get_material("silicon"))
        assert len(issues) == 0

    def test_negative_conductivity_is_error(self):
        """Negative thermal conductivity is physically impossible."""
        bad = Material("Bad", -1.0, 500, 2000, 1e6, 600)
        issues = validate_material(bad)
        errors = [i for i in issues if "ERROR" in i]
        assert len(errors) > 0
        assert "thermal_conductivity" in errors[0]

    def test_extreme_values_warn(self):
        """Values outside typical range should trigger warnings."""
        extreme = Material("Extreme", 50000.0, 500, 2000, 1e6, 600)
        issues = validate_material(extreme)
        warns = [i for i in issues if "WARNING" in i]
        assert len(warns) > 0

    def test_empty_name_is_error(self):
        """Empty name should be an error."""
        bad = Material("", 100, 500, 2000, 1e6, 600)
        issues = validate_material(bad)
        assert any("name" in i for i in issues)

    def test_register_rejects_invalid_material(self):
        """Registration should fail for physically impossible materials."""
        with pytest.raises(ValueError, match="physically invalid"):
            registry.register("bad", Material("Bad", -100, 500, 2000, 1e6, 600))

    def test_register_warns_for_extreme_values(self):
        """Registration should warn (not fail) for extreme but valid values."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            registry.register("extreme", Material(
                "Extreme", 50000.0, 500, 2000, 1e6, 600,
            ))
            assert len(w) > 0
            assert "WARNING" in str(w[0].message)


class TestMaterialSerialization:
    """Tests for material JSON serialization."""

    def test_round_trip(self):
        """material_to_dict → material_from_dict should preserve data."""
        m = get_material("silicon")
        d = material_to_dict(m)
        m2 = material_from_dict(d)
        assert m2.name == m.name
        assert m2.thermal_conductivity == m.thermal_conductivity
        assert m2.bandgap_eV == m.bandgap_eV

    def test_from_dict_missing_required(self):
        """material_from_dict should reject dicts missing required fields."""
        with pytest.raises(ValueError, match="Missing"):
            material_from_dict({"name": "Incomplete"})

    def test_json_save_load(self, sample_material):
        """Save custom materials to JSON and load them back."""
        registry.register("json_test", sample_material)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            n_saved = registry.save_json(path)
            assert n_saved == 1

            # Reset and reload
            registry.reset()
            assert "json_test" not in registry

            n_loaded = registry.load_json(path)
            assert n_loaded == 1
            assert "json_test" in registry
            m = registry.get("json_test")
            assert m.name == "Test Material"
        finally:
            os.unlink(path)

    def test_save_custom_only(self, sample_material):
        """custom_only=True should skip built-in materials."""
        registry.register("save_test", sample_material)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            n = registry.save_json(path, custom_only=True)
            data = json.loads(open(path).read())
            assert "save_test" in data
            assert "silicon" not in data
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
#  Paradigm Registry Tests
# ══════════════════════════════════════════════════════════════════════

@dataclass
class _MockParadigm:
    """A minimal custom paradigm for testing."""
    tech_node_nm: float = 7.0
    fixed_energy: float = 1e-17

    def energy_per_switch(self, frequency=1e9, T=300.0):
        return self.fixed_energy

    def landauer_gap(self, T=300.0, frequency=1e9):
        return self.energy_per_switch(frequency, T) / landauer_limit(T)


class TestParadigmRegistry:
    """Tests for custom computing paradigm registration."""

    def test_builtin_paradigms(self):
        """Built-in paradigms should be registered."""
        assert "cmos" in paradigm_registry
        assert "adiabatic" in paradigm_registry
        assert "reversible" in paradigm_registry
        assert "landauer" in paradigm_registry
        assert "idle" in paradigm_registry  # special case

    def test_register_custom_paradigm(self):
        """Register and create a custom paradigm."""
        paradigm_registry.register("mock_paradigm", _MockParadigm)
        model = paradigm_registry.create("mock_paradigm", tech_node_nm=14)
        assert model.tech_node_nm == 14
        assert model.energy_per_switch() == 1e-17

    def test_protocol_check(self):
        """Built-in models satisfy the EnergyModel protocol."""
        assert isinstance(CMOSGateEnergy(), EnergyModel)
        assert isinstance(AdiabaticGateEnergy(), EnergyModel)
        assert isinstance(ReversibleGateEnergy(), EnergyModel)
        assert isinstance(LandauerLimitEnergy(), EnergyModel)
        assert isinstance(_MockParadigm(), EnergyModel)

    def test_protocol_check_rejects_bad_class(self):
        """Classes without required methods should be rejected."""
        class BadModel:
            pass

        with pytest.raises(TypeError, match="EnergyModel"):
            paradigm_registry.register("bad", BadModel)

    def test_paradigm_ids(self):
        """Each paradigm gets a unique integer ID for visualization."""
        assert paradigm_registry.paradigm_id("idle") == 0
        assert paradigm_registry.paradigm_id("cmos") == 1
        assert paradigm_registry.paradigm_id("adiabatic") == 2

        paradigm_registry.register("test_id_paradigm", _MockParadigm)
        pid = paradigm_registry.paradigm_id("test_id_paradigm")
        assert pid >= 5  # custom paradigms start at 5+

    def test_create_idle_returns_none(self):
        """The 'idle' paradigm should return None (no energy model)."""
        assert paradigm_registry.create("idle") is None

    def test_create_unknown_raises(self):
        """Creating an unknown paradigm should raise KeyError."""
        with pytest.raises(KeyError, match="Unknown paradigm"):
            paradigm_registry.create("nonexistent_paradigm")

    def test_list_paradigms(self):
        """list_paradigms() returns sorted list of registered names."""
        names = paradigm_registry.list_paradigms()
        assert "cmos" in names
        assert "adiabatic" in names
        assert names == sorted(names)


class TestParadigmInFloorplan:
    """Test that custom paradigms work in ChipFloorplan."""

    def test_custom_paradigm_in_heat_map(self):
        """Custom paradigm should generate correct heat in a chip."""
        paradigm_registry.register("test_floor_paradigm", _MockParadigm)

        chip = ChipFloorplan(grid_shape=(10, 10, 2))
        chip.add_block(FunctionalBlock(
            name="test_block",
            x_range=(0, 5), y_range=(0, 5), z_range=(0, 2),
            gate_density=1e6,
            activity=0.5,
            paradigm="test_floor_paradigm",
        ))

        heat = chip.heat_map(frequency_Hz=1e9)
        assert heat.max() > 0
        assert heat[6, 6, 0] == 0  # outside block

    def test_custom_paradigm_in_paradigm_map(self):
        """Custom paradigm should get a unique ID in paradigm_map."""
        paradigm_registry.register("test_pmap_paradigm", _MockParadigm)

        chip = ChipFloorplan(grid_shape=(10, 10, 2))
        chip.add_block(FunctionalBlock(
            name="test_block",
            x_range=(2, 8), y_range=(2, 8), z_range=(0, 2),
            paradigm="test_pmap_paradigm",
        ))

        pmap = chip.paradigm_map()
        pid = paradigm_registry.paradigm_id("test_pmap_paradigm")
        assert pid in pmap  # custom paradigm ID appears in map
        assert pmap[0, 0, 0] == 0  # outside = idle


# ══════════════════════════════════════════════════════════════════════
#  Cooling Registry Tests
# ══════════════════════════════════════════════════════════════════════

class TestCoolingRegistry:
    """Tests for custom cooling layer registration."""

    def test_builtin_layers_available(self):
        """All built-in layers should be accessible."""
        assert "copper_ihs" in cooling_registry
        assert "liquid_metal" in cooling_registry
        assert len(cooling_registry) == len(THERMAL_LAYERS)

    def test_register_custom_layer(self):
        """Register and retrieve a custom cooling layer."""
        cooling_registry.register("test_layer", ThermalLayer(
            "Test Layer", 100e-6, 25.0, "Test."
        ))
        layer = cooling_registry.get("test_layer")
        assert layer.name == "Test Layer"
        assert layer.thermal_conductivity == 25.0

    def test_register_from_dict(self):
        """Register a layer from a dictionary."""
        cooling_registry.register("dict_layer", {
            "name": "Dict Layer",
            "thickness_m": 50e-6,
            "thermal_conductivity": 10.0,
        })
        layer = cooling_registry.get("dict_layer")
        assert layer.name == "Dict Layer"

    def test_unregister(self):
        """Unregister a custom layer."""
        cooling_registry.register("temp_layer", ThermalLayer(
            "Temp", 1e-3, 5.0
        ))
        cooling_registry.unregister("temp_layer")
        assert "temp_layer" not in cooling_registry

    def test_validation_rejects_negative_conductivity(self):
        """Negative thermal conductivity should be rejected."""
        with pytest.raises(ValueError):
            cooling_registry.register("bad", ThermalLayer(
                "Bad", 1e-3, -5.0
            ))

    def test_custom_layer_in_stack(self):
        """Custom layers should work in CoolingStack."""
        cooling_registry.register("custom_tim", ThermalLayer(
            "Custom TIM", 30e-6, 15.0, "High-performance paste."
        ))

        stack = CoolingStack(h_ambient=5000)
        stack.add_layer(cooling_registry.get("custom_tim"))
        stack.add_layer(cooling_registry.get("copper_heatsink"))

        h = stack.effective_h(100e-6)
        assert h > 0
        assert h < 5000  # should be less than bare h_ambient


class TestCoolingSerialization:
    """Tests for cooling layer JSON serialization."""

    def test_round_trip(self):
        """layer_to_dict → layer_from_dict preserves data."""
        layer = THERMAL_LAYERS["copper_ihs"]
        d = layer_to_dict(layer)
        layer2 = layer_from_dict(d)
        assert layer2.name == layer.name
        assert layer2.thickness_m == layer.thickness_m
        assert layer2.thermal_conductivity == layer.thermal_conductivity

    def test_json_save_load(self):
        """Save and load custom layers as JSON."""
        cooling_registry.register("json_layer", ThermalLayer(
            "JSON Test", 1e-3, 42.0, "For testing."
        ))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            n = cooling_registry.save_json(path)
            assert n >= 1

            cooling_registry.unregister("json_layer")
            assert "json_layer" not in cooling_registry

            n = cooling_registry.load_json(path)
            assert "json_layer" in cooling_registry
        finally:
            os.unlink(path)
            cooling_registry.reset()


# ══════════════════════════════════════════════════════════════════════
#  Integration: Custom material through full pipeline
# ══════════════════════════════════════════════════════════════════════

class TestFullPipelineExtensibility:
    """End-to-end: custom material flows through optimizer and simulation."""

    def test_custom_material_in_optimizer_ranking(self):
        """A custom material should appear in optimizer rankings."""
        registry.register("pipeline_test", Material(
            name="Pipeline Test",
            thermal_conductivity=500.0,
            specific_heat=600.0,
            density=2800.0,
            electrical_resistivity=1e10,
            max_operating_temp=900.0,
            bandgap_eV=4.0,
        ))

        opt = ThermalOptimizer(
            grid_shape=(8, 8, 2),
            tech_node_nm=7,
            frequency_Hz=1e9,
        )
        ranking = opt.material_ranking(
            h_conv=1000,
            materials=["silicon", "pipeline_test"],
        )

        names = [r["material_name"] for r in ranking]
        assert "Pipeline Test" in names
        # Higher conductivity should allow higher density
        assert ranking[0]["material_name"] == "Pipeline Test"

    def test_custom_material_in_chip_simulation(self):
        """A custom material should work as chip substrate."""
        registry.register("chip_test", Material(
            name="Chip Test",
            thermal_conductivity=300.0,
            specific_heat=450.0,
            density=4000.0,
            electrical_resistivity=1e5,
            max_operating_temp=700.0,
        ))

        chip = ChipFloorplan(
            grid_shape=(10, 10, 2),
            material="chip_test",
        )
        chip.add_block(FunctionalBlock(
            name="core",
            x_range=(2, 8), y_range=(2, 8), z_range=(0, 2),
            gate_density=1e5,
            activity=0.3,
        ))

        # Should be able to simulate
        solver = chip.simulate(frequency_Hz=1e9, steps=10)
        assert solver.T.max() > 300  # some heating occurred
        assert solver.T.min() >= 299  # reasonable temperature
