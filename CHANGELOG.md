# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- **Yovanovich (1983) spreading resistance** in `PackageStack` — new
  `spreading_area_m2` parameter models die-to-IHS/chassis thermal spreading.
  Dramatically improves hardware correlation: A100 θ_jc from 1.97× to 0.98×,
  i9-13900K T_j +9 K, M1 T_j within published range (+5 K).
- **Independent textbook validation** (`benchmarks/independent_textbook_validation.py`)
  — 16 checks against hand-calculable references (Incropera, CRC Handbook,
  Landauer 1961, Yovanovich 1983). All pass at 0.00% error.
- **`PackageStack` in API_REFERENCE.md** — full constructor, method table,
  factory methods, contact resistance reference, and spreading resistance docs.

### Changed
- `PackageStack.theta_jc()` now includes spreading resistance when
  `spreading_area_m2` is set.
- Hardware correlation benchmark (`benchmarks/hardware_correlation.py`)
  rewritten with spreading resistance and ψ_jc vs θ_jc distinction for Intel.
- Documentation updates across 15+ files to reflect improved residuals.
- All "277" test count references updated to 308 (or annotated with
  "(at v1.0.0; now 308+)" in historical documents).
- Install links updated from v1.0.0 to v1.0.1 in INSTALL_VERIFY.md.
- External validation: peer review documented as Pilot 2 (5 rounds,
  15+ issues found and resolved).

## [1.0.1] - 2026-03-31

### Added — Peer Review Response
- **Package restructure**: All modules moved under `aethermor/` namespace
  (`aethermor.physics`, `aethermor.analysis`, `aethermor.validation`,
  `aethermor.simulation`). Proper installable package with `pip install -e .`.
- **CLI entry point**: `aethermor dashboard`, `aethermor validate`,
  `aethermor version` via `[project.scripts]` in pyproject.toml.
- **Dashboard split**: Monolithic `app.py` (730 lines) replaced with modular
  `aethermor/app/` package — 6 tab modules + shared utils + main entry point.
- **Calibration case study**: `docs/calibration_case_study.md` — 15 real
  production chips (A100, H100, MI300X, i9-13900K, Ryzen 7950X, RTX 4090, etc.)
  validated against datasheet Tj_max values.
- **Datacenter GPU case study**: `docs/case_study_datacenter_gpu.md` — 8-GPU
  node cooling decision matrix (air vs liquid vs substrate).
- **Uncertainty & sensitivity analysis**: `docs/uncertainty_sensitivity.md` —
  Monte Carlo uncertainty propagation, OAT sensitivity, transient roadmap.
- **README enhancements**: "Start Here" evaluation guide, validation summary
  table, expected accuracy section, "When This Model Breaks" failure modes,
  CFD comparison table, reproducibility section, academic references.

### Changed
- All 65+ source files updated from `physics.*` → `aethermor.physics.*` imports.
- All `sys.path.insert` hacks removed (20 files).
- All documentation updated for new package paths and consistent test counts.
- pyproject.toml: `packages.find` now includes only `aethermor*`.

### Removed
- Monolithic `app.py` — replaced by `aethermor/app/` modular architecture.
- All `sys.path` manipulation from `tests/conftest.py`.

## [1.0.0] - 2026-03-25

### Added — Experimental Measurement Validation
- `benchmarks/experimental_validation.py`: 18 checks validating the thermal model
  against published hardware measurements:
  - **Tier 1**: JEDEC-standard junction-to-case thermal resistance (θ_jc) for
    NVIDIA A100, Intel i9-13900K, AMD Ryzen 7950X
  - **Tier 2**: Published experimental data — Kandlikar 2003 microchannel ΔT,
    Bar-Cohen & Wang 2009 IR hotspot, Yovanovich 1998 spreading resistance,
    full-path junction temperature for 100 W desktop package
  - **Tier 3**: HotSpot ev6 benchmark, Incropera analytical, Biot number,
    thermal time constant, COMSOL-verified fin geometry, 3D Fourier energy
    conservation
- CI pipeline now runs experimental measurement validation on every push

### Changed
- Version bumped to 1.0.0 — validated for architecture-stage engineering.
  **Why**: 680+ validated checks now pass including experimental hardware
  measurements; the project meets the standard for architecture-stage tooling.
- Development Status classifier upgraded from "4 - Beta" to "5 - Production/Stable".
  **Why**: All validation tiers (specifications, measurements, literature,
  analytical solutions) are passing; no known blockers remain.
  **Note (v1.0.1):** Classifier was subsequently downgraded back to
  "4 - Beta" to better align with architecture-stage scope.
- Updated VALIDATION.md with experimental measurement validation section.
  **Why**: New Tier 2 checks (JEDEC θ_jc, IR imaging, HotSpot) needed
  documentation alongside the existing literature cross-checks.
- Updated LIMITATIONS.md: "Not Validated Against Direct Silicon Measurement" →
  "Validated Against Published Hardware Measurements — Not Custom Test Chips".
  **Why**: The 18 experimental checks close the "no hardware validation" gap
  while honestly scoping what "validated" means (published data, not our own
  test chips).
- Updated HONEST_REVIEW.md: added 18 experimental checks to validation grade,
  OSS readiness upgraded to "Validated for architecture-stage engineering".
  **Why**: The self-assessment must track the actual validation state.
- CI matrix tests Python 3.10, 3.11, and 3.12.
  **Why**: Production users run multiple Python versions; 3.12 is the current
  stable release.

## [0.1.0] - 2026-03-24

### Added — Real-World Chip Validation
- `benchmarks/real_world_validation.py`: 33 checks validating thermal predictions
  against published specifications for NVIDIA A100, Apple M1, AMD EPYC 9654, and
  Intel i9-13900K
- Junction temperature predictions within expected ranges using first-principles
  physics (conduction + package heat spreading + convection)
- CI pipeline now runs literature and real-world chip validation on every push

### Added — Benchmarks and Case Studies
- `benchmarks/hotspot_comparison.py`: Fair 6-test comparison against HotSpot,
  showing where each tool adds value
- `benchmarks/literature_validation.py`: 20 cross-checks against CODATA, CRC
  Handbook, ITRS/IRDS, Incropera & DeWitt
- `benchmarks/case_study_substrate_selection.py`: Substrate selection workflow
  answering 4 questions in ~9 seconds
- `benchmarks/case_study_soc_bottleneck.py`: SoC bottleneck identification and
  power reallocation

### Added — Physics Foundation
- `physics/` package with real SI-unit thermodynamic models:
  - `constants.py`: Boltzmann constant (CODATA 2018), Landauer limit, thermal
    noise, bits-per-joule
  - `materials.py`: 9 substrate materials (Si, SiO₂, GaAs, Diamond, Graphene,
    Cu, InP, SiC, GaN) with published thermal/electrical properties, plus
    extensible MaterialRegistry with validation, JSON import/export
  - `energy_models.py`: 4 gate energy paradigms (CMOS, adiabatic, reversible,
    Landauer floor) with crossover calculations, plus extensible ParadigmRegistry
    with EnergyModel protocol enforcement
  - `thermal.py`: 3D Fourier thermal transport with CFL stability, convective/
    fixed/adiabatic boundaries, hotspot detection, 0.00% energy conservation error
  - `cooling.py`: Multi-layer cooling stacks (11 built-in layers, 6 factory
    configurations), plus extensible CoolingRegistry with validation
  - `chip_floorplan.py`: Heterogeneous SoC model with per-block paradigm,
    activity, tech node, and density; factory methods for modern SoC and
    hybrid CMOS/adiabatic layouts

### Added — Research Analysis Tools
- `analysis/` package:
  - `thermal_optimizer.py`: 8 inverse design tools — max density, min cooling,
    material ranking, cooling sweep, paradigm comparison, thermal headroom map,
    power redistribution optimizer, full design exploration
  - `tech_roadmap.py`: Technology node projections (130 nm → 1.4 nm) — energy
    per gate, Landauer gap, paradigm crossover, thermal wall
  - `design_space.py`: Multi-dimensional parameter sweeps with Pareto extraction
  - `regime_map.py`: 5-regime classification (deep_classical → near_limit),
    crossover analysis, thermal density limits
  - `landauer_gap.py`: Distance-from-limit analysis (spatial, per-node,
    per-temperature)
  - `thermal_map.py`: Hotspot detection, cooling efficiency maps

### Added — Interactive Explorer UI
- `aethermor/app/`: Modular Dash-based interactive explorer with 6 tabs:
  - Material Ranking, Cooling Analysis, Paradigm Comparison,
    Technology Roadmap, SoC Thermal Map, Custom Material registration

### Added — Extensibility Architecture
- MaterialRegistry: register/unregister custom substrates with physical bounds
  validation, key normalization, JSON save/load
- ParadigmRegistry: register custom computing paradigms with runtime
  EnergyModel protocol checking; chip_floorplan uses registry instead of
  hardcoded dispatch
- CoolingRegistry: register custom thermal interface layers with validation
  and JSON serialization
- All registries support `save_json()` / `load_json()` for sharing configurations

### Added — Research Examples
- `examples/optimal_density.py`: Thermal wall analysis per substrate
- `examples/adiabatic_crossover.py`: Paradigm crossover mapping
- `examples/material_comparison.py`: Substrate and cooling strategy comparison
- `examples/heterogeneous_soc.py`: SoC hotspot analysis with cooling stacks
- `examples/technology_roadmap.py`: 130 nm → 1.4 nm projections
- `examples/thermal_optimizer.py`: Inverse design — headroom and power redistribution
- `examples/custom_material.py`: Register custom material, paradigm, and cooling layer

### Added — Validation & Testing
- 254 unit, integration, regression, and performance tests (pytest)
- 133 physics cross-checks (`python -m aethermor.validation.validate_all`) against
  CODATA 2018, CRC Handbook, ITRS/IRDS, analytical solutions
- 43 registry-specific tests covering all three extensible registries

### Added — Paper
- `paper/aethermor_paper.tex`: arXiv-ready LaTeX paper with all claims
  verified against live computation
- `paper/aethermor_paper.md`: Markdown companion

### Added — OSS Infrastructure
- `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- `CITATION.cff`, `.gitignore`, `.gitattributes`, `pyproject.toml`
- CI: `.github/workflows/ci.yml` (test + dependency audit)
- `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.md`

### Changed — Project Structure
- Moved legacy simulation scripts (12 files) from project root into
  `simulation/` package for a clean, documented directory layout.
  **Why**: A flat root with 20+ scripts is unprofessional and makes it hard
  to distinguish production code from experimental scripts.
