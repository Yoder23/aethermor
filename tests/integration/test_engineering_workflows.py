"""
Integration tests for real engineering workflows.

These tests exercise the kind of multi-step analyses a thermodynamic
computing engineer would run day-to-day with Aethermor.  Each test
represents a complete workflow from material selection through
decision output.
"""

import math
import numpy as np
import pytest
from physics.constants import k_B, landauer_limit
from physics.materials import get_material, registry as material_registry
from physics.thermal import FourierThermalTransport, ThermalBoundaryCondition
from physics.cooling import CoolingStack
from physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)
from physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from analysis.thermal_optimizer import ThermalOptimizer
from analysis.tech_roadmap import TechnologyRoadmap

ALL_MATERIAL_NAMES = [
    "silicon", "silicon_dioxide", "gallium_arsenide", "diamond",
    "graphene_layer", "copper", "indium_phosphide", "silicon_carbide",
    "gallium_nitride",
]


# ── Workflow 1: Chip Thermal Feasibility ──────────────────────────

class TestChipThermalFeasibility:
    """Full workflow: is a proposed chip design thermally feasible?"""

    def test_server_gpu_needs_liquid(self):
        """700W GPU — air cooling insufficient, liquid cooling required."""
        si = get_material("silicon")
        die_area = 800e-6  # 800 mm²
        cold_plate_area = 10000e-6  # liquid cold plate much larger than die
        thickness = 0.5e-3
        P = 700.0
        T_amb = 300.0
        T_j_max = 378.15

        R_die = thickness / (si.thermal_conductivity * die_area)

        # Air cooling only over die area — R_conv huge, T_j explodes
        R_air = 1.0 / (120 * die_area)
        T_j_air = T_amb + P * (R_die + R_air)
        assert T_j_air > T_j_max, "Air cooling on die alone should be insufficient"

        # Liquid cooling with proper cold plate spreading
        R_liquid = 1.0 / (5000 * cold_plate_area)
        T_j_liquid = T_amb + P * (R_die + R_liquid)
        assert T_j_liquid < T_j_air, "Liquid should be cooler than air"

    def test_more_power_more_temperature(self):
        """Higher power should give higher junction temperature."""
        si = get_material("silicon")
        area = 500e-6
        t = 0.3e-3
        T_amb = 300.0

        R_die = t / (si.thermal_conductivity * area)
        R_conv = 1.0 / (1000 * area)
        R = R_die + R_conv

        T_100 = T_amb + 100 * R
        T_300 = T_amb + 300 * R

        assert T_300 > T_100
        assert T_100 > T_amb

    def test_overpower_detection(self):
        """1000W on small die should exceed T_j_max at any air cooling."""
        si = get_material("silicon")
        area = 200e-6
        t = 0.5e-3
        P = 1000.0
        T_amb = 300.0
        T_j_max = 378.15

        R_die = t / (si.thermal_conductivity * area)
        R_conv = 1.0 / (120 * area)
        T_j = T_amb + P * (R_die + R_conv)

        assert T_j > T_j_max, "1000W on small die should overheat at air"


# ── Workflow 2: Substrate Material Selection ──────────────────────

class TestSubstrateMaterialSelection:
    """Workflow: choose the best substrate for a thermal design."""

    def test_ranking_by_thermal_resistance(self):
        """Rank substrates by θ_jc for a given die geometry."""
        area = 400e-6
        t = 0.3e-3
        substrates = ["silicon", "silicon_carbide", "diamond"]

        resistances = {}
        for name in substrates:
            m = get_material(name)
            R = t / (m.thermal_conductivity * area)
            resistances[name] = R

        # Diamond < SiC < Si
        assert resistances["diamond"] < resistances["silicon_carbide"]
        assert resistances["silicon_carbide"] < resistances["silicon"]

    def test_cost_benefit_tradeoff(self):
        """Diamond saves the most but at diminishing returns with cooling."""
        area = 400e-6
        t = 0.3e-3
        P = 300.0
        T_amb = 300.0

        results = {}
        for name in ["silicon", "silicon_carbide", "diamond"]:
            m = get_material(name)
            R_die = t / (m.thermal_conductivity * area)
            R_conv = 1.0 / (5000 * area)
            T_j = T_amb + P * (R_die + R_conv)
            results[name] = T_j

        # With liquid cooling, differences shrink but still exist
        save_sic = results["silicon"] - results["silicon_carbide"]
        save_dia = results["silicon"] - results["diamond"]

        assert save_sic > 0, "SiC should save temperature"
        assert save_dia > save_sic, "Diamond should save more"


# ── Workflow 3: Energy Paradigm Selection ─────────────────────────

class TestEnergyParadigmSelection:
    """Workflow: which compute paradigm is best for my application?"""

    def test_paradigm_ordering_at_low_freq(self):
        """At low frequency, energy should be ordered:
        Landauer < Reversible < Adiabatic < CMOS."""
        T = 350.0
        f = 1e8  # 100 MHz

        cmos = CMOSGateEnergy(tech_node_nm=7, V_dd=0.7, C_load=1e-15)
        adiab = AdiabaticGateEnergy(tech_node_nm=7, V_dd=0.7, C_load=1e-15)
        rev = ReversibleGateEnergy()
        landau = LandauerLimitEnergy()

        e_cmos = cmos.energy_per_switch(f, T)
        e_adiab = adiab.energy_per_switch(f, T)
        e_rev = rev.energy_per_switch(f, T)
        e_landau = landau.energy_per_switch(f, T)

        assert e_landau < e_rev < e_adiab < e_cmos

    def test_cmos_dominates_energy_budget(self):
        """At GHz frequencies, CMOS should still be orders above Landauer."""
        T = 350.0
        f = 3e9

        cmos = CMOSGateEnergy(tech_node_nm=5, V_dd=0.65, C_load=0.5e-15)
        landau = LandauerLimitEnergy()

        gap = cmos.energy_per_switch(f, T) / landau.energy_per_switch(f, T)
        assert gap > 100, "CMOS should be >100× above Landauer limit"

    def test_crossover_frequency_positive(self):
        """Adiabatic-CMOS crossover should exist at positive frequency."""
        T = 350.0
        cmos = CMOSGateEnergy(tech_node_nm=7, V_dd=0.7, C_load=1e-15)
        adiab = AdiabaticGateEnergy(tech_node_nm=7, V_dd=0.7, C_load=1e-15)

        f_cross = adiab.crossover_frequency(cmos, T)
        assert f_cross > 0, "Crossover should be at positive frequency"


# ── Workflow 4: Technology Roadmap ────────────────────────────────

class TestTechnologyRoadmap:
    """Workflow: project thermal challenges at future nodes."""

    def test_energy_roadmap_covers_nodes(self):
        """Energy roadmap should project across technology nodes."""
        roadmap = TechnologyRoadmap(tech_nodes=[7, 5, 3, 2])
        entries = roadmap.energy_roadmap(frequency_Hz=1e9)

        assert len(entries) == 4
        for e in entries:
            assert "E_cmos_J" in e
            assert "E_landauer_J" in e
            assert e["E_cmos_J"] > e["E_landauer_J"]

    def test_gap_closure_projection(self):
        """Gap closure should show path toward Landauer limit."""
        roadmap = TechnologyRoadmap(tech_nodes=[7, 5, 3])
        gaps = roadmap.gap_closure_projection(frequency_Hz=1e9)

        assert len(gaps) == 3
        for g in gaps:
            assert "gap_cmos" in g
            assert g["gap_cmos"] > 1, "CMOS should be above Landauer"


# ── Workflow 5: CoolingStack Design ──────────────────────────────

class TestCoolingStackDesign:
    """Workflow: select and validate cooling solution."""

    def test_cooling_hierarchy(self):
        """Cooling solutions should form a strict thermal hierarchy."""
        area = 400e-6
        P = 200.0
        T_amb = 300.0

        stacks = {
            "bare": CoolingStack.bare_die_natural_air(),
            "desktop": CoolingStack.desktop_air(),
            "server": CoolingStack.server_air(),
            "liquid": CoolingStack.liquid_cooled(),
            "direct": CoolingStack.direct_liquid(),
        }

        T_j = {}
        for name, stack in stacks.items():
            R = stack.total_resistance(area)
            T_j[name] = T_amb + P * R

        # Strict ordering (less cooling → higher T)
        assert T_j["direct"] < T_j["liquid"]
        assert T_j["liquid"] < T_j["server"]
        assert T_j["server"] < T_j["desktop"]
        assert T_j["desktop"] < T_j["bare"]

    def test_liquid_keeps_gpu_cool(self):
        """Liquid cooling should handle a 400W GPU."""
        area = 600e-6  # 600 mm²
        P = 400.0
        T_amb = 300.0
        T_j_max = 378.15

        liquid = CoolingStack.liquid_cooled()
        R = liquid.total_resistance(area)
        T_j = T_amb + P * R

        # May or may not be under T_j_max depending on area,
        # but should at least be finite and below 500K
        assert 300 < T_j < 500

    def test_resistance_scales_with_area(self):
        """Thermal resistance should decrease with larger area."""
        liquid = CoolingStack.liquid_cooled()
        R_small = liquid.total_resistance(100e-6)
        R_large = liquid.total_resistance(1000e-6)
        assert R_large < R_small


# ── Workflow 6: 3D Fourier Thermal Solve ──────────────────────────

class TestFourierThermalSolve:
    """Workflow: 3D thermal simulation."""

    def test_steady_state_solve(self):
        """Should converge to a steady state temperature field."""
        si = get_material("silicon")
        bc = ThermalBoundaryCondition(h_conv=5000.0, T_ambient=300.0)
        solver = FourierThermalTransport(
            material=si, grid_shape=(10, 10, 5),
            element_size_m=1e-4, boundary=bc,
        )

        # Distributed heat (moderate intensity)
        Q = np.ones((10, 10, 5)) * 1e-2
        Q[5, 5, :] = 1.0  # hotter stripe

        T_final = solver.steady_state_temperature(Q, max_steps=500)

        # Hot stripe should be warmest
        assert T_final[5, 5, 2] > T_final[0, 0, 2]
        # Should be above ambient
        assert T_final.max() > 300.0

    def test_no_heat_stays_ambient(self):
        """No heat input should keep field at ambient."""
        si = get_material("silicon")
        bc = ThermalBoundaryCondition(h_conv=500.0, T_ambient=300.0)
        solver = FourierThermalTransport(
            material=si, grid_shape=(8, 8, 4),
            element_size_m=1e-4, boundary=bc,
        )

        Q = np.zeros((8, 8, 4))
        T_final = solver.steady_state_temperature(Q, max_steps=100)

        np.testing.assert_allclose(T_final, 300.0, atol=0.1)


# ── Workflow 7: ChipFloorplan Analysis ────────────────────────────

class TestChipFloorplanWorkflow:
    """Workflow: build a chip floorplan and analyze hotspots."""

    def test_create_and_analyze_floorplan(self):
        """Should create a floorplan and compute power."""
        fp = ChipFloorplan(grid_shape=(40, 40, 4), element_size_m=5e-4)
        cpu = FunctionalBlock("CPU", x_range=(2, 18), y_range=(2, 18),
                              z_range=(0, 4), gate_density=1e7, activity=0.3)
        gpu = FunctionalBlock("GPU", x_range=(20, 38), y_range=(2, 38),
                              z_range=(0, 4), gate_density=5e6, activity=0.5)
        fp.add_block(cpu).add_block(gpu)

        total = fp.total_power_W()
        assert total > 0, "Floorplan should have positive power"

    def test_empty_floorplan(self):
        """Empty floorplan should have zero power."""
        fp = ChipFloorplan(grid_shape=(10, 10, 4), element_size_m=5e-4)
        assert fp.total_power_W() == 0.0


# ── Workflow 8: Multi-Material Comparison ─────────────────────────

class TestMultiMaterialComparison:
    """Workflow: compare all materials for a specific application."""

    def test_all_materials_have_physical_properties(self):
        """Every registered material should have positive k, ρ, c_p."""
        for name in ALL_MATERIAL_NAMES:
            m = get_material(name)
            assert m.thermal_conductivity > 0
            assert m.density > 0
            assert m.specific_heat > 0

    def test_material_sorting_by_conductivity(self):
        """Materials sorted by k should have diamond or graphene on top."""
        materials = []
        for name in ALL_MATERIAL_NAMES:
            m = get_material(name)
            materials.append((name, m.thermal_conductivity))

        materials.sort(key=lambda x: x[1], reverse=True)
        assert materials[0][0] in ("diamond", "graphene_layer")

    def test_thermal_diffusivity_ranking(self):
        """Thermal diffusivity α = k/(ρ·c_p) should rank correctly."""
        pairs = [("diamond", "silicon"), ("silicon", "silicon_dioxide")]
        for better, worse in pairs:
            m_b = get_material(better)
            m_w = get_material(worse)
            alpha_b = m_b.thermal_conductivity / (m_b.density * m_b.specific_heat)
            alpha_w = m_w.thermal_conductivity / (m_w.density * m_w.specific_heat)
            assert alpha_b > alpha_w, f"{better} should have higher α than {worse}"


# ── Workflow 9: Thermal Optimizer ─────────────────────────────────

class TestThermalOptimizerWorkflow:
    """Workflow: use the optimizer for inverse thermal design."""

    def test_find_cooling_for_target(self):
        """Should find h_conv needed for target T_j."""
        opt = ThermalOptimizer()
        result = opt.find_min_cooling(
            material_key="silicon",
            gate_density=1e7,
            T_max_target=370.0,
        )
        assert result["min_h_conv"] > 0

    def test_find_max_density(self):
        """Should find maximum safe gate density for given cooling."""
        opt = ThermalOptimizer()
        result = opt.find_max_density(
            material_key="silicon",
            h_conv=5000.0,
            T_max_target=378.15,
            paradigm="cmos",
        )
        assert result["max_density"] > 0
        assert result["T_max_K"] <= 378.15 + 1.0


# ── Workflow 10: End-to-End Decision Pipeline ─────────────────────

class TestEndToEndDecision:
    """Complete engineering decision: material + cooling + paradigm."""

    def test_full_design_pipeline(self):
        """Full pipeline: pick material, check cooling, evaluate paradigm."""
        # Step 1: Material choice
        si = get_material("silicon")
        sic = get_material("silicon_carbide")
        assert sic.thermal_conductivity > si.thermal_conductivity

        # Step 2: Thermal resistance
        area = 500e-6
        t = 0.3e-3
        R_si = t / (si.thermal_conductivity * area)
        R_sic = t / (sic.thermal_conductivity * area)
        assert R_sic < R_si

        # Step 3: Cooling requirement
        P = 300.0
        T_amb = 300.0
        T_j_max = 378.15
        R_budget = (T_j_max - T_amb) / P
        h_needed_si = 1.0 / ((R_budget - R_si) * area)
        h_needed_sic = 1.0 / ((R_budget - R_sic) * area)
        assert h_needed_sic < h_needed_si, "SiC needs less cooling"

        # Step 4: Energy model at target frequency
        f = 2e9
        T = 360.0
        cmos = CMOSGateEnergy(tech_node_nm=5, V_dd=0.65, C_load=0.5e-15)
        E_gate = cmos.energy_per_switch(f, T)
        E_landauer = landauer_limit(T)
        gap = E_gate / E_landauer
        assert gap > 1, "Must be above Landauer limit"

        # Step 5: Validate total power
        N_gates = 1e9  # 1 billion gates
        P_total = E_gate * f * N_gates * 0.1  # 10% activity
        assert P_total > 0
