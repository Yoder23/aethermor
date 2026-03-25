# Aethermor: An Open-Source Inverse Thermal Design Toolkit for Thermodynamic Computing Research

**Aethermor Contributors**
March 2026

---

## Abstract

As transistor scaling approaches fundamental thermodynamic limits, hardware
architects increasingly need tools that quantify how close a design sits to
the Landauer limit and what thermal constraints govern achievable compute
density. We present **Aethermor**, an open-source Python toolkit that solves
*inverse* thermal design problems: given a power budget, cooling
architecture, and substrate material, it finds the maximum gate density,
minimum required cooling, optimal power distribution across heterogeneous
functional blocks, and paradigm crossover points — questions that currently
require weeks of manual sweeps in commercial finite-element tools. Aethermor
combines a 3D Fourier thermal solver (0.00% energy conservation error),
ITRS/IRDS-calibrated CMOS energy models, adiabatic and reversible computing
paradigms, nine substrate materials with CRC Handbook properties, multi-layer
cooling stack models, and heterogeneous chip floorplan simulation. A built-in
validation suite of 133 cross-checks against CODATA 2018, analytical
solutions, and published roadmap data ensures physical correctness. We
demonstrate that diamond substrates sustain 17× higher gate density than
silicon at equal cooling, that adiabatic logic provides a 2,006× energy
advantage over CMOS at 1 GHz on a 7 nm node, and that thermal headroom
redistribution on a heterogeneous SoC yields up to 2× throughput improvement.
Aethermor is released under the Apache 2.0 license with an interactive
browser-based explorer, 254 automated tests, and seven ready-to-run research
examples.

---

## 1. Introduction

The semiconductor industry faces a fundamental physical barrier: Dennard
scaling has ended, and each new technology node brings diminishing
energy-per-switch improvements while power density continues to rise
[Dennard 1974, Esmaeilzadeh 2011]. At advanced nodes (≤ 7 nm), the energy
per CMOS gate switch is approximately 2.4 × 10⁻¹⁶ J — still roughly
85,000× above the Landauer limit of k_B T ln 2 ≈ 2.87 × 10⁻²¹ J at room
temperature [Landauer 1961]. This gap defines the thermodynamic design space
that hardware architects must navigate.

Existing thermal simulation tools fall into two categories. *Forward solvers*
(HotSpot [Skadron 2004], COMSOL Multiphysics) compute temperature given a
known power map. *Commercial FEM tools* can in principle solve inverse
problems, but require manual scripting, cost $25,000+ per year, and lack
built-in models for Landauer-aware energy accounting, multi-paradigm
comparisons, and technology roadmap projection. No existing open-source tool
answers questions such as:

- What is the maximum gate density this substrate can sustain?
- What is the minimum cooling coefficient needed for this density?
- How should I distribute compute across functional blocks to maximise
  throughput under a thermal limit?
- At what frequency does adiabatic logic become more efficient than CMOS on
  this material?

Aethermor fills this gap. It is a Python toolkit that combines SI-unit
physics models with inverse design algorithms, enabling hardware researchers
to explore the full thermodynamic design space interactively or
programmatically. This paper describes the architecture, physics models,
validation methodology, and representative results.

---

## 2. System Architecture

Aethermor is organized into three layers, each building on the one below it.

### 2.1 Physics Layer (`physics/`)

**Fundamental Constants.**
All calculations derive from CODATA 2018 exact values: Boltzmann
k_B = 1.380649 × 10⁻²³ J/K, Planck h = 6.62607015 × 10⁻³⁴ J·s. The
Landauer limit is computed as E_min(T) = k_B · T · ln 2.

**Material Database.**
Nine chip substrates are included (Table 1), each with published thermal
conductivity, specific heat, density, electrical resistivity, bandgap, and
maximum operating temperature. All values are sourced from the CRC Handbook
of Chemistry and Physics (97th ed.) and Morkoç (2006, 2008) for wide-bandgap
materials.

| Material | k (W/m·K) | T_max (K) | E_g (eV) |
|----------|-----------|-----------|----------|
| Silicon | 148 | 723 | 1.12 |
| Diamond | 2,200 | 973 | 5.47 |
| SiC (4H) | 490 | 873 | 3.26 |
| GaN | 130 | 873 | 3.40 |
| GaAs | 55 | 623 | 1.42 |
| SiO₂ | 1.4 | 1,673 | 9.0 |
| Copper | 401 | 673 | — |
| InP | 68 | 673 | 1.35 |
| Graphene | 5,000 | 973 | 0.0 |

*Table 1: Substrate materials in Aethermor.*

**Gate Energy Models.**
Four computing paradigms are modelled:

1. **CMOS**: E = ½ C_L V_dd² + E_leak(T), with V_dd and C_L calibrated to
   ITRS 2013 and IRDS 2022 roadmaps across 10 nodes (130–1.4 nm). Leakage
   follows an Arrhenius model.
2. **Adiabatic**: E = R C_L² V_dd² f, proportional to frequency — energy
   approaches zero as f → 0.
3. **Reversible**: E = n_erase · k_B T ln 2 + E_overhead, where n_erase is
   the number of irreversible bit erasures per gate operation.
4. **Landauer floor**: E = k_B T ln 2, the information-theoretic minimum.

**Fourier Thermal Solver.**
A 3D explicit finite-difference solver for the heat equation:

> ρ c_p ∂T/∂t = k ∇²T + q̇

with CFL-stable timestep Δt < Δx²/(6α) where α = k/(ρ c_p). The solver
supports convective, fixed-temperature, and adiabatic boundary conditions.
Energy conservation is verified at every run:
|E_in − E_out − ΔU| / E_in < 5%, with observed error of 0.00%.

**Cooling Stack.**
A `CoolingStack` module models the die-to-ambient thermal path as series
thermal resistances:

> R_total = Σ(t_i / (k_i · A)) + 1/(h_amb · A)

Eleven pre-built materials and six factory configurations are provided
(bare-die, desktop-air, server-air, liquid, direct-liquid,
diamond-spreader-liquid).

**Chip Floorplan.**
A `ChipFloorplan` class defines heterogeneous architectures with distinct
functional blocks (CPU, GPU, cache, I/O), each with independent gate density,
activity factor, technology node, and computing paradigm.

### 2.2 Analysis Layer (`analysis/`)

The analysis layer provides eight inverse thermal design tools
(Section 3), technology roadmap projection, Landauer gap analysis, design
space sweeps with Pareto extraction, thermal regime classification, and
hotspot detection.

### 2.3 Interface Layer

Users interact with Aethermor through three channels: (1) a browser-based
interactive explorer (`app.py`) with six parameterised tabs updated in real
time; (2) a Python scripting API; (3) seven ready-to-run example scripts.

---

## 3. Inverse Thermal Design

The central contribution of Aethermor is solving the inverse thermal design
problem: *given constraints, find the best design*. Eight tools are provided.

### 3.1 Maximum Achievable Gate Density

Given a material and cooling coefficient h, a binary search over the 3D
Fourier solver finds the maximum gate density D_max such that
T_max ≤ T_limit.

### 3.2 Minimum Required Cooling

Given a material and target density D, the combined conduction + convection
1D steady-state model:

> T_max = T_amb + Q · (1/(h·A) + Δx/(2·k·A))

is inverted analytically for h_min:

> h_min = Q / (A · (ΔT − ΔT_cond))

where ΔT_cond = Q·Δx/(2·k·A) is the irreducible conduction floor. If
ΔT_cond ≥ ΔT, no amount of convective cooling suffices — the design
requires a higher-conductivity substrate.

### 3.3 Material Ranking

Runs `find_max_density` across all materials and sorts by D_max. At
h = 1,000 W/(m²·K) on a 7 nm node, diamond sustains 7.0 × 10⁸
gates/element versus silicon's 4.1 × 10⁷ — a 17× advantage (Table 2).

| Material | D_max (gates/elem) | Ratio vs. Si |
|----------|-------------------|-------------|
| Diamond | 7.04 × 10⁸ | 17.2× |
| SiC (4H) | 1.36 × 10⁸ | 3.3× |
| GaN | 8.02 × 10⁷ | 2.0× |
| Silicon | 4.10 × 10⁷ | 1.0× |
| GaAs | 2.49 × 10⁷ | 0.6× |

*Table 2: Material ranking at 7 nm, 1 GHz, h = 1,000 W/(m²·K).*

### 3.4 Cooling Sweep

Sweeps h from natural air (10 W/m²·K) to microchannel cooling
(50,000 W/m²·K), revealing the diminishing-returns regime where the
conduction floor dominates. This makes visible a critical phenomenon:
beyond a material-dependent threshold, improving the cooling infrastructure
yields negligible temperature reduction because the die's own thermal
conductivity is the bottleneck.

### 3.5 Paradigm Comparison

Compares CMOS, adiabatic, and reversible paradigms head-to-head. At 7 nm and
1 GHz, adiabatic switching consumes 1.22 × 10⁻¹⁹ J/gate versus CMOS's
2.45 × 10⁻¹⁶ J/gate — a 2,006× energy reduction. The crossover frequency
where CMOS becomes competitive is f_c = 2.0 THz, well above practical
operating frequencies.

### 3.6 Thermal Headroom Map

Analyses per-block thermal budget utilisation on a heterogeneous SoC. For
each functional block, it computes the steady-state temperature, thermal
headroom (T_limit − T_max), whether the block is the thermal bottleneck, and
how much additional density it could accommodate. A representative SoC
typically reveals that cache and I/O blocks utilise less than 5% of their
thermal budget while the CPU cluster is at the limit.

### 3.7 Power Redistribution Optimizer

Given a total power budget P_budget and thermal limit T_limit, distributes
gate density across functional blocks to maximise total throughput:

> max Σ D_i · N_i · a_i · f
> subject to: T_i ≤ T_limit, Σ P_i ≤ P_budget

The solver identifies whether the design is *thermally limited* (cannot use
all power budget) or *power limited* (thermal headroom available). On a
representative SoC, this yields up to 1.9× throughput improvement.

### 3.8 Full Design Exploration

A single-call entry point that runs all of the above analyses and produces a
comprehensive design space report with automatically generated insights.

---

## 4. Technology Roadmap Projection

The `TechnologyRoadmap` module projects four metrics across 10 technology
nodes (130 nm to 1.4 nm):

1. **Energy per gate switch** for each paradigm, showing how CMOS dynamic
   energy scales as ~V_dd² · C_L while adiabatic energy scales as ~f.
2. **Landauer gap** (ratio of actual energy to k_B T ln 2), showing
   convergence toward the thermodynamic limit at advanced nodes.
3. **Paradigm crossover frequency** — the frequency below which adiabatic
   logic consumes less energy than CMOS at each node.
4. **Thermal wall** — the maximum gate density sustainable on each substrate
   at each node.

Key finding: the Landauer gap for CMOS monotonically decreases from ~10⁷×
at 130 nm to ~10⁴× at 1.4 nm, but remains orders of magnitude above the
limit — confirming that room for improvement exists even at the most advanced
nodes.

---

## 5. Validation

Aethermor includes a self-contained validation suite (133 checks, executable
with a single command) that verifies every physics model against published
reference data.

### 5.1 Constants and Material Properties

Fundamental constants are compared to CODATA 2018 exact values with < 0.01%
tolerance. Material properties are compared to CRC Handbook reference values
with < 0.1% tolerance. Derived quantities are verified for self-consistency.

### 5.2 Energy Model Calibration

CMOS supply voltage at five reference nodes is compared to ITRS 2013 and
IRDS 2022 published values, with all errors below 3%. Key physics
constraints are verified: CMOS energy exceeds the Landauer limit; leakage
increases with temperature; adiabatic energy is below CMOS at low frequency.

### 5.3 Thermal Solver Verification

The 3D solver is verified against the analytical solution for a uniformly
heated slab with convective cooling [Carslaw & Jaeger 1959]. Energy
conservation (|E_in − E_out − ΔU| / E_in) is verified at < 5% with
observed error of 0.00%.

### 5.4 Inverse Design Consistency

Round-trip consistency is verified: `find_max_density` gives T ≈ T_limit at
D_max; `find_min_cooling` gives T ≈ T_limit at h_min; the power optimizer
satisfies its constraints; the headroom map obeys T + headroom = T_limit.

### 5.5 Reproducibility

All functions return identical results across independent runs with the same
inputs. The full test suite (254 tests) and validation suite (133 checks)
execute deterministically.

| Category | Reference | Checks | Status |
|----------|-----------|--------|--------|
| Fundamental constants | CODATA 2018 | 6 | Pass |
| Landauer limit | Landauer (1961) | 5 | Pass |
| Material properties | CRC Handbook | 18 | Pass |
| CMOS energy model | ITRS/IRDS | 13 | Pass |
| Fourier solver | Carslaw & Jaeger | 5 | Pass |
| Analytical 1D model | Manual R-model | 7 | Pass |
| Max density reciprocity | 3D ↔ analytical | 5 | Pass |
| Min cooling inverse | Constraint round-trip | 4 | Pass |
| Optimizer constraints | Budget/thermal/binding | 9 | Pass |
| Headroom map physics | T + h = T_limit | 11 | Pass |
| Cooling stack resistance | Incropera & DeWitt | 4 | Pass |
| Tech roadmap monotonicity | 10 nodes, gap > 1 | 28 | Pass |
| Dimensional analysis | Unit consistency | 4 | Pass |
| Full exploration | Response schema | 11 | Pass |
| Reproducibility | Deterministic | 3 | Pass |

*Table 3: Validation summary (133 checks total).*

---

## 6. Representative Results

### 6.1 Material Selection: Substrate Determines Density Ceiling

At 7 nm, 1 GHz, with forced-air cooling (h = 1,000 W/m²·K), diamond
sustains 7.0 × 10⁸ gates/element — 17× more than silicon (4.1 × 10⁷) and
28× more than GaAs (2.5 × 10⁷). This quantifies a well-known qualitative
principle: substrate thermal conductivity sets the density ceiling. The
advantage persists across all cooling levels because the conduction floor
(determined by k) is the binding constraint at high h.

### 6.2 Paradigm Crossover: Adiabatic Advantage at Practical Frequencies

At 7 nm and room temperature, the CMOS ↔ adiabatic crossover occurs at
f_c = 2.0 THz. Below this frequency — which includes the entire practical
range for digital logic — adiabatic switching is more energy-efficient. The
advantage at 1 GHz is 2,006×.

### 6.3 Heterogeneous SoC: Thermal Budget Redistribution

On a representative modern SoC, the headroom map reveals that I/O and cache
blocks use less than 5% of their thermal budget. The power redistribution
optimizer identifies that reallocating compute density yields up to 1.9×
total throughput improvement — without changing the cooling architecture or
exceeding any block's thermal limit.

---

## 7. Comparison with Existing Tools

| Feature | Aethermor | HotSpot | COMSOL |
|---------|-----------|---------|--------|
| Forward thermal sim | 3D Fourier | Compact | FEM |
| Inverse design | 8 tools | — | Script |
| Landauer gap tracking | Yes | — | — |
| Multi-paradigm | 4 | — | — |
| Multi-material | 9 | Si | Yes |
| Cooling stack | Multi-layer | Partial | Yes |
| Tech roadmap | 10 nodes | — | — |
| SoC headroom map | Per-block | — | — |
| Power redistribution | Yes | — | — |
| Interactive UI | Browser | — | Desktop |
| Open source | Apache 2.0 | BSD | — |
| Cost | Free | Free | $25k+/yr |

*Table 4: Feature comparison with existing tools.*

---

## 8. Limitations and Future Work

We document limitations with the same rigour as capabilities.

**Isotropic thermal model.** All materials are treated as isotropic.
Graphene's extreme in-plane versus cross-plane anisotropy (5,000 vs.
~6 W/m·K) is approximated with a single effective value.

**No interconnect power.** Energy models account for gate switching but not
wire dissipation, which is significant at advanced nodes.

**Simplified leakage.** CMOS leakage uses a constant reference current across
all nodes, ignoring short-channel effects. At room temperature, leakage is a
small fraction of dynamic energy, so impact on paradigm comparisons is
minimal.

**Validation scope.** The thermal model has been validated against published
specifications for four real chips (NVIDIA A100, Apple M1, AMD EPYC 9654,
Intel i9-13900K) and produces correct-order-of-magnitude junction temperature
predictions (33 checks, all passing). Die-level correlation with proprietary
floorplan data or direct thermal imaging is a planned next step.

**Steady-state focus.** The inverse design tools target steady-state. Dynamic
workloads, power gating, and DVFS are future work.

**1D cooling stack.** The `CoolingStack` does not model 2D/3D spreading
resistance or temperature-dependent properties.

---

## 9. Availability and Reproducibility

Aethermor is released under the Apache 2.0 license at:

> https://github.com/Yoder23/aethermor

To reproduce all results in this paper:

```bash
git clone https://github.com/Yoder23/aethermor
cd aethermor
pip install -e ".[all]"
python -m validation.validate_all   # 133 checks
python -m pytest tests/ -v          # 254 tests
python app.py                       # Interactive UI
```

All random number generators are seeded for deterministic output. The
validation suite encodes the exact numerical checks presented in this paper
and can be run on any machine with Python ≥ 3.10 and NumPy.

---

## 10. Conclusion

Aethermor provides an integrated open-source toolkit for inverse thermal design
in thermodynamic computing research.  By combining calibrated energy models,
validated thermal solvers, and systematic inverse design algorithms, it
compresses the exploratory workflow for material selections, cooling
trade-offs, paradigm crossovers, and heterogeneous SoC optimisations into
interactive, sub-second queries. The built-in validation suite of 133 cross-checks
against published data ensures that every result is grounded in verified
physics. As transistor scaling pushes designs closer to the Landauer limit,
tools like Aethermor become essential for navigating the narrowing design
space between what physics allows and what engineering can achieve.

---

## References

1. R. Landauer, "Irreversibility and heat generation in the computing
   process," *IBM J. Res. Dev.*, vol. 5, no. 3, pp. 183–191, 1961.

2. R. H. Dennard, F. H. Gaensslen, H. N. Yu, V. L. Rideout, E. Bassous,
   and A. R. LeBlanc, "Design of ion-implanted MOSFET's with very small
   physical dimensions," *IEEE J. Solid-State Circuits*, vol. 9, no. 5,
   pp. 256–268, 1974.

3. H. Esmaeilzadeh, E. Blem, R. St. Amant, K. Sankaralingam, and D. Burger,
   "Dark silicon and the end of multicore scaling," in *Proc. ISCA*, 2011,
   pp. 365–376.

4. K. Skadron, M. R. Stan, K. Sankaranarayanan, W. Huang, S. Velusamy, and
   D. Tarjan, "Temperature-aware microarchitecture: Modeling and
   implementation," *ACM Trans. Archit. Code Optim.*, vol. 1, no. 1,
   pp. 94–125, 2004.

5. International Technology Roadmap for Semiconductors, *ITRS 2013 Edition*,
   Semiconductor Industry Association, 2013.

6. IEEE International Roadmap for Devices and Systems, *IRDS 2022 Edition*,
   IEEE, 2022.

7. E. Tiesinga, P. J. Mohr, D. B. Newell, and B. N. Taylor, "CODATA
   recommended values of the fundamental physical constants: 2018,"
   *Rev. Mod. Phys.*, vol. 93, no. 2, 025010, 2021.

8. W. M. Haynes, Ed., *CRC Handbook of Chemistry and Physics*, 97th ed.,
   CRC Press, 2016.

9. H. S. Carslaw and J. C. Jaeger, *Conduction of Heat in Solids*, 2nd ed.,
   Oxford University Press, 1959.

10. H. Morkoç, "SiC and GaN based devices — review and challenges," in
    *Proc. SPIE*, vol. 6127, 2006.

11. H. Morkoç, *Handbook of Nitride Semiconductors and Devices*, Wiley, 2008.

12. F. P. Incropera, D. P. DeWitt, T. L. Bergman, and A. S. Lavine,
    *Fundamentals of Heat and Mass Transfer*, 7th ed., Wiley, 2011.
