#!/usr/bin/env python3
"""
RESEARCH EXAMPLE: Heterogeneous SoC thermal analysis
=====================================================

Research question: How does block placement on a heterogeneous SoC
(CPU + GPU + cache + I/O) affect thermal coupling and hotspot formation?

This is a research workflow that would take days in COMSOL or custom
MATLAB scripts.  Aethermor does it in seconds.

What this script demonstrates:
  1. Define a realistic SoC floorplan with 4 functional blocks
  2. Simulate thermal behaviour with material-specific Fourier transport
  3. Show per-block temperature statistics
  4. Compare a hybrid CMOS+adiabatic chip against a pure CMOS chip
  5. Quantify the thermal benefit of using adiabatic logic in the periphery
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from aethermor.physics.cooling import CoolingStack

# ═══════════════════════════════════════════════════════════════
# Part 1: Modern SoC floorplan analysis
# ═══════════════════════════════════════════════════════════════

print("=" * 80)
print("HETEROGENEOUS SoC THERMAL ANALYSIS")
print("=" * 80)
print()

# Use the factory method for a realistic SoC
soc = ChipFloorplan.modern_soc(grid_shape=(40, 40, 6), element_size_m=75e-6)

freq = 2e9  # 2 GHz
print(soc.summary(frequency_Hz=freq))
print()

# Simulate with a realistic cooling stack
stack = CoolingStack.desktop_air()
die_area = soc.die_area_m2()
print(stack.describe(die_area))
print()

thermal = soc.simulate(frequency_Hz=freq, steps=500, cooling_stack=stack)

print(f"Die-level results:")
print(f"  T_max  = {thermal.max_temperature():.1f} K")
print(f"  T_mean = {thermal.mean_temperature():.1f} K")
print()

# Per-block breakdown
print(f"{'Block':<25s}  {'T_max (K)':>10s}  {'T_mean (K)':>10s}  {'T_min (K)':>10s}")
print("-" * 62)
block_temps = soc.block_temperatures(thermal)
for bt in block_temps:
    print(f"{bt['name']:<25s}  {bt['T_max_K']:>10.1f}  "
          f"{bt['T_mean_K']:>10.1f}  {bt['T_min_K']:>10.1f}")

# Energy balance
eb = thermal.energy_balance()
pct_err = 100 * abs(eb["balance_error_J"]) / max(eb["generated_J"], 1e-30)
print(f"\nEnergy balance: generated={eb['generated_J']:.4e} J, "
      f"removed={eb['removed_J']:.4e} J, error={pct_err:.2f}%")

# ═══════════════════════════════════════════════════════════════
# Part 2: CMOS-only vs hybrid CMOS+adiabatic
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 80)
print("PARADIGM COMPARISON: Pure CMOS vs Hybrid CMOS+Adiabatic")
print("=" * 80)
print()

# Pure CMOS chip
cmos_chip = ChipFloorplan(grid_shape=(40, 40, 6), element_size_m=75e-6)
cmos_chip.add_block(FunctionalBlock(
    name="CMOS_core",
    x_range=(10, 30), y_range=(10, 30), z_range=(0, 6),
    gate_density=5e5, activity=0.3, tech_node_nm=7, paradigm="cmos",
))
cmos_chip.add_block(FunctionalBlock(
    name="CMOS_periphery_N",
    x_range=(0, 40), y_range=(0, 10), z_range=(0, 6),
    gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="cmos",
))
cmos_chip.add_block(FunctionalBlock(
    name="CMOS_periphery_S",
    x_range=(0, 40), y_range=(30, 40), z_range=(0, 6),
    gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="cmos",
))
cmos_chip.add_block(FunctionalBlock(
    name="CMOS_periphery_W",
    x_range=(0, 10), y_range=(10, 30), z_range=(0, 6),
    gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="cmos",
))
cmos_chip.add_block(FunctionalBlock(
    name="CMOS_periphery_E",
    x_range=(30, 40), y_range=(10, 30), z_range=(0, 6),
    gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="cmos",
))

# Hybrid chip: same core is CMOS, periphery uses adiabatic
hybrid_chip = ChipFloorplan.hybrid_paradigm(
    grid_shape=(40, 40, 6), element_size_m=75e-6
)

# Simulate both with same cooling
for label, chip in [("Pure CMOS", cmos_chip), ("Hybrid CMOS+Adiabatic", hybrid_chip)]:
    th = chip.simulate(frequency_Hz=freq, steps=500, cooling_stack=stack)
    power = chip.total_power_W(freq)
    pd = chip.power_density_W_cm2(freq)
    print(f"{label}:")
    print(f"  Total power: {power:.2f} W  ({pd:.1f} W/cm²)")
    print(f"  T_max: {th.max_temperature():.1f} K")
    print(f"  T_mean: {th.mean_temperature():.1f} K")
    print(f"  Per-block temperatures:")
    for bt in chip.block_temperatures(th):
        print(f"    {bt['name']:<25s}  T_max={bt['T_max_K']:.1f} K  "
              f"T_mean={bt['T_mean_K']:.1f} K")
    print()

# ═══════════════════════════════════════════════════════════════
# Part 3: Cooling stack comparison
# ═══════════════════════════════════════════════════════════════

print("=" * 80)
print("COOLING STACK IMPACT ON SoC THERMALS")
print("=" * 80)
print()

cooling_configs = [
    ("Bare die (natural air)", CoolingStack.bare_die_natural_air()),
    ("Desktop air cooler",     CoolingStack.desktop_air()),
    ("Server air",             CoolingStack.server_air()),
    ("Liquid cold plate",      CoolingStack.liquid_cooled()),
    ("Direct liquid",          CoolingStack.direct_liquid()),
    ("Diamond + liquid",       CoolingStack.diamond_spreader_liquid()),
]

print(f"{'Cooling':<25s}  {'h_eff':>10s}  {'T_max (K)':>10s}  "
      f"{'T_mean (K)':>10s}  {'Headroom':>10s}")
print("-" * 72)
for label, cs in cooling_configs:
    h_eff = cs.effective_h(die_area)
    th = soc.simulate(frequency_Hz=freq, steps=500, cooling_stack=cs)
    from aethermor.physics.materials import MATERIAL_DB
    headroom = MATERIAL_DB["silicon"].max_operating_temp - th.max_temperature()
    status = "OK" if headroom > 0 else "OVER LIMIT"
    print(f"{label:<25s}  {h_eff:>9.0f}  {th.max_temperature():>10.1f}  "
          f"{th.mean_temperature():>10.1f}  {headroom:>8.1f} K  {status}")

print()
print("INSIGHT: The cooling stack determines whether the SoC can operate")
print("within thermal limits.  Bare-die natural air cannot sustain modern")
print("SoC power densities.  Liquid cooling provides 10-100× more headroom.")
