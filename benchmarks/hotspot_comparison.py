#!/usr/bin/env python3
"""
Benchmark: Aethermor vs HotSpot on a representative SoC thermal problem.

This script sets up a heterogeneous SoC thermal problem that can be run
in both Aethermor and HotSpot, compares what each tool can answer,
and documents the workflow differences.

PURPOSE: Demonstrate where Aethermor adds value vs established tools,
and where HotSpot is more appropriate. This is a fair comparison, not
a sales pitch.

WHAT HOTSPOT DOES WELL:
  - Established, validated compact thermal model (RC network)
  - Efficient transient simulation
  - Package-level thermal resistance modeling
  - HotFloorplan for layout optimization
  - Published validation against real silicon (SPEC benchmarks)

WHAT AETHERMOR ADDS:
  - Inverse queries (max density, min cooling) as first-class operations
  - Multi-material substrate comparison in one call
  - Landauer-aware energy models with paradigm crossover
  - Interactive dashboard for real-time exploration
  - Extensible registries for custom materials/paradigms

METHODOLOGY:
  We define a 4-block SoC (CPU, GPU, cache, IO) and run:
    1. Forward thermal simulation (both tools can do this)
    2. Material comparison (Aethermor: one call; HotSpot: N separate runs)
    3. Cooling sweep (Aethermor: one call; HotSpot: N separate runs)
    4. Inverse density query (Aethermor: one call; HotSpot: manual binary search)
    5. Paradigm crossover (Aethermor: built-in; HotSpot: not supported)

  We report Aethermor results and document the equivalent HotSpot workflow
  for each step.
"""

import time
import sys
import os

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from aethermor.analysis.thermal_optimizer import ThermalOptimizer
from aethermor.physics.materials import get_material


def build_soc():
    """Build a representative 4-block heterogeneous SoC.

    This layout is comparable to the ev6 and alpha21364 benchmarks
    commonly used in HotSpot validation studies.

    Grid: 60×60×8 elements, 50μm pitch → 3mm × 3mm × 400μm die
    """
    fp = ChipFloorplan(
        grid_shape=(60, 60, 8),
        element_size_m=50e-6,
        material="silicon",
    )

    fp.add_block(FunctionalBlock(
        name="CPU_cluster", x_range=(0, 20), y_range=(0, 20), z_range=(0, 8),
        gate_density=5e5, activity=0.3, tech_node_nm=5, paradigm="cmos",
    ))
    fp.add_block(FunctionalBlock(
        name="GPU_array", x_range=(20, 50), y_range=(0, 30), z_range=(0, 8),
        gate_density=2e5, activity=0.5, tech_node_nm=7, paradigm="cmos",
    ))
    fp.add_block(FunctionalBlock(
        name="L2_cache", x_range=(0, 20), y_range=(20, 50), z_range=(0, 8),
        gate_density=3e5, activity=0.05, tech_node_nm=5, paradigm="cmos",
    ))
    fp.add_block(FunctionalBlock(
        name="IO_ring", x_range=(50, 60), y_range=(0, 60), z_range=(0, 8),
        gate_density=1e4, activity=0.2, tech_node_nm=7, paradigm="cmos",
    ))

    return fp


def benchmark_forward_simulation():
    """Test 1: Forward thermal simulation.

    Both Aethermor and HotSpot can answer: 'What is the temperature of
    each block given this power map and cooling?'

    HotSpot workflow:
      1. Create .flp file (block positions and sizes)
      2. Create .ptrace file (power per block per timestep)
      3. Configure package params (R_convec, etc.)
      4. Run: hotspot -c config -f floorplan.flp -p power.ptrace -o temps.ttrace
      5. Parse output file

    Aethermor workflow:
      1. Define floorplan in Python
      2. Call floorplan.simulate()
      3. Read temperatures directly
    """
    print("=" * 70)
    print("TEST 1: Forward Thermal Simulation (both tools handle this)")
    print("=" * 70)

    fp = build_soc()

    t0 = time.perf_counter()
    result = fp.simulate(frequency_Hz=1e9, steps=200, h_conv=1000.0)
    elapsed = time.perf_counter() - t0

    block_temps = fp.block_temperatures(result)
    print(f"\n  Aethermor: {elapsed:.2f}s for 200-step 3D Fourier simulation")
    print(f"  Die area: {fp.die_area_m2() * 1e6:.1f} mm²")
    print(f"  Total power: {fp.total_power_W(frequency_Hz=1e9):.2f} W")
    print()
    print(f"  {'Block':<20s}  {'T_max (K)':>10s}  {'T_mean (K)':>10s}  {'Paradigm':>10s}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*10}  {'-'*10}")
    for bt in block_temps:
        print(f"  {bt['name']:<20s}  {bt['T_max_K']:>10.1f}  {bt['T_mean_K']:>10.1f}  {bt['paradigm']:>10s}")

    print()
    print("  Equivalent HotSpot command:")
    print("    hotspot -c hotspot.config -f soc.flp -p soc.ptrace -o soc.ttrace")
    print("    (requires .flp + .ptrace + config files prepared manually)")

    return block_temps


def benchmark_material_comparison():
    """Test 2: Substrate comparison — 5 materials in one call.

    Question: 'Which substrate allows the highest compute density at
    7nm / 1GHz with liquid cooling?'

    HotSpot workflow:
      1. Create one .flp + .ptrace for each material
      2. Modify thermal conductivity and heat capacity in config
      3. Run hotspot 5 times
      4. Parse 5 output files
      5. Manually compare results
      Estimated setup: 30–60 min for someone experienced with HotSpot

    Aethermor workflow:
      1. One function call: material_ranking()
    """
    print("\n" + "=" * 70)
    print("TEST 2: Material Comparison — 5 substrates ranked in one call")
    print("=" * 70)

    opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

    materials = ["silicon", "diamond", "silicon_carbide", "gallium_nitride",
                 "gallium_arsenide"]

    t0 = time.perf_counter()
    ranking = opt.material_ranking(h_conv=1000.0, materials=materials)
    elapsed = time.perf_counter() - t0

    print(f"\n  Aethermor: {elapsed:.2f}s for 5-material ranking")
    print()
    print(f"  {'Material':<25s}  {'Max density':>14s}  {'T_max (K)':>10s}  {'Landauer gap':>12s}")
    print(f"  {'-'*25}  {'-'*14}  {'-'*10}  {'-'*12}")
    for r in ranking:
        print(f"  {r['material_name']:<25s}  {r['max_density']:>14.2e}  {r['T_max_K']:>10.1f}  {r['landauer_gap']:>12.0f}")

    if len(ranking) >= 2:
        ratio = ranking[0]["max_density"] / ranking[-1]["max_density"]
        print(f"\n  Key insight: {ranking[0]['material_name']} sustains "
              f"{ratio:.0f}× higher density than {ranking[-1]['material_name']}")
        print("  under identical cooling constraints.")

    print()
    print("  Equivalent HotSpot workflow:")
    print("    - Modify material properties in config file for each substrate")
    print("    - Run hotspot 5 times with binary search for max density each time")
    print("    - Estimated: 30–60 min for 5-material comparison")

    return ranking


def benchmark_cooling_sweep():
    """Test 3: Cooling diminishing returns — find the conduction floor.

    Question: 'At what cooling level does better convection stop helping?'

    This surfaces the conduction floor — the minimum junction temperature
    set by substrate thermal conductivity, regardless of cooling. This is
    a tradeoff that is invisible in forward-only simulation unless you
    explicitly sweep h_conv to high values and observe saturation.

    HotSpot workflow:
      1. Run hotspot N times with different R_convec values
      2. Plot results manually
      3. Identify saturation point by inspection
      Estimated: 15–30 min

    Aethermor workflow:
      1. One function call: cooling_sweep()
    """
    print("\n" + "=" * 70)
    print("TEST 3: Cooling Sweep — conduction floor detection")
    print("=" * 70)

    opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

    t0 = time.perf_counter()
    sweep = opt.cooling_sweep("silicon", gate_density=1e6)
    elapsed = time.perf_counter() - t0

    print(f"\n  Aethermor: {elapsed:.3f}s for cooling sweep (analytical)")
    print()
    print(f"  {'h_conv (W/m²K)':>16s}  {'T_max (K)':>10s}  {'Status'}")
    print(f"  {'-'*16}  {'-'*10}  {'-'*20}")
    for pt in sweep:
        status = ""
        if pt["T_max_K"] > get_material("silicon").max_operating_temp:
            status = "EXCEEDS LIMIT"
        elif pt["h_conv"] >= 10000:
            status = "diminishing returns"
        print(f"  {pt['h_conv']:>16.0f}  {pt['T_max_K']:>10.1f}  {status}")

    # Show conduction floor
    last = sweep[-1]
    print(f"\n  Conduction floor: T_max → {last['T_max_K']:.1f} K even at h = {last['h_conv']:.0f}")
    print("  Beyond this, better cooling has negligible effect.")
    print("  The bottleneck shifts to substrate thermal conductivity.")

    print()
    print("  Equivalent HotSpot workflow:")
    print("    - Run hotspot N times with decreasing R_convec")
    print("    - Plot T_max vs R_convec manually, identify saturation by inspection")

    return sweep


def benchmark_inverse_density():
    """Test 4: Inverse query — max density from constraints.

    Question: 'What is the maximum gate density silicon can sustain at
    7nm, 1GHz, with h_conv=1000?'

    This is the inverse of the forward problem. Instead of specifying
    density and getting temperature, we specify the thermal limit and
    get the maximum density.

    HotSpot workflow:
      1. Guess a density
      2. Run hotspot
      3. Check if T_max < limit
      4. Adjust density (binary search)
      5. Repeat ~20 times to converge
      Estimated: 30–60 min (scripted) or impossible (manually)

    Aethermor workflow:
      1. One function call: find_max_density()
    """
    print("\n" + "=" * 70)
    print("TEST 4: Inverse Density Query — constraints → max density")
    print("=" * 70)

    opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

    t0 = time.perf_counter()
    result = opt.find_max_density("silicon", h_conv=1000.0)
    elapsed = time.perf_counter() - t0

    print(f"\n  Aethermor: {elapsed:.2f}s for inverse density search")
    print(f"  Max density: {result['max_density']:.2e} gates/element")
    print(f"  T_max:       {result['T_max_K']:.1f} K  (limit: "
          f"{get_material('silicon').max_operating_temp:.0f} K)")
    print(f"  Power:       {result['power_W']:.3f} W")
    print(f"  Landauer gap: {result['landauer_gap']:.0f}×")

    print()
    print("  Equivalent HotSpot workflow:")
    print("    - Write a script to binary-search density:")
    print("      for each candidate density → create ptrace → run hotspot → parse T")
    print("    - ~20 iterations × HotSpot execution time")
    print("    - This is doable but requires custom scripting around HotSpot")


def benchmark_paradigm_crossover():
    """Test 5: Paradigm crossover — when does adiabatic beat CMOS?

    Question: 'At 7nm, below what frequency does adiabatic logic
    consume less energy than CMOS?'

    HotSpot: Does not model adiabatic or reversible computing paradigms.
    This is outside its scope.

    COMSOL: Would require separate energy model implementations.

    Aethermor: Built-in, one function call.
    """
    print("\n" + "=" * 70)
    print("TEST 5: Paradigm Crossover — CMOS vs adiabatic")
    print("=" * 70)

    from aethermor.physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy

    cmos = CMOSGateEnergy(tech_node_nm=7)
    adiabatic = AdiabaticGateEnergy(tech_node_nm=7)

    t0 = time.perf_counter()
    f_cross = adiabatic.crossover_frequency(cmos)
    elapsed = time.perf_counter() - t0

    print(f"\n  Aethermor: {elapsed:.4f}s for crossover computation")
    print(f"  Crossover frequency: {f_cross:.2e} Hz")
    print(f"  Below {f_cross/1e6:.0f} MHz, adiabatic uses less energy than CMOS at 7 nm")
    print()

    # Show energy at several frequencies
    freqs = [1e6, 1e7, 1e8, 1e9, 1e10]
    print(f"  {'Frequency':>12s}  {'CMOS (J)':>12s}  {'Adiabatic (J)':>14s}  {'Winner'}")
    print(f"  {'-'*12}  {'-'*12}  {'-'*14}  {'-'*12}")
    for f in freqs:
        e_cmos = cmos.energy_per_switch(f)
        e_adia = adiabatic.energy_per_switch(f)
        winner = "CMOS" if e_cmos < e_adia else "Adiabatic"
        print(f"  {f:>12.0e}  {e_cmos:>12.3e}  {e_adia:>14.3e}  {winner}")

    print()
    print("  Equivalent workflow in other tools:")
    print("    - HotSpot: Not supported (CMOS energy model only)")
    print("    - COMSOL: Would require implementing both energy models from scratch")
    print("    - Custom script: Possible but requires implementing the physics")


def benchmark_headroom_map():
    """Test 6: Per-block headroom — find the bottleneck.

    Question: 'Which block on my SoC is the thermal bottleneck, and
    how much density headroom does each block have?'

    This is the workflow compression test the reviewer asked for:
    surface a tradeoff that an experienced engineer would not get
    as quickly from HotSpot or COMSOL-style sweeps.

    HotSpot gives per-block temperatures (forward), but does not
    compute headroom factors or recommend reallocation. An engineer
    would need to:
      1. Run HotSpot → get temperatures
      2. Compare each block's T_max vs material limit
      3. For each block, binary-search the density that fills the gap
      4. Compute throughput implications manually

    Aethermor does this in one call with recommendations.
    """
    print("\n" + "=" * 70)
    print("TEST 6: Thermal Headroom Map — bottleneck identification")
    print("=" * 70)

    fp = build_soc()
    opt = ThermalOptimizer(tech_node_nm=5, frequency_Hz=1e9)

    t0 = time.perf_counter()
    headroom = opt.thermal_headroom_map(fp, h_conv=1000.0)
    elapsed = time.perf_counter() - t0

    print(f"\n  Aethermor: {elapsed:.3f}s for headroom analysis")
    print()
    print(f"  {'Block':<20s}  {'T_max (K)':>10s}  {'Headroom':>10s}  {'Bottleneck?'}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*10}  {'-'*12}")
    for h in headroom:
        bn = "YES ←" if h.get("is_bottleneck", False) else ""
        hf = h.get("density_headroom_factor", 0)
        print(f"  {h['name']:<20s}  {h['T_max_K']:>10.1f}  {hf:>10.1f}×  {bn}")

    print()
    print("  Equivalent HotSpot workflow:")
    print("    - Run HotSpot → get per-block temperatures")
    print("    - Manually compute (T_limit - T_block) for each block")
    print("    - Manually binary-search headroom density per block")
    print("    - Estimated: 30–60 min for a 4-block SoC")


def print_summary():
    """Print overall comparison summary."""
    print("\n" + "=" * 70)
    print("SUMMARY: Where each tool wins")
    print("=" * 70)
    print("""
  AETHERMOR IS BETTER FOR:
    ✓ Architecture-stage exploration (fast 'what if' queries)
    ✓ Multi-material substrate comparison (one call)
    ✓ Cooling diminishing-returns / conduction floor visibility
    ✓ Inverse density queries (constraints → optimal design)
    ✓ Paradigm crossover analysis (CMOS vs adiabatic vs reversible)
    ✓ Interactive dashboard for meetings / design reviews
    ✓ Per-block headroom + reallocation recommendations

  HOTSPOT IS BETTER FOR:
    ✓ Validated against real silicon (published SPEC benchmark correlation)
    ✓ Transient thermal analysis (time-domain power traces)
    ✓ Established in the research community (peer-reviewed, cited)
    ✓ Package-level thermal resistance modeling
    ✓ HotFloorplan for layout-specific optimization
    ✓ Integration with architecture simulators (SimpleScalar, etc.)

  COMPLEMENTARY USE:
    Use Aethermor for early exploration → narrow the design space
    Use HotSpot for detailed validation → confirm thermal feasibility
    Use COMSOL/ANSYS for sign-off → final thermal verification
""")


if __name__ == "__main__":
    print("Aethermor vs HotSpot: Representative SoC Thermal Benchmark")
    print("=" * 70)
    print()

    benchmark_forward_simulation()
    benchmark_material_comparison()
    benchmark_cooling_sweep()
    benchmark_inverse_density()
    benchmark_paradigm_crossover()
    benchmark_headroom_map()
    print_summary()
