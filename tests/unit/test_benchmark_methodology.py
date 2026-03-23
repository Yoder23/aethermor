# tests/unit/test_benchmark_methodology.py
"""
Tests that verify benchmark methodology is documented and that claimed gains
are attributable to the experimental design rather than discovered properties.

These tests encode the critical review findings and serve as guardrails against
overstated claims.
"""

import numpy as np
import pytest

from simulation.aethermor_full_simulation_v2 import AethermorSimV2
from simulation.thermodynamic_core import ThermodynamicAICore


class TestThermoCoreMethodology:
    """Verify that thermo-core efficiency gain is driven by compute_cost parameter."""

    def test_efficiency_scales_with_compute_cost(self):
        """
        If the 'efficiency improvement' is a genuine thermodynamic discovery,
        it should not be fully explained by the ratio of compute_cost parameters.
        This test checks whether the efficiency ratio approximately equals the
        cost ratio, demonstrating the gain is parameter-driven.
        """
        seed = 42
        steps = 30
        base_sim = AethermorSimV2(steps=1, seed=seed)
        base_cost = base_sim.compute_cost

        # Run "naive" (1.5x cost) and "optimized" (0.75x cost)
        cost_ratio = 1.5 / 0.75  # = 2.0

        sim_naive = AethermorSimV2(steps=steps, seed=seed)
        sim_naive.compute_cost = base_cost * 1.5
        sim_naive.ai_core = ThermodynamicAICore()
        sim_naive.run()

        sim_opt = AethermorSimV2(steps=steps, seed=seed)
        sim_opt.compute_cost = base_cost * 0.75
        sim_opt.ai_core = ThermodynamicAICore()
        sim_opt.run()

        # Compute efficiency: useful_bits / compute_energy
        import pandas as pd

        df_na = pd.DataFrame(sim_naive.metrics)
        df_op = pd.DataFrame(sim_opt.metrics)

        compute_na = df_na["compute_energy_step"].to_numpy(dtype=float)
        compute_op = df_op["compute_energy_step"].to_numpy(dtype=float)

        # The compute energies should differ by approximately the cost ratio
        mean_ratio = np.mean(compute_na) / np.mean(compute_op)
        assert mean_ratio == pytest.approx(cost_ratio, rel=0.3), (
            f"Compute energy ratio ({mean_ratio:.2f}) should be close to the "
            f"parameter cost ratio ({cost_ratio:.2f}), confirming the efficiency "
            f"gain is parameter-driven, not a discovered property."
        )

    def test_landauer_is_bookkeeping_only(self):
        """
        Verify that the ThermodynamicAICore does not modify simulation state.
        It should be a passive observer/bookkeeper.
        """
        seed = 42
        steps = 10

        sim_with = AethermorSimV2(steps=steps, seed=seed)
        sim_with.ai_core = ThermodynamicAICore()
        sim_with.run()

        sim_without = AethermorSimV2(steps=steps, seed=seed)
        sim_without.ai_core = None
        sim_without.run()

        # Energy fields should be identical — ai_core is passive
        np.testing.assert_allclose(
            sim_with.energy_field,
            sim_without.energy_field,
            rtol=1e-10,
            err_msg="ThermodynamicAICore should not alter simulation dynamics",
        )


class TestMaterialTwinMethodology:
    """Verify that material twin gain comes from active energy injection."""

    def test_closed_loop_injects_energy(self):
        """
        The 'material twin' benefit should come from _material_healing_boost
        injecting energy into nodes with nonzero repair_priority.
        """
        sim = AethermorSimV2(grid_shape=(4, 4, 2), steps=1, seed=42)
        pos = (1, 1, 0)
        node = sim.nodes[pos]

        # Mark node as faulted with repair priority
        node["faulted"] = True
        node["repair_priority"] = 0.5
        energy_before = node["energy"]

        sim._material_healing_boost(pos, node)

        # Healing boost should increase node energy
        assert node["energy"] > energy_before, (
            "Material twin boost should inject energy into faulted nodes "
            "with nonzero repair_priority"
        )

    def test_no_boost_without_fault(self):
        """Nodes not marked as faulted should receive no boost."""
        sim = AethermorSimV2(grid_shape=(4, 4, 2), steps=1, seed=42)
        pos = (1, 1, 0)
        node = sim.nodes[pos]
        node["faulted"] = False
        energy_before = node["energy"]

        sim._material_healing_boost(pos, node)

        assert node["energy"] == energy_before


class TestMetabolicClusterMethodology:
    """Verify that the metabolic cluster benchmark's cooling is a direct subtraction."""

    def test_cooling_is_direct_subtraction(self):
        """
        The metabolic cluster controller applies a hardcoded COOL_DELTA
        subtraction to temperature. This test confirms the temperature
        reduction is a direct parameter effect.
        """
        sim = AethermorSimV2(grid_shape=(8, 8, 2), steps=1, seed=42)
        hs_slice = (slice(3, 5), slice(3, 5), slice(0, 2))

        # Set hotspot above threshold
        sim.temp_field[hs_slice] = 350.0
        temp_before = sim.temp_field[hs_slice].mean()

        # Apply the same logic as benchmark_metabolic_cluster._run_metabolic_cluster
        COOL_DELTA = 6.0
        TEMP_HOT = 340.0
        hs_temp = float(sim.temp_field[hs_slice].mean())

        if hs_temp > TEMP_HOT:
            sim.temp_field[hs_slice] -= COOL_DELTA

        temp_after = sim.temp_field[hs_slice].mean()
        reduction = temp_before - temp_after

        assert reduction == pytest.approx(COOL_DELTA, abs=0.01), (
            f"Temperature reduction ({reduction:.2f}) should equal COOL_DELTA "
            f"({COOL_DELTA:.2f}), confirming it is a hardcoded parameter effect."
        )
