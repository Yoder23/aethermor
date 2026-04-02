# Aethermor

[![CI](https://github.com/Yoder23/aethermor/actions/workflows/ci.yml/badge.svg)](https://github.com/Yoder23/aethermor/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Yoder23/aethermor)](https://github.com/Yoder23/aethermor/releases)

**Open-source Python toolkit for chip thermal analysis, cooling tradeoffs, and compute-density limits in advanced hardware systems.**

---

As transistor scaling slows, **thermal constraints are becoming the primary
bottleneck in computing**. Aethermor provides the tools to model, analyze, and
design around those constraints — interactively or programmatically.

### What you can do with Aethermor

- **Find compute-density limits** — how many gates can a substrate actually sustain before thermal runaway?
- **Explore cooling tradeoffs** — at what point does better cooling stop helping?
- **Compare chip architectures** — CMOS vs. adiabatic vs. reversible logic under real thermal constraints
- **Locate thermal bottlenecks** — per-block headroom analysis on heterogeneous SoCs
- **Project technology scaling** — energy and thermal wall from 130 nm down to 1.4 nm
- **Test your own materials** — plug in custom substrates, paradigms, and cooling layers

All models use real physics in SI units, validated against CODATA 2018, the CRC
Handbook, ITRS/IRDS roadmaps, published specifications for real chips
(NVIDIA A100, Apple M1, AMD EPYC, Intel i9-13900K), and published hardware
measurements (JEDEC θ_jc thermal resistance, IR thermal imaging, HotSpot
benchmarks). **Scope: Architecture-stage thermal exploration and inverse design. Not intended for sign-off, transient package verification, or transistor-level thermal closure.** Calibration status: analytically validated with published material data, plausibility-checked against 15 production chips, and hardware-correlated against 3 published chip designs (A100, i9-13900K, M1) with full gap analysis. See [LIMITATIONS.md](LIMITATIONS.md) for scope, [docs/HARDWARE_CORRELATION.md](docs/HARDWARE_CORRELATION.md) for correlation evidence, and [docs/calibration_case_study.md](docs/calibration_case_study.md) for calibration methodology.

---

## Case Study: The Cooling Upgrade That Wouldn't Help

> *Full writeup: [docs/CASE_STUDY.md](docs/CASE_STUDY.md) · Run it: `python benchmarks/case_study_cooling_decision.py`*

A team designing a 5 nm AI accelerator is considering a **$2M data center
retrofit** to upgrade from air cooling to direct liquid cooling. Their
assumption: 20× more aggressive cooling should unlock significantly more
compute density.

Aethermor's model suggests this assumption is wrong — in about 10 seconds:

| Strategy | Density Gain | Cost |
|----------|-------------|------|
| Upgrade to liquid cooling (20× more aggressive) | **0.3%** | $2M retrofit |
| Switch to SiC substrate (same air cooling) | **232%** | Per-die premium |
| Redistribute compute across SoC blocks | **47% throughput** | **Free** |

The reason: silicon's conduction floor — an irreducible thermal resistance
set by the substrate's thermal conductivity — means heat can't leave the die
interior fast enough regardless of how well you cool the surface. Switching
substrate is 780× more effective than upgrading cooling. And redistributing
compute from the thermally-limited GPU block to the underutilized L3 cache
(26× thermal headroom) gives 47% more throughput with zero hardware changes.

This is the type of non-obvious tradeoff that architecture-stage thermal
exploration can surface before committing to expensive hardware decisions.

---

## Start Here (Thermal Engineers)

New to Aethermor? Follow this 5-minute evaluation path:

```bash
# 1. Install
git clone https://github.com/Yoder23/aethermor.git && cd aethermor
pip install -e ".[all]"

# 2. Run the full validation suite — 700+ validation checks, ~3 min
python run_all_validations.py

# 3. Try an inverse-design question
python examples/optimal_density.py

# 4. Launch the interactive dashboard
aethermor dashboard
```

**What to look at first**:

| Your Interest | Start With |
|---------------|-----------|
| "Does the physics check out?" | [docs/calibration_case_study.md](docs/calibration_case_study.md) — θ_jc correlation + plausibility checks |
| "What can it actually do?" | [docs/CASE_STUDY.md](docs/CASE_STUDY.md) — cooling vs substrate decision |
| "What are the limitations?" | [LIMITATIONS.md](LIMITATIONS.md) — scope, simplifications, known gaps |
| "How accurate is it?" | [docs/ACCURACY.md](docs/ACCURACY.md) — error bands and operating envelope |
| "Full API reference" | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |

---

## Quick Start

```bash
git clone https://github.com/Yoder23/aethermor.git
cd aethermor
pip install -e ".[dashboard]"      # core + interactive UI
aethermor dashboard                # open http://127.0.0.1:8050
```

Or install directly from the release wheel:

```bash
pip install https://github.com/Yoder23/aethermor/releases/download/v1.0.1/aethermor-1.0.1-py3-none-any.whl
```

> **Core only** (no UI): `pip install -e .`
> **Everything** (dev + UI): `pip install -e ".[all]"`

---

## Interactive Explorer Dashboard

```bash
aethermor dashboard
```

The built-in dashboard lets you interactively explore thermal design spaces
with live-updating charts. Every parameter is a slider or dropdown:

| Tab | What You Can Do |
|-----|-----------------|
| **Material Ranking** | Pick a tech node, frequency, and cooling — see which substrate lets you pack the most compute |
| **Cooling Analysis** | Set a material and gate density — see temperature vs. cooling with the conduction floor |
| **Paradigm Comparison** | Drag the frequency slider to watch the CMOS ↔ adiabatic crossover shift in real time |
| **Technology Roadmap** | Energy per gate and Landauer gap from 130 nm down to 1.4 nm |
| **SoC Thermal Map** | Thermal headroom per block on a heterogeneous CPU+GPU+cache+IO chip — find the bottleneck |
| **Custom Material** | Define your own substrate by entering its thermal properties — it instantly appears in every other tab |

![Explorer Dashboard — Material Ranking](docs/screenshot.png)

*The Material Ranking tab comparing maximum compute density across five
substrates at the 7 nm node and 1 GHz. Diamond sustains 28× higher gate
density than GaAs under the same thermal and cooling constraints.*

---

## Python API

Every capability in the dashboard is also available as a Python function.

```python
from aethermor.analysis.thermal_optimizer import ThermalOptimizer

opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

# Material ranking: which substrate sustains the highest compute density?
ranking = opt.material_ranking(h_conv=1000.0)
for r in ranking:
    print(f"{r['material_name']:<25s}  {r['max_density']:.2e} gates/elem")

# Minimum cooling for a target density
req = opt.find_min_cooling("silicon", gate_density=1e5)
print(f"Min h_conv: {req['min_h_conv']:.0f} W/(m²·K)  →  {req['cooling_category']}")
```

```python
# Thermal bottleneck analysis on a heterogeneous SoC
from aethermor.physics.chip_floorplan import ChipFloorplan

soc = ChipFloorplan.modern_soc()
headroom = opt.thermal_headroom_map(soc, h_conv=1000.0)
for block in headroom:
    print(f"{block['name']:<20s}  T={block['T_max_K']:.0f} K  headroom={block['density_headroom_factor']:.1f}×")
```

```python
# Custom materials plug into the optimizer and dashboard
from aethermor.physics.materials import registry, Material

registry.register("hex_bn", Material(
    name="Hexagonal Boron Nitride (h-BN)",
    thermal_conductivity=600.0, specific_heat=800.0, density=2100.0,
    electrical_resistivity=1e15, max_operating_temp=1273.15, bandgap_eV=6.0,
))
```

For more: [docs/API_REFERENCE.md](docs/API_REFERENCE.md) · 7 ready-to-run scripts in [`examples/`](examples/)

---

## Verification

```bash
python -m pytest tests/ -v              # 308 unit/integration/robustness tests, ~2 min
python run_all_validations.py           # 12+ suites, 700+ checks, ~3 min
```

Individual benchmark suites are in [`benchmarks/`](benchmarks/). Key ones:

| Suite | Checks | What It Validates |
|-------|--------|-------------------|
| `experimental_validation.py` | 18 | JEDEC θ_jc, IR imaging, HotSpot — published measurements |
| `chip_thermal_database.py` | 82 | 12 real chips across 4 segments |
| `material_cross_validation.py` | 93 | 9 materials vs CRC, ASM, NIST, Ioffe |
| `real_world_validation.py` | 33 | 4 published chip designs (A100, M1, EPYC, i9) |
| `literature_validation.py` | 20 | CODATA, CRC, ITRS, Incropera & DeWitt |

Case studies: [`benchmarks/case_study_datacenter.py`](benchmarks/case_study_datacenter.py),
[`benchmarks/case_study_mobile_soc.py`](benchmarks/case_study_mobile_soc.py),
[`benchmarks/case_study_cooling_decision.py`](benchmarks/case_study_cooling_decision.py)

---

## Who This Is For

Aethermor is for **architecture-stage thermal engineering** — deciding *what*
to build before committing to detailed design.

- **Chip architects** exploring substrates, cooling, and density targets
- **Thermal engineers** evaluating cooling stacks and identifying diminishing returns
- **Computer architecture researchers** studying thermal tradeoffs across paradigms

Aethermor helps identify which designs are worth simulating in detail — and
which assumptions to challenge before committing silicon.

## Project Layout

```
aethermor/                # Installable Python package
  physics/                # SI-unit thermodynamic models (extensible registries)
  analysis/               # Inverse design & research tools
  simulation/             # Monte Carlo / evolutionary simulation engine
  validation/             # 133 physics cross-checks
  app/                    # Interactive dashboard (modular tab architecture)
  cli.py                  # CLI entry point: aethermor dashboard|validate|version
benchmarks/               # Validation, correlation, and case-study scripts
examples/                 # 10 ready-to-run research scripts + 3 team workflows
tests/                    # 308 unit, integration, regression, robustness tests
```

Module details: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

## Validation & Calibration

Aethermor is built on established heat transfer and semiconductor physics.
Models are cross-validated against published reference data:

| Check | Result |
|-------|--------|
| Unit + integration tests | 308 pass, 1 skipped |
| Physics validation | 133 cross-checks vs CODATA 2018, CRC Handbook, ITRS/IRDS | 
| Material cross-validation | 93 checks, 9 materials vs CRC, ASM, NIST, Ioffe |
| Chip thermal database | 82 checks across 12 real chips in 4 segments |
| Experimental measurements | 18 checks vs JEDEC θ_jc, IR imaging, HotSpot |
| Hardware correlation (3 chips) | PackageStack with Yovanovich spreading vs measured θ_jc / T_j — A100 0.98×, i9 +9 K, M1 within range |
| External benchmark pack | 6 analytical cases (1D slab, convection, multi-layer, Landauer, PackageStack, max-power) |
| Energy conservation | 0.00% error in 3D Fourier solver |
| **Total checks** | **700+** (see [docs/VERIFICATION_LAYERS.md](docs/VERIFICATION_LAYERS.md) for exact breakdown) |

See [VALIDATION.md](VALIDATION.md) for methodology. Run `python run_all_validations.py` to verify.

### Expected Accuracy

| Calculation Type | Expected Accuracy | Notes |
|-----------------|-------------------|-------|
| **Relative comparisons** (material A vs B, cooling X vs Y) | High confidence | Ordering and ratios are physics-correct |
| **Absolute junction temperatures** | ±5–15% (±10 K demonstrated) | Depends on h_conv accuracy and package model fidelity; see [HARDWARE_CORRELATION](docs/HARDWARE_CORRELATION.md) |
| **Cooling requirement estimates** | ±10–20% | Simplified convection (single h_conv coefficient) |
| **Material thermal properties** | < 5% vs published | Cross-validated against CRC, ASM, NIST |

**Calibration details**: [docs/calibration_case_study.md](docs/calibration_case_study.md) — θ_jc
residual analysis for A100 (0.98×), i9-13900K (+9 K), M1 (+5 K); experimental
temperature correlation against 4 published studies; 15-chip plausibility check.

**Safe-use limits**: This is a 1D/reduced-order model. Detailed package
geometry, mixed convection, transient dynamics, and board-level paths are
out of scope. See [LIMITATIONS.md](LIMITATIONS.md).

### When This Model Breaks

| Scenario | Why It Breaks | What To Use Instead |
|----------|---------------|---------------------|
| Complex 3D package geometry | 1D conduction ignores spreading, TIM, IHS | COMSOL, ANSYS Icepak |
| Turbulent / mixed convection | Single h_conv; no flow modeling | CFD (Fluent, OpenFOAM) |
| Transient thermal dynamics | Steady-state only | HotSpot transient, COMSOL |
| Detailed TIM / solder modeling | `PackageStack` includes die/TIM/IHS contact resistances; for detailed package FEA use COMSOL | Package-level FEA |
| PCB / board-level thermal paths | Die-only model | 6SigmaET, FloTHERM |

**Rule of thumb**: "Which direction should we go?" → Aethermor.
"Exactly how hot is this die corner at t = 3.7 ms?" → FEA/CFD.

See [LIMITATIONS.md](LIMITATIONS.md).

### Aethermor vs. CFD/FEA Tools

| | Aethermor | COMSOL / Icepak / FloTHERM |
|---|---|---|
| **Speed** | Seconds | Hours–days per geometry |
| **Setup** | `pip install`, 3 lines of Python | License, mesh, BCs, convergence |
| **Accuracy (absolute)** | ±5–15% (±10 K on 3 chips) | ±1–3% |
| **Accuracy (ranking)** | High | High |
| **Inverse design** | Built-in | Manual parameter sweeps |
| **Sign-off** | Not suitable | Required |
| **Cost** | Free (Apache 2.0) | $10K–$100K/year |

Use Aethermor to decide which designs are worth simulating in CFD/FEA.

## Documentation

| Category | Documents |
|----------|-----------|
| **Getting started** | [INSTALL_VERIFY](docs/INSTALL_VERIFY.md) · [API_REFERENCE](docs/API_REFERENCE.md) · [SAFE_USE](docs/SAFE_USE.md) |
| **Case studies** | [Calibration](docs/calibration_case_study.md) · [Datacenter GPU](docs/case_study_datacenter_gpu.md) · [Cooling/Substrate](docs/CASE_STUDY.md) · [SoC](docs/CASE_STUDY_SOC.md) · [Paradigm](docs/CASE_STUDY_PARADIGM.md) |
| **Validation** | [VALIDATION](VALIDATION.md) · [LIMITATIONS](LIMITATIONS.md) · [HONEST_REVIEW](HONEST_REVIEW.md) · [ACCURACY](docs/ACCURACY.md) · [Uncertainty](docs/uncertainty_sensitivity.md) · [External](docs/EXTERNAL_VALIDATION.md) · [Reproducibility](docs/REPRODUCIBILITY.md) · [Benchmark protocol](docs/benchmark_protocol.md) |
| **Governance** | [CHANGELOG](CHANGELOG.md) · [Release notes](RELEASE_NOTES_v1.0.0.md) · [SEMVER](docs/SEMVER.md) · [Support](docs/SUPPORT_POLICY.md) |

## Reproducibility

```bash
python run_all_validations.py    # 12+ suites, 700+ checks, ~3 min
```

All benchmarks are seeded and deterministic. See
[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for seed policy and tolerances.

## References

Aethermor's physics models and material data are grounded in:

1. **Incropera, F.P. et al.** *Fundamentals of Heat and Mass Transfer*, 8th ed.
   Wiley, 2019. — Conduction, convection, and thermal resistance theory.

2. **Lide, D.R. (ed.)** *CRC Handbook of Chemistry and Physics*, 101st ed.
   CRC Press, 2020. — Thermal conductivity, specific heat, density for
   Si, SiO₂, GaAs, diamond, Cu, InP, SiC, GaN.

3. **ITRS/IRDS** *International Roadmap for Devices and Systems*, IEEE, 2022.
   — Technology node scaling parameters connected to CMOS gate energy models.

4. **CODATA 2018** *Recommended Values of the Fundamental Physical Constants*.
   NIST, 2019. — Boltzmann constant, Planck constant used in Landauer limit.

5. **Carslaw, H.S. & Jaeger, J.C.** *Conduction of Heat in Solids*, 2nd ed.
   Oxford, 1959. — Fourier heat diffusion formulation.

6. **Skadron, K. et al.** "Temperature-Aware Microarchitecture: Modeling and
   Implementation", *ACM TACO*, 2004. — HotSpot methodology for comparison
   benchmarks.

Material property sources are individually attributed in
[docs/ACCURACY.md](docs/ACCURACY.md).

## Contributing

Contributions welcome — especially new materials, computing paradigms,
thermal models, or analysis tools. The registry architecture makes it
easy to add new components without touching core code:

- **New material?** → `registry.register("my_mat", Material(...))` 
- **New paradigm?** → `paradigm_registry.register("my_idea", MyModelClass)`
- **New cooling layer?** → `cooling_registry.register("my_tim", ThermalLayer(...))`

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
