"""
Tests for Landauer gap analysis tools.

Validates that the analysis correctly identifies energy waste, regime
boundaries, and technology node scaling — the core research outputs.
"""

import numpy as np
import pytest
from physics.constants import k_B, landauer_limit
from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
from analysis.landauer_gap import (
    compute_gap,
    spatial_gap_map,
    gap_vs_technology_node,
    gap_vs_temperature,
    identify_efficiency_bottlenecks,
)


class TestComputeGap:
    """Test single-point Landauer gap computation."""

    def test_at_landauer_limit_gap_is_1(self):
        """Energy exactly at Landauer limit should give gap = 1."""
        E = landauer_limit(300.0)
        result = compute_gap(E, T=300.0)
        assert abs(result.gap_ratio - 1.0) < 1e-10
        assert abs(result.wasted_fraction) < 1e-10

    def test_above_landauer_gap_greater_than_1(self):
        """Energy above Landauer should give gap > 1."""
        E = landauer_limit(300.0) * 1000
        result = compute_gap(E, T=300.0)
        assert abs(result.gap_ratio - 1000.0) < 1e-6
        assert result.wasted_fraction > 0.99  # 99.9% wasted

    def test_bits_per_joule_correct(self):
        """bits_per_joule should be 1/E."""
        E = 1e-18
        result = compute_gap(E, T=300.0)
        assert abs(result.bits_per_joule_actual - 1e18) < 1e8


class TestSpatialGapMap:
    """Test spatial Landauer gap analysis."""

    def test_uniform_field_uniform_gap(self):
        """Uniform energy and temperature should give uniform gap."""
        shape = (10, 10, 4)
        E = np.ones(shape) * 1e-15
        T = np.ones(shape) * 300.0
        ops = np.ones(shape) * 1e6

        gap_map = spatial_gap_map(E, T, ops)

        # All gaps should be equal
        assert np.std(gap_map) / np.mean(gap_map) < 1e-10

    def test_hotter_regions_have_smaller_gap(self):
        """
        At the same energy, hotter regions have higher Landauer limit,
        so the gap should be SMALLER (closer to the limit).
        """
        shape = (10, 10, 4)
        E = np.ones(shape) * 1e-15
        ops = np.ones(shape) * 1e6

        T = np.ones(shape) * 300.0
        T[5:, :, :] = 600.0  # hot region

        gap_map = spatial_gap_map(E, T, ops)

        mean_gap_cold = np.mean(gap_map[:5, :, :])
        mean_gap_hot = np.mean(gap_map[5:, :, :])

        assert mean_gap_hot < mean_gap_cold, \
            "Hotter regions should have smaller Landauer gap"


class TestTechnologyScaling:
    """Test gap vs technology node analysis."""

    def test_returns_all_paradigms(self):
        results = gap_vs_technology_node()
        assert "cmos" in results
        assert "adiabatic" in results

    def test_gap_decreases_with_smaller_nodes(self):
        """Smaller tech nodes should have smaller Landauer gap."""
        results = gap_vs_technology_node()
        cmos_gaps = [r["gap"] for r in results["cmos"]]
        # First entry is largest node (130 nm), last is smallest (3 nm)
        assert cmos_gaps[0] > cmos_gaps[-1], \
            "Larger nodes should have larger Landauer gap"


class TestTemperatureScaling:
    """Test gap vs temperature analysis."""

    def test_cmos_gap_decreases_with_temperature(self):
        """
        CMOS energy is roughly constant, but Landauer limit increases with T.
        So the gap should decrease at higher temperatures.
        """
        cmos = CMOSGateEnergy(tech_node_nm=7)
        results = gap_vs_temperature(cmos, frequency_Hz=1e9)
        gaps = [r["gap"] for r in results]
        # Gap at 4 K should be much larger than at 600 K
        assert gaps[0] > gaps[-1]


class TestBottleneckIdentification:
    """Test efficiency bottleneck detection."""

    def test_no_bottlenecks_when_uniform_below_threshold(self):
        gap_map = np.ones((10, 10, 4)) * 1.5  # all below threshold of 2
        result = identify_efficiency_bottlenecks(gap_map, threshold=2.0)
        assert result["fraction_bottleneck"] == 0.0

    def test_all_bottlenecks_when_above_threshold(self):
        gap_map = np.ones((10, 10, 4)) * 100.0
        result = identify_efficiency_bottlenecks(gap_map, threshold=2.0)
        assert result["fraction_bottleneck"] == 1.0
        assert result["max_gap"] == 100.0
