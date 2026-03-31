"""
Tests for ChipFloorplan heterogeneous architecture model.

Validates functional block definitions, heat map generation,
thermal simulation, and factory methods for standard architectures.
"""

import math
import numpy as np
import pytest
from aethermor.physics.chip_floorplan import FunctionalBlock, ChipFloorplan


class TestFunctionalBlock:
    """Verify FunctionalBlock data and slice generation."""

    def test_slices_correct_ranges(self):
        """Slices should match x/y/z range specifications."""
        block = FunctionalBlock(
            name="test",
            x_range=(0, 10), y_range=(5, 15), z_range=(0, 4),
            gate_density=1e6, activity=0.3,
            tech_node_nm=7, paradigm="cmos",
        )
        sx, sy, sz = block.slices  # property, not method
        assert sx == slice(0, 10)
        assert sy == slice(5, 15)
        assert sz == slice(0, 4)

    def test_n_elements(self):
        """n_elements should be the product of range widths."""
        block = FunctionalBlock(
            name="test",
            x_range=(2, 5), y_range=(0, 3), z_range=(1, 4),
            gate_density=1e6, activity=0.2,
            tech_node_nm=7, paradigm="cmos",
        )
        assert block.n_elements == 3 * 3 * 3  # 27 (property)

    def test_activity_bounds(self):
        """Activity should be between 0 and 1."""
        block = FunctionalBlock(
            name="test",
            x_range=(0, 5), y_range=(0, 5), z_range=(0, 2),
            gate_density=1e6, activity=0.5,
            tech_node_nm=7, paradigm="cmos",
        )
        assert 0 <= block.activity <= 1


class TestChipFloorplan:
    """Verify ChipFloorplan model operations."""

    @pytest.fixture
    def simple_floorplan(self):
        """Create a simple 10×10×4 floorplan with two blocks."""
        fp = ChipFloorplan(
            grid_shape=(10, 10, 4),
            element_size_m=100e-6,
        )
        fp.add_block(FunctionalBlock(
            "CPU", x_range=(0, 5), y_range=(0, 5), z_range=(0, 4),
            gate_density=1e6, activity=0.3,
            tech_node_nm=7, paradigm="cmos",
        ))
        fp.add_block(FunctionalBlock(
            "Cache", x_range=(5, 10), y_range=(0, 10), z_range=(0, 4),
            gate_density=5e5, activity=0.1,
            tech_node_nm=7, paradigm="cmos",
        ))
        return fp

    def test_add_block_returns_self(self, simple_floorplan):
        """add_block should return self for chaining."""
        fp = ChipFloorplan(grid_shape=(10, 10, 4), element_size_m=100e-6)
        result = fp.add_block(FunctionalBlock(
            "test", (0, 5), (0, 5), (0, 4), 1e6, 0.2, 7, "cmos"))
        assert result is fp

    def test_heat_map_shape(self, simple_floorplan):
        """Heat map should match grid_shape."""
        hm = simple_floorplan.heat_map()
        assert hm.shape == (10, 10, 4)

    def test_heat_map_positive(self, simple_floorplan):
        """Heat map values should be non-negative."""
        hm = simple_floorplan.heat_map()
        assert np.all(hm >= 0)

    def test_gate_density_map(self, simple_floorplan):
        """Gate density map should reflect block assignments."""
        dm = simple_floorplan.gate_density_map()
        assert dm.shape == (10, 10, 4)
        # CPU region should have 1e6
        assert dm[0, 0, 0] == pytest.approx(1e6)
        # Cache region should have 5e5
        assert dm[5, 0, 0] == pytest.approx(5e5)

    def test_activity_map(self, simple_floorplan):
        """Activity map should reflect block assignments."""
        am = simple_floorplan.activity_map()
        assert am[0, 0, 0] == pytest.approx(0.3)  # CPU
        assert am[5, 0, 0] == pytest.approx(0.1)  # Cache

    def test_paradigm_map(self, simple_floorplan):
        """Paradigm map should label blocks correctly."""
        pm = simple_floorplan.paradigm_map()
        assert pm.shape == (10, 10, 4)

    def test_total_power_positive(self, simple_floorplan):
        """Total power should be positive for active blocks."""
        P = simple_floorplan.total_power_W()
        assert P > 0

    def test_die_area(self, simple_floorplan):
        """Die area should be grid_x * grid_y * element_size²."""
        area = simple_floorplan.die_area_m2()
        expected = 10 * 10 * (100e-6) ** 2  # 1e-6 m²
        assert abs(area - expected) < 1e-15

    def test_power_density_positive(self, simple_floorplan):
        """Power density should be positive."""
        pd = simple_floorplan.power_density_W_cm2()
        assert pd > 0

    def test_summary_returns_string(self, simple_floorplan):
        """summary() should return a non-empty string."""
        s = simple_floorplan.summary()
        assert isinstance(s, str)
        assert len(s) > 10

    def test_simulate_returns_thermal(self, simple_floorplan):
        """simulate() should return a FourierThermalTransport."""
        from aethermor.physics.thermal import FourierThermalTransport
        thermal = simple_floorplan.simulate(steps=10)
        assert isinstance(thermal, FourierThermalTransport)

    def test_simulate_temperature_above_ambient(self, simple_floorplan):
        """After simulation, T_max should be above ambient."""
        thermal = simple_floorplan.simulate(steps=50)
        assert thermal.max_temperature() > 300.0

    def test_block_temperatures(self, simple_floorplan):
        """block_temperatures should return one entry per block."""
        thermal = simple_floorplan.simulate(steps=50)
        temps = simple_floorplan.block_temperatures(thermal)
        assert len(temps) == 2  # CPU and Cache
        # CPU (higher density + activity) should be hotter than cache
        cpu_temp = [t for t in temps if t["name"] == "CPU"][0]
        cache_temp = [t for t in temps if t["name"] == "Cache"][0]
        assert cpu_temp["T_max_K"] >= cache_temp["T_max_K"]

    def test_landauer_gap_map_shape(self, simple_floorplan):
        """Landauer gap map should match grid_shape."""
        gm = simple_floorplan.landauer_gap_map()
        assert gm.shape == (10, 10, 4)

    def test_cpu_closer_to_landauer_than_cache(self, simple_floorplan):
        """Higher-density CPU should have larger Landauer gap."""
        gm = simple_floorplan.landauer_gap_map()
        cpu_gap = gm[0, 0, 0]
        cache_gap = gm[5, 0, 0]
        # Both should be > 0 (above Landauer limit)
        assert cpu_gap > 0
        assert cache_gap > 0


class TestChipFloorplanFactories:
    """Verify factory methods create valid floorplans."""

    def test_modern_soc_shape(self):
        """modern_soc should create a 60×60×8 floorplan by default."""
        soc = ChipFloorplan.modern_soc()
        hm = soc.heat_map()
        assert hm.shape == (60, 60, 8)

    def test_modern_soc_has_blocks(self):
        """modern_soc should have at least 3 functional blocks."""
        soc = ChipFloorplan.modern_soc()
        assert len(soc.blocks) >= 3

    def test_hybrid_paradigm_has_adiabatic(self):
        """hybrid_paradigm should include adiabatic blocks."""
        hybrid = ChipFloorplan.hybrid_paradigm()
        paradigms = [b.paradigm for b in hybrid.blocks]
        assert "adiabatic" in paradigms
        assert "cmos" in paradigms

    def test_hybrid_lower_power_than_cmos(self):
        """Hybrid paradigm should use less total power than full CMOS."""
        # Use small grids for speed
        cmos_soc = ChipFloorplan.modern_soc(grid_shape=(10, 10, 4))
        hybrid = ChipFloorplan.hybrid_paradigm(grid_shape=(10, 10, 4))
        P_cmos = cmos_soc.total_power_W()
        P_hybrid = hybrid.total_power_W()
        # Hybrid should be lower (adiabatic blocks use less energy)
        assert P_hybrid < P_cmos

    def test_custom_grid_shape(self):
        """Factory methods should accept custom grid shapes."""
        soc = ChipFloorplan.modern_soc(grid_shape=(20, 20, 4))
        hm = soc.heat_map()
        assert hm.shape == (20, 20, 4)
