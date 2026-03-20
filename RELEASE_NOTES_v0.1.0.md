# Aethermor v0.1.0 Release Notes

## Release Scope

This release publishes Aethermor as a physically-grounded simulation toolkit for
thermodynamic computing research. It includes real-physics models in SI units,
research analysis tools, and a 3D lattice simulation framework.

## Key Additions

### Physics Foundation (`physics/`)
- Fundamental constants (CODATA 2018) and Landauer limit calculations
- 9 substrate materials (Si, SiO₂, GaAs, diamond, graphene, Cu, InP, SiC, GaN)
- 4 gate energy models (CMOS, adiabatic, reversible, Landauer floor)
- 3D Fourier thermal transport with CFL stability and boundary conditions

### Research Analysis Tools (`analysis/`)
- Landauer gap analysis (spatial maps, technology scaling, temperature scaling)
- Design space sweeps with Pareto frontier extraction
- 5-regime classification (deep_classical → near_limit)
- Thermal hotspot detection and cooling efficiency maps

### Physically-Grounded Simulation
- `PhysicalSimulation` class producing Joules, Kelvin, W/cm²
- Paradigm comparison (CMOS vs. adiabatic vs. reversible)
- Material comparison across substrates

### Research Examples (`examples/`)
- `optimal_density.py` — thermal wall analysis per substrate
- `adiabatic_crossover.py` — paradigm crossover mapping
- `material_comparison.py` — substrate comparison with cooling strategies

### Statistical Framework
- Publication-grade ablation framework (`experiments/exp_ablations.py`)
  - paired ON/OFF design
  - paired/unpaired tests
  - bootstrap confidence intervals
  - Holm/FDR multiple-testing correction
  - run manifest outputs
- Cross-configuration robustness sweeps (`experiments/exp_publication_robustness.py`)
- Automated publication gate (`publication_gate.py`)
- Benchmark runner (`run_all_benchmarks.py`)

## Validation Summary

Latest test suite: `97 passed, 1 skipped` (dashboard test skipped without `dash`).

64 physics/analysis tests + 34 existing framework tests.

Reproducible validation:
- `python run_all_benchmarks.py` runs all four benchmarks
- `python experiments/exp_ablations.py` runs seeded ON/OFF ablations
- `python publication_gate.py` checks publication-readiness thresholds

## Core Evidence Paths

Generated evidence (after running benchmarks):
- `artifacts/_report/ablations_statistical.csv`
- `artifacts/_report/ablations_manifest.json`
- `artifacts/_report/publication_gate.json`

Manuscript:
- `AETHERMOR_FULL_PROJECT_PAPER.md`

## Reproduction Commands

PowerShell:

```powershell
$env:BENCH_STEPS="80"
$env:ABLATION_N="10"
$env:ABLATION_BASE_SEED="1000"
python run_all_benchmarks.py
python experiments/exp_ablations.py
python publication_gate.py
python -m pytest tests/ -v
```

See `SCIENTIFIC_VALIDATION.md` for the full validation workflow.

## Community and Governance

Included governance and collaboration files:
- `LICENSE`
- `NOTICE`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `CITATION.cff`
- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`

## Limitations

- This release does not claim physical-hardware validation.
- Reported gains are simulator findings under documented assumptions and tested regimes.

## Recommended Tag

- `v0.1.0`
