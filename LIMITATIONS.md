# Scope and Model Architecture

Aethermor is a **production thermal engineering toolkit** for chip thermal
analysis, cooling tradeoffs, and compute-density optimization.

> **Scope: Production-stable for architecture-stage thermal exploration and inverse design; not intended for sign-off, transient package verification, or transistor-level thermal closure.**

This document describes what the project provides, the physics it models, and its
validation coverage.

---

## What Aethermor Provides

### Physics-Grounded Simulation

The `physics/` package implements real thermodynamic models in SI units:

- **Fundamental constants**: Boltzmann constant (CODATA 2018), Landauer limit
  `k_B · T · ln 2`, thermal noise voltage, derived quantities like bits-per-joule
  at temperature T.
- **Material database**: Nine chip substrates (Si, SiO₂, GaAs, diamond,
  graphene, Cu, InP, SiC, GaN) with published thermal conductivity, specific
  heat, density, resistivity, bandgap, and max operating temperature. Each
  material computes thermal diffusivity and volumetric heat capacity from these
  primary properties.
- **Gate energy models**: Four computing paradigms — CMOS (dynamic + leakage
  with technology-node scaling), adiabatic (R·C²·V²·f), reversible (erasures ×
  Landauer limit + overhead), and theoretical Landauer floor. Models include
  crossover-frequency and temperature-crossover calculations.
- **Fourier thermal transport**: 3D heat diffusion solver with CFL-stable
  timestep selection, convective / fixed / adiabatic boundary conditions,
  energy conservation tracking, hotspot detection, and steady-state estimation.

All values are in Joules, Kelvin, Watts, and metres. Every input and output maps
directly to measurable physical quantities.

### Research Analysis Tools

The `analysis/` package provides tools designed for hardware research questions:

- **Landauer gap analysis**: How far is a design from the thermodynamic limit?
  Spatial gap maps across the chip, gap vs. technology node, gap vs. temperature.
- **Design space sweeps**: Sweep technology node × frequency × gate density ×
  material × cooling, with automatic Pareto frontier extraction.
- **Regime classification**: Automatically labels designs as deep-classical,
  classical, transitional, thermodynamic, or near-limit, based on their
  Landauer gap.
- **Thermal mapping**: Hotspot detection (connected-component labelling),
  cooling efficiency maps, thermal gradient analysis.
- **Technology roadmap projection**: Track energy per gate, Landauer gap,
  paradigm crossover frequency, and thermal wall from 130 nm down to 1.4 nm.
- **Inverse thermal design (ThermalOptimizer)**: Find the maximum compute
  density a material+cooling combination can sustain, or the minimum cooling
  needed for a target density. Uses a combined conduction + convection 1D
  model that correctly captures both material conductivity and cooling
  sensitivity, with 3D simulation for material ranking.

### Physics — Cooling and Architecture Models

- **Cooling stack model** (`physics/cooling.py`): Assemble a realistic thermal
  path from die to ambient — TIM → IHS → heatsink → convection. Eleven
  pre-built layers and six factory configurations (bare-die, desktop-air,
  server, liquid, direct-liquid, diamond-spreader). Computes effective h,
  max power, layer-by-layer temperatures.
- **Chip floorplan model** (`physics/chip_floorplan.py`): Define heterogeneous
  architectures with distinct functional blocks (CPU, GPU, cache, I/O), each
  with its own density, activity, technology node, and paradigm
  (CMOS / adiabatic). Generates heat maps, simulates thermal coupling, and
  reports per-block temperatures. Factory methods create typical SoC and
  hybrid CMOS+adiabatic layouts.

### Research Example Scripts

The `examples/` directory contains ready-to-run scripts that demonstrate
concrete research workflows:

| Script | Research Question |
|--------|-------------------|
| `optimal_density.py` | What is the maximum gate density each substrate can sustain before hitting its thermal wall? |
| `adiabatic_crossover.py` | At what frequency does adiabatic logic become more efficient than CMOS, and how does this depend on technology node? |
| `material_comparison.py` | How does substrate choice (Si vs. diamond vs. SiC vs. GaAs) affect achievable compute density and power? |
| `heterogeneous_soc.py` | How do hotspots, cooling stacks, and CMOS/adiabatic mixing interact on a realistic SoC? |
| `technology_roadmap.py` | How does the Landauer gap close as technology scales from 130 nm to 1.4 nm, and when does each paradigm win? |
| `thermal_optimizer.py` | Given a thermal limit, which material allows the highest density, and what cooling is required? |
| `custom_material.py` | How do I register and test my own materials, paradigms, and cooling layers? |

---

## Research Questions This Tool Can Address

Aethermor is designed to help hardware teams answer questions like:

1. **"At what technology node does our architecture hit a thermal wall?"**
   Sweep gate density and node size → find where steady-state temperature
   exceeds the substrate limit.

2. **"When does adiabatic logic pay off?"**
   Compare CMOS and adiabatic energy models across frequencies → find the
   crossover point where adiabatic switching consumes less energy.

3. **"How close to Landauer are we, and where does the gap come from?"**
   Compute the Landauer gap spatially across a chip → identify which regions
   or components waste the most energy above the thermodynamic floor.

4. **"Which substrate buys us the most thermal headroom?"**
   Run identical workloads on Si, diamond, SiC, GaN → compare peak
   temperature and maximum sustainable density.

5. **"What cooling strategy is needed for our target density?"**
   Sweep convective heat transfer coefficient from natural air (h ≈ 10) to
   microchannel cooling (h ≈ 50,000) → find the minimum cooling required.

6. **"Where on the thermodynamic spectrum does our design sit?"**
   Classify a design as deep_classical / classical / transitional /
   thermodynamic / near_limit based on its Landauer gap.

7. **"How does a heterogeneous SoC distribute heat across blocks?"**
   Define CPU, GPU, cache, I/O regions with different densities and paradigms
   → simulate thermal coupling → identify which block is the thermal bottleneck.

8. **"What cooling stack gets us under the thermal limit?"**
   Build a realistic die → TIM → IHS → heatsink → ambient path → compute
   effective h and max dissipable power for a given die size.

9. **"At what node does adiabatic logic match CMOS on energy?"**
   Run the technology roadmap projection across nodes (130 nm to 1.4 nm) →
   find the node and frequency where paradigm crossover occurs.

10. **"What density advantage does material X give over material Y?"**
    Use the ThermalOptimizer to binary-search maximum density on each
    substrate, accounting for full 3D heat spreading and material properties.

---

## What This Is Not

Intellectual honesty matters. Aethermor operates at the thermal and energy
level — a different layer than circuit-level or transistor-level tools:

### Not a Hardware Simulator

Aethermor does not model transistor physics, interconnect parasitics, clock
distribution, or real circuit layout. It operates at the **thermal and energy
level** — modeling heat transport and switching energy — not at the device level.
Results show thermal and energetic feasibility, not circuit correctness.

### Not a Boltzmann Machine or Stochastic Computing System

The project does not implement:
- Boltzmann machine dynamics or Gibbs sampling
- Stochastic noise-exploiting computation (p-bits, p-circuits)
- Quantum annealing or probabilistic computing architectures

Published architectures from groups like Extropic, Normal Computing, or Purdue's
p-bit work are not modeled. Aethermor addresses the **thermal management and
energy efficiency layer** that underlies all these architectures.

### Validated Against Published Hardware Measurements

The thermal model has been validated at three tiers:

1. **Published chip specifications** — 33 checks against NVIDIA A100, Apple M1,
   AMD EPYC 9654, and Intel i9-13900K (all pass).
2. **Published hardware measurements** — 18 checks against JEDEC-standard
   junction-to-case thermal resistance (θ_jc) for the A100, i9-13900K, and
   Ryzen 7950X; published IR thermal imaging data (Kandlikar 2003, Bar-Cohen &
   Wang 2009); Yovanovich 1998 spreading resistance; and the HotSpot ev6
   benchmark (all pass).
3. **Literature and analytical** — 20 checks against CODATA 2018, CRC Handbook,
   ITRS/IRDS, and Incropera & DeWitt textbook solutions (all pass).
4. **Chip thermal database** — 82 checks across 12 real production chips in 4
   market segments: accelerators (A100, H100, MI300X), servers (EPYC 9654,
   Xeon w9-3495X), desktops (i9-13900K, Ryzen 9 7950X), and mobile
   (M1, M2 Pro, Snapdragon 8 Gen 2) — all pass.
5. **Material cross-validation** — 93 checks across 9 materials validated
   against CRC Handbook, ASM International, NIST, Ioffe Institute, and
   manufacturer datasheets — all pass.

**Total: 680+ validated checks across 12 suites, all passing.**

### Original Lattice Simulation

The original `AethermorSimV2` simulation operates in abstract energy units. Its
benchmarks demonstrate that active controllers outperform passive baselines —
an expected result by construction. The statistical framework (paired ablations,
Holm correction) validates implementation correctness, not physical discovery.
See the benchmark documentation for details.

---

## Known Model Simplifications

1. **Isotropic thermal conductivity**: Materials are treated as isotropic.
   Graphene's highly anisotropic thermal conductivity (in-plane vs.
   cross-plane) is approximated as a single effective value.

2. **Uniform gate density**: The base simulation assumes uniform gate density
   per lattice element. The `ChipFloorplan` model addresses this by allowing
   heterogeneous blocks with different densities, paradigms, and activities,
   but each block is still internally uniform.

3. **Simplified leakage scaling**: CMOS leakage uses an exponential temperature
   model with a constant reference current (1 nA/gate) across all nodes. In
   reality, leakage current increases at smaller nodes (shorter channels,
   thinner oxides) and depends on threshold voltage, channel length, and DIBL
   in ways that vary by foundry process. At room temperature, leakage energy
   is a small fraction of dynamic energy so this simplification has minimal
   impact on paradigm comparisons.

4. **No interconnect power**: The energy models account for switching energy but
   not interconnect (wire) dissipation, which is a significant fraction of total
   power in advanced nodes.

5. **Steady-state thermal**: The Fourier solver captures transient thermal
   evolution, but does not model time-varying workloads or power gating
   transients.

6. **Thermal boundary model**: In convective mode, the 3D Laplacian treats
   ghost cells outside the lattice as fixed at T_ambient. This models a chip
   conductively coupled to a large thermal reservoir (package substrate or heat
   sink) — the dominant cooling path in real chip packages. Surface convection
   (Newton's law) is applied separately on top. The combined effect is
   realistic for packaged-die analysis.

7. **Cooling stack model**: The `CoolingStack` class models a 1D thermal path
   (die → TIM → IHS → heatsink → ambient) with constant-property layers.
   It does not model 2D/3D spreading resistance, contact imperfections, or
   temperature-dependent thermal conductivity.

8. **Analytical vs 3D models in optimizer**: The `ThermalOptimizer` uses 3D
   simulation for material ranking (captures thermal spreading) and a combined
   conduction + convection 1D model for cooling sensitivity analyses. These
   give different numerical results for the same scenario because they model
   different physical aspects (spreading vs. convective removal). Both are
   documented and appropriate for their respective use cases.

---

## Extending Aethermor for Your Design Flow

For teams integrating Aethermor into an existing thermal workflow:

1. **Calibrate material properties** against your foundry's measured values
   rather than textbook defaults. Material properties in `physics/materials.py`
   are easily overridden.

2. **Compare against SPICE** at the block level: run the same workload profile
   in Aethermor and in a thermal-aware SPICE simulator, then compare power maps.

3. **Validate against your own thermal imaging**: Aethermor already matches
   published IR thermal data (Kandlikar 2003, Bar-Cohen & Wang 2009) and
   JEDEC θ_jc measurements for three commercial chips. The next step is to
   compare against IR measurements of **your specific** test chip with known
   power patterns.

4. **Extend the energy models** for your target paradigm: the framework
   (`physics/energy_models.py`) is designed to be subclassed. Add your own
   gate energy model and it will integrate with the full analysis pipeline.

---

## Contributing New Physics

The most valuable contributions would extend the physics foundation:

- **Additional materials**: Add entries to `MATERIAL_DB` with published
  properties. Each material needs only 6 properties + a name.
- **New energy models**: Subclass the gate energy interface to model
  superconducting logic (SFQ), spintronic gates, photonic switching, or
  domain-specific architectures.
- **Anisotropic thermal transport**: Extend `FourierThermalTransport` to
  support direction-dependent thermal conductivity tensors.
- **Interconnect power models**: Add wire dissipation as a function of
  technology node and metal stack.
- **Thermal interface resistance**: Model the die → TIM → heatsink stack for
  realistic package-level thermal analysis.

See `CONTRIBUTING.md` for guidelines.
