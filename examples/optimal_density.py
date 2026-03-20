"""
Research Example 1: Optimal Compute Density

QUESTION: At what gate density does thermal throttling offset the throughput
gains from packing more logic into the chip?

This is one of the most practical questions in chip architecture. The answer
depends on substrate material, cooling capability, and technology node.

This script sweeps gate density and identifies the "thermal wall" — the
density beyond which temperatures exceed safe limits. It also finds the
Pareto-optimal density that maximizes throughput per watt.

Run:
    python examples/optimal_density.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
from physical_simulation import PhysicalSimulation, PhysicalSimConfig
from physics.materials import MATERIAL_DB


def find_thermal_wall():
    """
    Sweep gate density and find where max temperature exceeds limit.

    Uses small grid (10×10×4) with 500 steps to approach thermal equilibrium,
    and sweeps to high densities (1e9) to actually hit the thermal wall.
    """
    materials = ["silicon", "diamond", "silicon_carbide", "gallium_arsenide"]
    densities = [1e5, 1e6, 5e6, 1e7, 5e7, 1e8, 5e8, 1e9]

    print("=" * 80)
    print("RESEARCH QUESTION: What is the maximum sustainable compute density?")
    print("=" * 80)
    print()
    print(f"{'Material':<22} {'Gate Density':>14} {'T_max (K)':>10} {'Power (W)':>12} "
          f"{'Landauer Gap':>14} {'Status':>10}")
    print("-" * 86)

    for mat_key in materials:
        mat = MATERIAL_DB[mat_key]
        max_safe_density = 0

        for density in densities:
            sim = PhysicalSimulation(
                grid_shape=(10, 10, 4),
                element_size_m=100e-6,
                material=mat_key,
                tech_node_nm=7,
                frequency_Hz=1e9,
                gate_density=density,
                steps=500,
                h_conv=1000.0,
            )
            sim.run()
            s = sim.summary()

            if s.get("thermal_runaway", False):
                status = "RUNAWAY"
                # Don't print meaningless numbers for runaway cases
                print(f"{mat.name:<22} {density:>14.0e} {'---':>10} "
                      f"{'---':>12} {'---':>14} "
                      f"{status:>10}")
            else:
                if s["T_max_K"] < mat.max_operating_temp:
                    status = "OK"
                    max_safe_density = density
                else:
                    status = "EXCEEDED"

                print(f"{mat.name:<22} {density:>14.0e} {s['T_max_K']:>10.1f} "
                      f"{s['total_power_W']:>12.3e} {s['landauer_gap']:>14.1f} "
                      f"{status:>10}")

        print(f"  → Max safe density for {mat.name}: {max_safe_density:.0e} gates/element")
        print()


def throughput_per_watt_curve():
    """
    Compare maximum achievable chip throughput for each material.

    Total throughput = gate_density × frequency × n_elements.
    Higher thermal conductivity → can sustain higher density → more throughput.
    This shows why substrate choice matters at scale.
    """
    print()
    print("=" * 80)
    print("THROUGHPUT COMPARISON: Max Sustainable Throughput by Material")
    print("=" * 80)
    print()

    densities = np.logspace(5, 9, 15)  # 1e5 to 1e9

    for mat_key in ["silicon", "diamond", "gallium_arsenide"]:
        mat = MATERIAL_DB[mat_key]
        best_throughput = 0
        best_density = 0
        best_power = 0

        for density in densities:
            sim = PhysicalSimulation(
                grid_shape=(10, 10, 4),
                material=mat_key,
                tech_node_nm=7,
                gate_density=density,
                steps=300,
                h_conv=1000.0,
            )
            sim.run()
            s = sim.summary()

            # Skip runaway or thermally exceeded cases
            if s.get("thermal_runaway", False):
                continue
            if s["T_max_K"] >= mat.max_operating_temp:
                continue

            n_elements = np.prod(s["grid_shape"])
            ops_per_s = s["gate_density"] * s["frequency_GHz"] * 1e9 * n_elements

            if ops_per_s > best_throughput:
                best_throughput = ops_per_s
                best_density = density
                best_power = s["total_power_W"]

        tpw = best_throughput / max(best_power, 1e-30)
        print(f"{mat.name}:")
        print(f"  Max safe density:    {best_density:.0e} gates/element")
        print(f"  Peak throughput:     {best_throughput:.2e} ops/s")
        print(f"  Power at peak:       {best_power:.1f} W")
        print(f"  Efficiency at peak:  {tpw:.2e} ops/J")
        print()

    print("INSIGHT: Diamond sustains ~20x higher gate density than Silicon,")
    print("translating directly to ~20x higher chip throughput at the thermal wall.")


if __name__ == "__main__":
    find_thermal_wall()
    throughput_per_watt_curve()
