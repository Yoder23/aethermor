"""
Tests for ThermalOptimizer inverse-design module.

Validates maximum density search, cooling requirement finder,
material ranking, cooling sweep, paradigm comparison,
thermal headroom map, power redistribution, and full design exploration.
"""

import math
import pytest
from analysis.thermal_optimizer import ThermalOptimizer
from physics.chip_floorplan import ChipFloorplan, FunctionalBlock


@pytest.fixture
def opt():
    """Create a small optimizer for fast tests."""
    return ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
        thermal_steps=200,
    )


class TestAnalyticalModel:
    """Verify the combined conduction + convection 1D model."""

    def test_T_max_above_ambient(self, opt):
        """With positive gate density, T_max should exceed ambient."""
        T = opt._analytical_T_max(1e5, "silicon", h_conv=1000.0)
        assert T > opt.T_ambient

    def test_T_max_increases_with_density(self, opt):
        """Higher gate density → higher temperature."""
        T_lo = opt._analytical_T_max(1e4, "silicon", h_conv=1000.0)
        T_hi = opt._analytical_T_max(1e6, "silicon", h_conv=1000.0)
        assert T_hi > T_lo

    def test_T_max_decreases_with_h(self, opt):
        """Higher cooling → lower temperature."""
        T_poor = opt._analytical_T_max(1e5, "silicon", h_conv=100.0)
        T_good = opt._analytical_T_max(1e5, "silicon", h_conv=10000.0)
        assert T_poor > T_good

    def test_conduction_floor(self, opt):
        """As h → ∞, T_max should approach the conduction floor, not ambient."""
        T_huge_h = opt._analytical_T_max(1e6, "silicon", h_conv=1e12)
        # Should be very close to T_ambient + Q·dx/(2·k·A)
        # but still above T_ambient
        assert T_huge_h > opt.T_ambient
        # And well below what a moderate h would give
        T_moderate = opt._analytical_T_max(1e6, "silicon", h_conv=1000.0)
        assert T_huge_h < T_moderate

    def test_material_affects_conduction_floor(self, opt):
        """Diamond should have lower conduction floor than silicon."""
        T_si = opt._analytical_T_max(1e6, "silicon", h_conv=1e12)
        T_dia = opt._analytical_T_max(1e6, "diamond", h_conv=1e12)
        assert T_dia < T_si  # Diamond has ~15× higher k


class TestFindMaxDensity:
    """Verify 3D binary search for max sustainable density."""

    def test_returns_positive_density(self, opt):
        """Should find a positive max density."""
        result = opt.find_max_density("silicon", h_conv=1000.0)
        assert result["max_density"] > 0

    def test_T_max_below_material_limit(self, opt):
        """T_max at found density should be at/below material limit."""
        result = opt.find_max_density("silicon", h_conv=1000.0)
        from physics.materials import get_material
        mat = get_material("silicon")
        # Allow small overshoot from binary search
        assert result["T_max_K"] <= mat.max_operating_temp + 5.0

    def test_diamond_higher_than_silicon(self, opt):
        """Diamond should sustain higher density than silicon."""
        si = opt.find_max_density("silicon", h_conv=1000.0)
        dia = opt.find_max_density("diamond", h_conv=1000.0)
        assert dia["max_density"] > si["max_density"]

    def test_result_has_required_keys(self, opt):
        """Result should contain all expected metrics."""
        result = opt.find_max_density("silicon")
        required = ["max_density", "T_max_K", "power_W",
                     "power_density_W_cm2", "landauer_gap",
                     "thermal_headroom_K"]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_adiabatic_higher_than_cmos(self, opt):
        """Adiabatic paradigm should allow higher density."""
        cmos = opt.find_max_density("silicon", paradigm="cmos")
        adiab = opt.find_max_density("silicon", paradigm="adiabatic")
        assert adiab["max_density"] >= cmos["max_density"]


class TestFindMinCooling:
    """Verify minimum cooling requirement finder."""

    def test_returns_dict(self, opt):
        """Should return a dict with min_h_conv."""
        result = opt.find_min_cooling("silicon", gate_density=1e5)
        assert isinstance(result, dict)
        assert "min_h_conv" in result

    def test_h_min_positive(self, opt):
        """Minimum h should be positive for non-zero density."""
        result = opt.find_min_cooling("silicon", gate_density=1e5)
        assert result["min_h_conv"] > 0

    def test_higher_density_needs_more_cooling(self, opt):
        """More gates → higher cooling requirement."""
        r_lo = opt.find_min_cooling("silicon", gate_density=1e4)
        r_hi = opt.find_min_cooling("silicon", gate_density=1e5)
        assert r_hi["min_h_conv"] > r_lo["min_h_conv"]

    def test_conduction_floor_reported(self, opt):
        """Result should include conduction floor temperature."""
        result = opt.find_min_cooling("silicon", gate_density=1e5)
        assert "conduction_floor_K" in result
        assert result["conduction_floor_K"] > opt.T_ambient

    def test_impossible_when_conduction_limited(self, opt):
        """Very high density should be conduction-limited (h_min = inf)."""
        # Extremely high density on a poor conductor
        result = opt.find_min_cooling("gallium_arsenide", gate_density=1e10)
        # Should either be inf or very large
        assert result["min_h_conv"] > 1e6 or result["min_h_conv"] == float('inf')

    def test_cooling_category_string(self, opt):
        """Should classify the cooling requirement."""
        result = opt.find_min_cooling("silicon", gate_density=1e4)
        assert "cooling_category" in result
        assert isinstance(result["cooling_category"], str)


class TestMaterialRanking:
    """Verify material ranking by max density."""

    def test_returns_sorted_list(self, opt):
        """Should return a list sorted by density (descending)."""
        ranking = opt.material_ranking(h_conv=1000.0)
        assert len(ranking) >= 3
        densities = [r["max_density"] for r in ranking]
        for i in range(len(densities) - 1):
            assert densities[i] >= densities[i + 1]

    def test_diamond_ranks_first(self, opt):
        """Diamond should rank highest at standard cooling."""
        ranking = opt.material_ranking(h_conv=1000.0)
        assert ranking[0]["material"] == "diamond"

    def test_format_material_ranking(self, opt):
        """format_material_ranking should return a readable table."""
        text = opt.format_material_ranking()
        assert isinstance(text, str)
        assert "Diamond" in text or "diamond" in text


class TestCoolingSweep:
    """Verify cooling coefficient sweep."""

    def test_returns_list(self, opt):
        """Should return a list of results."""
        sweep = opt.cooling_sweep("silicon", gate_density=1e5)
        assert isinstance(sweep, list)
        assert len(sweep) > 0

    def test_temperature_decreases_with_h(self, opt):
        """Higher h should give lower T_max."""
        sweep = opt.cooling_sweep("silicon", gate_density=1e5)
        temps = [s["T_max_K"] for s in sweep]
        for i in range(len(temps) - 1):
            assert temps[i] >= temps[i + 1] - 1e-6

    def test_conduction_floor_visible(self, opt):
        """At very high h, temperature should plateau (conduction floor)."""
        sweep = opt.cooling_sweep(
            "silicon", gate_density=1e4,
            h_values=[1000, 10000, 100000, 1000000, 10000000],
        )
        temps = [s["T_max_K"] for s in sweep]
        # Last two should be very close (approaching floor)
        assert abs(temps[-1] - temps[-2]) < abs(temps[0] - temps[1])

    def test_each_entry_has_status(self, opt):
        """Each sweep entry should indicate safe/runaway."""
        sweep = opt.cooling_sweep("silicon", gate_density=1e4)
        for s in sweep:
            assert "safe" in s
            assert "runaway" in s


class TestParadigmComparison:
    """Verify CMOS vs adiabatic density comparison."""

    def test_returns_both_paradigms(self, opt):
        """Should return data for both CMOS and adiabatic."""
        comp = opt.paradigm_density_comparison("silicon")
        assert "cmos" in comp
        assert "adiabatic" in comp
        assert "adiabatic_advantage_ratio" in comp

    def test_adiabatic_advantage_positive(self, opt):
        """Adiabatic should have ratio >= 1."""
        comp = opt.paradigm_density_comparison("silicon")
        assert comp["adiabatic_advantage_ratio"] >= 1.0

    def test_comparison_across_materials(self, opt):
        """Comparison should work for different materials."""
        for mat in ["silicon", "diamond"]:
            comp = opt.paradigm_density_comparison(mat)
            assert comp["cmos"]["max_density"] > 0
            assert comp["adiabatic"]["max_density"] >= comp["cmos"]["max_density"]


# ── Fixtures for floorplan-based tests ──────────────────────


@pytest.fixture
def soc():
    """A small modern SoC floorplan for testing."""
    return ChipFloorplan.modern_soc(
        grid_shape=(10, 10, 3), element_size_m=500e-6,
    )


class TestThermalHeadroomMap:
    """Verify per-block thermal headroom analysis."""

    def test_returns_list_per_block(self, opt, soc):
        """Should return one result per block in the floorplan."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        assert len(results) == len(soc.blocks)

    def test_block_names_match(self, opt, soc):
        """Result names should match floorplan block names."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        names = {r["name"] for r in results}
        expected = {b.name for b in soc.blocks}
        assert names == expected

    def test_T_max_above_ambient(self, opt, soc):
        """All blocks with non-zero density should be above ambient."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        for r in results:
            if r["gate_density"] > 0:
                assert r["T_max_K"] >= opt.T_ambient

    def test_headroom_is_positive(self, opt, soc):
        """All blocks should have positive thermal headroom (within limits)."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        for r in results:
            assert r["thermal_headroom_K"] > 0

    def test_bottleneck_identified(self, opt, soc):
        """Exactly one block should be the bottleneck (or all tied)."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        bottlenecks = [r for r in results if r["is_bottleneck"]]
        assert len(bottlenecks) >= 1

    def test_density_headroom_factor(self, opt, soc):
        """Blocks with low density should have larger headroom factor."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        for r in results:
            assert r["density_headroom_factor"] >= 1.0

    def test_recommended_action_present(self, opt, soc):
        """Every result should have a recommended_action string."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        for r in results:
            assert isinstance(r["recommended_action"], str)
            assert len(r["recommended_action"]) > 0

    def test_result_keys_complete(self, opt, soc):
        """Each result should contain all expected keys."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        required = [
            "name", "paradigm", "gate_density", "T_max_K", "T_mean_K",
            "thermal_headroom_K", "is_bottleneck",
            "density_headroom_factor", "recommended_action",
        ]
        for r in results:
            for key in required:
                assert key in r, f"Missing key: {key}"

    def test_io_has_more_headroom_than_cpu(self, opt, soc):
        """I/O (low power) should have more headroom than CPU (high power)."""
        results = opt.thermal_headroom_map(soc, h_conv=1000.0)
        cpu = next(r for r in results if r["name"] == "CPU_cluster")
        io = next(r for r in results if r["name"] == "IO_memctrl")
        assert io["density_headroom_factor"] > cpu["density_headroom_factor"]


class TestOptimizePowerDistribution:
    """Verify power redistribution optimiser."""

    def test_improvement_ratio_positive(self, opt, soc):
        """Improvement ratio should be > 0."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        assert result["improvement_ratio"] > 0

    def test_improvement_ratio_above_one(self, opt, soc):
        """With enough power budget, optimised should beat original."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        # The original layout is suboptimal — optimiser should improve it
        assert result["improvement_ratio"] >= 1.0

    def test_power_within_budget(self, opt, soc):
        """Total power should not exceed the budget."""
        budget = 50.0
        result = opt.optimize_power_distribution(
            soc, power_budget_W=budget, h_conv=1000.0,
        )
        assert result["total_power_W"] <= budget + 0.01

    def test_thermal_limit_respected(self, opt, soc):
        """All block temperatures should be within the thermal limit."""
        from physics.materials import get_material
        mat = get_material(soc.material)
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        for b in result["optimised_blocks"]:
            assert b["T_estimated_K"] <= mat.max_operating_temp + 1.0

    def test_binding_constraint_reported(self, opt, soc):
        """Result should report whether thermal or power is binding."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        assert result["binding_constraint"] in ("thermal", "power")

    def test_tight_budget_is_power_limited(self, opt, soc):
        """A very small power budget should be power-limited."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=0.001, h_conv=1000.0,
        )
        assert result["binding_constraint"] == "power"
        assert result["total_power_W"] <= 0.002

    def test_huge_budget_is_thermal_limited(self, opt, soc):
        """A very large power budget should be thermal-limited."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=1e6, h_conv=1000.0,
        )
        assert result["binding_constraint"] == "thermal"

    def test_all_blocks_have_required_keys(self, opt, soc):
        """Each optimised block should have all required output keys."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        required = [
            "name", "paradigm", "original_density", "optimised_density",
            "density_change", "power_W", "throughput_ops_s",
            "T_estimated_K", "thermal_headroom_K",
        ]
        for b in result["optimised_blocks"]:
            for key in required:
                assert key in b, f"Missing key: {key}"

    def test_optimised_densities_positive(self, opt, soc):
        """All optimised densities should be positive."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        for b in result["optimised_blocks"]:
            assert b["optimised_density"] > 0

    def test_underutilised_blocks_increase(self, opt, soc):
        """Blocks with low original density should get higher optimised density."""
        result = opt.optimize_power_distribution(
            soc, power_budget_W=50.0, h_conv=1000.0,
        )
        io = next(b for b in result["optimised_blocks"]
                  if b["name"] == "IO_memctrl")
        # IO had very low original density (1e4) — should increase
        assert io["density_change"] > 1.0


class TestFullDesignExploration:
    """Verify the one-call complete design exploration."""

    def test_returns_all_keys(self, opt):
        """Result should contain all component analyses."""
        result = opt.full_design_exploration("silicon", h_conv=1000.0)
        required = [
            "material_ranking", "best_material", "max_density",
            "cooling_requirement", "paradigm_comparison",
            "cooling_sweep", "insights",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_insights_non_empty(self, opt):
        """Should produce at least one insight."""
        result = opt.full_design_exploration("silicon", h_conv=1000.0)
        assert isinstance(result["insights"], list)
        assert len(result["insights"]) >= 1

    def test_best_material_is_diamond(self, opt):
        """Diamond should rank as best material at standard cooling."""
        result = opt.full_design_exploration("silicon", h_conv=1000.0)
        assert "diamond" in result["best_material"]["material"].lower() or \
               "Diamond" in result["best_material"]["material_name"]

    def test_max_density_positive(self, opt):
        """Max density on silicon should be positive."""
        result = opt.full_design_exploration("silicon")
        assert result["max_density"]["max_density"] > 0

    def test_paradigm_comparison_present(self, opt):
        """Paradigm comparison should show adiabatic advantage."""
        result = opt.full_design_exploration("silicon")
        assert result["paradigm_comparison"]["adiabatic_advantage_ratio"] >= 1.0

    def test_cooling_sweep_has_entries(self, opt):
        """Cooling sweep should return multiple data points."""
        result = opt.full_design_exploration("silicon")
        assert len(result["cooling_sweep"]) >= 3
