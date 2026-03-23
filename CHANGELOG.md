# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-03-23

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
- `app.py`: Dash-based interactive explorer with 6 tabs:
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
- 133 physics cross-checks (`python -m validation.validate_all`) against
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
  `simulation/` package for a clean, documented directory layout
