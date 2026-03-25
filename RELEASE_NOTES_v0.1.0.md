# Aethermor v0.1.0 Release Notes

## Release Scope

Aethermor v0.1.0 is an open-source Python toolkit for chip thermal analysis,
cooling tradeoffs, and compute-density limits. It helps engineers and
researchers answer: *What gate density can my substrate sustain? How much
cooling do I need? Where is my SoC's thermal bottleneck? When does adiabatic
logic beat CMOS?*

All models use SI-unit physics cross-validated against CODATA 2018, the CRC
Handbook, ITRS/IRDS roadmaps, and published specifications for four real
chip designs (NVIDIA A100, Apple M1, AMD EPYC 9654, Intel i9-13900K).

## Key Capabilities

### Physics Models (`physics/`)
- **Constants**: Boltzmann k_B, Planck h, Landauer limit (CODATA 2018 exact values)
- **Materials**: 9 substrate materials (Si, SiO₂, GaAs, Diamond, Graphene, Cu,
  InP, SiC, GaN) with extensible MaterialRegistry — register custom substrates
  with validation and JSON save/load
- **Energy Models**: 4 computing paradigms (CMOS, adiabatic, reversible,
  Landauer floor) with extensible ParadigmRegistry — register custom paradigms
  with EnergyModel protocol enforcement
- **Thermal Solver**: 3D Fourier heat diffusion, CFL-stable, 0.00% energy
  conservation error
- **Cooling Stacks**: Multi-layer thermal path model (11 built-in layers,
  6 factory configurations) with extensible CoolingRegistry
- **Chip Floorplan**: Heterogeneous SoC with per-block paradigm, density,
  activity, and tech node

### Inverse Design Tools (`analysis/`)
- `thermal_optimizer.py`: 8 tools — max density search, min cooling search,
  material ranking, cooling sweep, paradigm comparison, thermal headroom map,
  power redistribution optimizer, full design exploration
- `tech_roadmap.py`: 130 nm → 1.4 nm projections (energy, Landauer gap, crossover)
- `design_space.py`: Multi-dimensional sweeps with Pareto extraction
- `regime_map.py`: 5-regime classification
- `landauer_gap.py`: Distance-from-Landauer analysis
- `thermal_map.py`: Hotspot detection, cooling efficiency maps

### Interactive Explorer UI (`app.py`)
- 6 tabs: Material Ranking, Cooling Analysis, Paradigm Comparison,
  Technology Roadmap, SoC Thermal Map, Custom Material
- All parameters via sliders/dropdowns, all charts update live

### Research Examples (`examples/`)
- 7 ready-to-run scripts covering thermal wall analysis, paradigm crossover,
  substrate comparison, SoC hotspot analysis, technology roadmap, inverse
  design, and custom material/paradigm/cooling registration

## Verification

```bash
python -m pytest tests/ -v               # 254 tests, ~2 minutes
python -m validation.validate_all        # 133 physics cross-checks, ~13 seconds
python benchmarks/literature_validation.py    # 20 literature cross-checks
python benchmarks/real_world_validation.py    # 33 real-world chip validations
```

- **254 tests** across unit, integration, regression, and performance layers
- **133 physics cross-checks** against CODATA 2018, CRC Handbook 97th ed.,
  ITRS 2013, IRDS 2022, Incropera & DeWitt, Carslaw & Jaeger
- **20 literature cross-checks** against textbook solutions
- **33 real-world chip validation checks** against published specs for
  NVIDIA A100, Apple M1, AMD EPYC 9654, Intel i9-13900K
- **0.00% energy conservation error** in the 3D Fourier solver

See [VALIDATION.md](VALIDATION.md) for full methodology and reference sources.

## Install

```bash
git clone https://github.com/Yoder23/aethermor.git
cd aethermor
pip install -e ".[all]"     # core + UI + dev tools
python app.py               # launch interactive explorer
```

## Governance

- `LICENSE` (Apache 2.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- `CITATION.cff`, `CHANGELOG.md`, `NOTICE`
- `.github/workflows/ci.yml` (test + dependency audit)
- `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.md`

## Limitations

- All results are from physics-based models, not measured hardware.
- Energy models use published device parameters (ITRS/IRDS) but real chips
  have layout-dependent parasitics and manufacturing variation not captured here.
- See [LIMITATIONS.md](LIMITATIONS.md) for the full discussion.

## Recommended Tag

- `v0.1.0`
