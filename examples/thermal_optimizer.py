#!/usr/bin/env python3
"""
RESEARCH EXAMPLE: Thermal budget optimisation
==============================================

Research question: Given a thermal limit and cooling solution, what is
the maximum compute density each material can sustain — and what
cooling is needed to reach a target density?

This script solves the INVERSE problem:
  Forward:  design → temperature   (what most tools do)
  Inverse:  constraints → optimal design   (what Aethermor uniquely does)

What this script demonstrates:
  1. Find max density for each material via 3D thermal binary search
  2. Rank materials by achievable density (the material selection decision)
  3. Find minimum cooling requirement for a target density
  4. Compare CMOS vs adiabatic max density (paradigm selection decision)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from analysis.thermal_optimizer import ThermalOptimizer

# Use a moderate grid for speed; larger grids give more accurate results
opt = ThermalOptimizer(
    grid_shape=(15, 15, 4),
    element_size_m=100e-6,
    tech_node_nm=7,
    frequency_Hz=1e9,
    activity=0.2,
    thermal_steps=500,
)

# ═══════════════════════════════════════════════════════════════
# Part 1: Material ranking by max achievable density
# ═══════════════════════════════════════════════════════════════

print("=" * 95)
print("MATERIAL RANKING: Which substrate allows the highest compute density?")
print("=" * 95)
print()

ranking = opt.material_ranking(h_conv=1000.0)
print(opt.format_material_ranking(ranking, h_conv=1000.0))

# ═══════════════════════════════════════════════════════════════
# Part 2: Cooling requirement for target density
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 95)
print("COOLING REQUIREMENTS: What cooling do you need for a target density?")
print("=" * 95)
print()

target_densities = [1e4, 1e5, 5e5, 1e6, 5e6]
print(f"{'Target Density':>15s}  {'Min h_conv':>10s}  {'Cond. Floor (K)':>15s}  "
      f"{'Cooling Category':<35s}")
print("-" * 80)
for density in target_densities:
    result = opt.find_min_cooling("silicon", gate_density=density)
    h_str = (f"{result['min_h_conv']:>10.0f}"
             if result['min_h_conv'] < float('inf') else "       inf")
    floor = result.get('conduction_floor_K', 0)
    print(f"{density:>15.0e}  {h_str}  {floor:>15.1f}  "
          f"{result['cooling_category']:<35s}")

# ═══════════════════════════════════════════════════════════════
# Part 3: Cooling sweep for silicon at 1e7 gates/element
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 95)
print("COOLING SWEEP: Temperature vs cooling for Silicon @ 1e5 gates/element")
print("=" * 95)
print()

sweep = opt.cooling_sweep("silicon", gate_density=1e5)
# Show conduction floor
mat_info = opt.find_min_cooling("silicon", gate_density=1e5)
floor = mat_info.get('conduction_floor_K', 300)
print(f"  Conduction floor (h → ∞): {floor:.1f} K   "
      f"[set by Si thermal conductivity, irreducible]")
print()
print(f"{'h_conv':>10s}  {'T_max (K)':>10s}  {'Headroom (K)':>12s}  {'Status':>8s}")
print("-" * 45)
for s in sweep:
    status = "OK" if s["safe"] else ("RUNAWAY" if s["runaway"] else "OVER")
    print(f"{s['h_conv']:>10.0f}  {s['T_max_K']:>10.1f}  "
          f"{s['thermal_headroom_K']:>12.1f}  {status:>8s}")

# ═══════════════════════════════════════════════════════════════
# Part 4: CMOS vs Adiabatic density comparison
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 95)
print("PARADIGM COMPARISON: Max density with CMOS vs Adiabatic logic")
print("=" * 95)
print()

for mat in ["silicon", "diamond", "silicon_carbide"]:
    comp = opt.paradigm_density_comparison(mat, h_conv=1000.0)
    cmos_d = comp["cmos"]["max_density"]
    adiab_d = comp["adiabatic"]["max_density"]
    ratio = comp["adiabatic_advantage_ratio"]
    print(f"{comp['cmos']['material_name']:<30s}  "
          f"CMOS: {cmos_d:.2e}  Adiabatic: {adiab_d:.2e}  "
          f"Ratio: {ratio:.1f}×")

print()
print("INSIGHT: At 1 GHz, adiabatic logic at 7nm dissipates almost zero")
print("energy (below the crossover frequency), allowing dramatically higher")
print("density — limited only by the Landauer floor and thermal leakage.")

# ═══════════════════════════════════════════════════════════════
# Part 5: Thermal headroom map for a heterogeneous SoC
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 95)
print("THERMAL HEADROOM MAP: Where is thermal budget wasted on a heterogeneous SoC?")
print("=" * 95)
print()

from physics.chip_floorplan import ChipFloorplan

# Use 500 µm elements on a 20×20×4 grid → 10 mm × 10 mm = 100 mm² die
# (Coarse grid for speed; element_size sets the physical scale.)
soc = ChipFloorplan.modern_soc(grid_shape=(20, 20, 4), element_size_m=500e-6)
headroom = opt.thermal_headroom_map(soc, h_conv=1000.0, steps=200)

print(f"{'Block':<22s} {'Paradigm':<10s} {'T_max (K)':>10s} {'Headroom':>10s} "
      f"{'Bottleneck':>11s} {'Density ×':>10s}  {'Action'}")
print("-" * 110)
for h in headroom:
    bn = ">>> YES <<<" if h["is_bottleneck"] else ""
    print(f"{h['name']:<22s} {h['paradigm']:<10s} "
          f"{h['T_max_K']:>10.1f} {h['thermal_headroom_K']:>9.1f} K "
          f"{bn:>11s} {h['density_headroom_factor']:>9.1f}×  "
          f"{h['recommended_action']}")

print()
print("INSIGHT: This map shows which blocks have wasted thermal budget.")
print("Traditional tools require manual iteration to find this — Aethermor")
print("answers it in one call.")

# ═══════════════════════════════════════════════════════════════
# Part 6: Power redistribution — optimise density across blocks
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 95)
print("POWER REDISTRIBUTION: Optimise gate density across blocks for max throughput")
print("=" * 95)
print()

result = opt.optimize_power_distribution(
    soc, power_budget_W=50.0, frequency_Hz=1e9, h_conv=1000.0,
)

print(f"Power budget: {result['power_budget_W']:.0f} W")
print(f"Thermal power limit (all blocks at thermal max): {result['thermal_power_limit_W']:.1f} W")
print(f"Binding constraint: {result['binding_constraint']}")
print(f"Total power used: {result['total_power_W']:.1f} W")
print(f"Total throughput: {result['total_throughput_ops_s']:.2e} ops/s")
print(f"Improvement over original: {result['improvement_ratio']:.2f}×")
print()
print(f"{'Block':<22s} {'Original':>12s} {'Optimised':>12s} {'Change':>8s} "
      f"{'Power (W)':>10s} {'T_est (K)':>10s} {'Headroom':>10s}")
print("-" * 90)
for b in result["optimised_blocks"]:
    print(f"{b['name']:<22s} {b['original_density']:>12.2e} "
          f"{b['optimised_density']:>12.2e} {b['density_change']:>7.2f}× "
          f"{b['power_W']:>10.2f} {b['T_estimated_K']:>10.1f} "
          f"{b['thermal_headroom_K']:>9.1f} K")

print()
print("INSIGHT: The optimizer redistributes compute density to fill thermal")
print("headroom — putting more gates where the chip is cool and fewer where")
print("it's hot. This is the inverse design problem that chip architects")
print("solve manually over weeks. Aethermor does it in seconds.")
