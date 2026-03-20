# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-03-12

### Added — Physics Foundation
- `physics/` package with real SI-unit thermodynamic models:
  - `constants.py`: Boltzmann constant (CODATA 2018), Landauer limit, thermal
    noise, bits-per-joule
  - `materials.py`: 9 substrate materials (Si, SiO₂, GaAs, diamond, graphene,
    Cu, InP, SiC, GaN) with published thermal/electrical properties
  - `energy_models.py`: 4 gate energy paradigms (CMOS, adiabatic, reversible,
    Landauer floor) with crossover calculations
  - `thermal.py`: 3D Fourier thermal transport with CFL stability, convective/
    fixed/adiabatic boundaries, hotspot detection

### Added — Research Analysis Tools
- `analysis/` package:
  - `landauer_gap.py`: distance-from-limit analysis (spatial, per-node,
    per-temperature)
  - `design_space.py`: multi-dimensional sweeps with Pareto extraction
  - `regime_map.py`: 5-regime classification, crossover analysis, thermal
    density limits
  - `thermal_map.py`: hotspot detection, cooling efficiency maps

### Added — Physically-Grounded Simulation
- `physical_simulation.py`: `PhysicalSimulation` class producing Joules, Kelvin,
  W/cm², with paradigm and material comparison methods

### Added — Research Examples
- `examples/optimal_density.py`: thermal wall analysis per substrate
- `examples/adiabatic_crossover.py`: paradigm crossover mapping
- `examples/material_comparison.py`: substrate and cooling strategy comparison

### Added — Statistical Framework
- Publication-grade statistical ablation pipeline with:
  - paired/unpaired tests
  - Holm/FDR corrections
  - bootstrap CI for paired deltas
  - run manifest outputs
- Cross-configuration publication robustness sweep
- Automated publication gate with strict threshold checks
- Full project manuscript: `AETHERMOR_FULL_PROJECT_PAPER.md`

### Added — OSS Infrastructure
- `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- `CITATION.cff`, `.gitignore`, `.gitattributes`, `pyproject.toml`
- CI: `.github/workflows/ci.yml` (test + dependency audit)
- `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.md`
- Reproduction scripts: `scripts/reproduce_strict.ps1`, `scripts/reproduce_strict.sh`
- Honest review (`HONEST_REVIEW.md`) and research scope (`LIMITATIONS.md`)
- Methodology tests proving original benchmark design is parameter-driven

### Validation
- Full test suite: `97 passed, 1 skipped` (64 physics + 34 framework tests)
