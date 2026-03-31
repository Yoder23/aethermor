"""
Tests for TechnologyRoadmap analysis module.

Validates technology node projections, Landauer gap tracking,
paradigm crossover detection, and thermal wall calculations.
"""

import pytest
from aethermor.analysis.tech_roadmap import TechnologyRoadmap


class TestTechnologyRoadmap:
    """Verify technology roadmap projections."""

    @pytest.fixture
    def roadmap(self):
        return TechnologyRoadmap()

    def test_energy_roadmap_returns_list(self, roadmap):
        """energy_roadmap should return a non-empty list."""
        data = roadmap.energy_roadmap()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_energy_roadmap_has_expected_keys(self, roadmap):
        """Each row should have node_nm, E_cmos, etc."""
        data = roadmap.energy_roadmap()
        row = data[0]
        for key in ["node_nm", "E_cmos_J", "E_adiabatic_J",
                     "E_reversible_J", "E_landauer_J"]:
            assert key in row, f"Missing key: {key}"

    def test_energy_decreases_with_shrinking_node(self, roadmap):
        """CMOS energy should generally decrease at smaller nodes."""
        data = roadmap.energy_roadmap()
        # Compare first (largest) and last (smallest) nodes
        E_large = data[0]["E_cmos_J"]
        E_small = data[-1]["E_cmos_J"]
        assert E_large > E_small

    def test_cmos_always_above_landauer(self, roadmap):
        """CMOS energy should always exceed the Landauer limit."""
        data = roadmap.energy_roadmap()
        for row in data:
            assert row["E_cmos_J"] > row["E_landauer_J"], \
                f"CMOS below Landauer at {row['node_nm']} nm"

    def test_gap_closure_returns_list(self, roadmap):
        """gap_closure_projection should return a non-empty list."""
        data = roadmap.gap_closure_projection()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_gap_closure_has_ratio(self, roadmap):
        """Each entry should have gap_cmos field."""
        data = roadmap.gap_closure_projection()
        for row in data:
            assert "gap_cmos" in row

    def test_gap_ratio_decreases_at_smaller_nodes(self, roadmap):
        """Landauer gap ratio should decrease as nodes shrink."""
        data = roadmap.gap_closure_projection()
        first = data[0]["gap_cmos"]
        last = data[-1]["gap_cmos"]
        assert first > last

    def test_paradigm_crossover_returns_list(self, roadmap):
        """paradigm_crossover_map should return a non-empty list."""
        data = roadmap.paradigm_crossover_map()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_paradigm_crossover_has_winner(self, roadmap):
        """Each crossover entry should declare a winner at 1 GHz."""
        data = roadmap.paradigm_crossover_map()
        for row in data:
            assert "winner_at_1GHz" in row
            assert row["winner_at_1GHz"] in ["cmos", "adiabatic", "reversible"]

    def test_thermal_wall_returns_list(self, roadmap):
        """thermal_wall_roadmap should return a non-empty list."""
        data = roadmap.thermal_wall_roadmap()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_thermal_wall_has_density(self, roadmap):
        """Each thermal wall entry should have max density."""
        data = roadmap.thermal_wall_roadmap()
        for row in data:
            assert "max_gate_density" in row
            assert row["max_gate_density"] > 0

    def test_diamond_higher_thermal_wall(self, roadmap):
        """Diamond should sustain higher density than silicon."""
        data = roadmap.thermal_wall_roadmap()
        # Find silicon and diamond entries for the same node
        si_entries = {d["node_nm"]: d for d in data
                      if d["material"] == "silicon"}
        dia_entries = {d["node_nm"]: d for d in data
                       if d["material"] == "diamond"}
        common_nodes = set(si_entries) & set(dia_entries)
        assert len(common_nodes) > 0
        for node in common_nodes:
            assert dia_entries[node]["max_gate_density"] >= \
                   si_entries[node]["max_gate_density"]


class TestTechnologyRoadmapOutput:
    """Verify formatted output methods."""

    @pytest.fixture
    def roadmap(self):
        return TechnologyRoadmap()

    def test_full_report_returns_string(self, roadmap):
        """full_report should return a non-empty string."""
        report = roadmap.full_report()
        assert isinstance(report, str)
        assert len(report) > 100

    def test_format_energy_roadmap(self, roadmap):
        """format_energy_roadmap should mention technology nodes."""
        text = roadmap.format_energy_roadmap()
        assert "nm" in text.lower() or "node" in text.lower()

    def test_format_gap_closure(self, roadmap):
        """format_gap_closure should mention Landauer."""
        text = roadmap.format_gap_closure()
        assert "landauer" in text.lower() or "gap" in text.lower()
