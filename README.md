# Aethermor

**Inverse thermal design tools for thermodynamic computing research.**

Aethermor is the first open-source toolkit that answers inverse thermal design
questions: *"What gate density can this substrate sustain?"*, *"What cooling
do I need?"*, *"Which material wins at this node?"*, *"Where is the thermal
bottleneck in my SoC?"* — questions that currently require weeks of manual
sweeps in commercial FEM tools or custom scripts.

Every model uses published physics in SI units — Joules, Kelvin, Watts, metres —
cross-validated against CODATA 2018, the CRC Handbook, and ITRS/IRDS roadmaps.

## Verify the Physics Yourself

```bash
python -m validation.validate_all     # 133 checks, ~13 seconds
```

Every physics model is cross-checked against published reference data, analytical
solutions, conservation laws, and internal self-consistency. See
[VALIDATION.md](VALIDATION.md) for methodology and reference citations.

---

## What You Can Do

### Solve Inverse Design Problems

```python
from analysis.thermal_optimizer import ThermalOptimizer

opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

# What's the max density each material can sustain?
ranking = opt.material_ranking(h_conv=1000.0)
for r in ranking:
    print(f"{r['material_name']:<25s}  {r['max_density']:.2e} gates/elem")

# What cooling do I need for 1e5 gates/element on silicon?
req = opt.find_min_cooling("silicon", gate_density=1e5)
print(f"Min h_conv: {req['min_h_conv']:.0f} W/(m²·K)  →  {req['cooling_category']}")

# Where are the thermal bottlenecks in a heterogeneous SoC?
from physics.chip_floorplan import ChipFloorplan
soc = ChipFloorplan.modern_soc()
headroom = opt.thermal_headroom_map(soc, h_conv=1000.0)
for block in headroom:
    print(f"{block['name']:<20s}  T={block['T_max_K']:.0f} K  headroom={block['density_headroom_factor']:.1f}×")

# Optimally redistribute power across functional blocks
result = opt.optimize_power_distribution(soc, power_budget_W=50.0)
print(f"Improvement: {result['improvement_ratio']:.1f}×  ({result['binding_constraint']})")
```

### Compare Computing Paradigms

```python
from physical_simulation import PhysicalSimulation

sim = PhysicalSimulation(tech_node_nm=7, frequency_Hz=1e9)
results = sim.compare_paradigms()
for paradigm, s in results.items():
    print(f"{paradigm:<20}  {s['energy_per_gate_switch_J']:.2e} J/gate  gap={s['landauer_gap']:.0f}×")
```

### Map Where Adiabatic Logic Wins

```python
from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy

cmos = CMOSGateEnergy(tech_node_nm=7)
adiabatic = AdiabaticGateEnergy(tech_node_nm=7)
f_cross = adiabatic.crossover_frequency(cmos)
print(f"Adiabatic beats CMOS below {f_cross:.2e} Hz")
```

### Project the Technology Roadmap

```python
from analysis.tech_roadmap import TechnologyRoadmap

roadmap = TechnologyRoadmap()   # 130 nm → 1.4 nm
print(roadmap.full_report())    # Energy, Landauer gap, paradigm crossover, thermal wall
```

### Build a Realistic Cooling Stack

```python
from physics.cooling import CoolingStack, THERMAL_LAYERS

stack = CoolingStack.server_liquid()          # pre-built server config
h_eff = stack.effective_h(die_area_m2=100e-6) # effective h for the thermal solver
print(f"Effective h = {h_eff:.0f} W/(m²·K)")
print(f"Max power   = {stack.max_power_W(100e-6):.1f} W")
```

---

## Quick Start

```bash
pip install -e .                    # core: numpy, pandas, scipy, matplotlib
pip install -e ".[dev]"             # + pytest, coverage, flake8
```

### Run Tests

```bash
python -m pytest tests/ -v          # 212 tests, ~2 minutes
```

### Run Research Examples

```bash
python examples/optimal_density.py       # Find thermal wall per substrate
python examples/adiabatic_crossover.py   # Map paradigm crossover points
python examples/material_comparison.py   # Compare substrate materials
python examples/heterogeneous_soc.py     # Simulate a heterogeneous SoC
python examples/technology_roadmap.py    # Project paradigm viability across nodes
python examples/thermal_optimizer.py     # Inverse design: headroom map, power redistribution
```

---

## Physics Foundation

### `physics/` — SI-Unit Models

| Module | What It Provides |
|--------|-----------------|
| `constants.py` | Boltzmann k_B, Planck h, Landauer limit — all CODATA 2018 |
| `materials.py` | 9 substrates (Si, SiO₂, GaAs, diamond, graphene, Cu, InP, SiC, GaN) — CRC Handbook values |
| `energy_models.py` | 4 paradigms: CMOS (ITRS-calibrated), adiabatic, reversible, Landauer floor |
| `thermal.py` | 3D Fourier heat diffusion, CFL-stable, 0.00% energy conservation error |
| `cooling.py` | Multi-layer cooling stack (TIM → IHS → heatsink → ambient), 12 pre-built layers, 6 factory configs |
| `chip_floorplan.py` | Heterogeneous SoC model — CPU/GPU/cache/IO blocks with per-block paradigms |

### `analysis/` — Inverse Design & Research Tools

| Module | Capability |
|--------|-----------|
| `thermal_optimizer.py` | **8 inverse design tools**: max density, min cooling, material ranking, paradigm comparison, cooling sweep, thermal headroom map, power redistribution optimizer, full design exploration |
| `tech_roadmap.py` | Node projections (130 nm → 1.4 nm): energy scaling, Landauer gap closure, paradigm crossover, thermal wall |
| `design_space.py` | Multi-dimensional sweeps with Pareto extraction |
| `regime_map.py` | 5-regime classification (deep_classical → near_limit) |
| `landauer_gap.py` | Distance-from-Landauer-limit analysis |
| `thermal_map.py` | Hotspot detection, cooling efficiency maps |

---

## Project Structure

```
physics/              # SI-unit thermodynamic models
analysis/             # Inverse design & research analysis tools
validation/           # 133 physics cross-checks (python -m validation.validate_all)
examples/             # 6 ready-to-run research scripts
tests/                # 212 unit, integration, regression tests

physical_simulation.py  # High-level simulation interface
thermodynamic_core.py   # Landauer bookkeeping engine
benchmark_*.py          # Mechanism benchmarks (legacy lattice simulation)
experiments/            # Ablation and robustness experiments
archive/                # Legacy code and documentation
```

## Trust & Validation

| Layer | What | Count |
|-------|------|-------|
| Unit tests | pytest suite | 212 pass, 0 fail |
| Physics validation | Cross-checks vs CODATA, CRC, ITRS/IRDS, analytical solutions | 133 pass, 0 fail |
| Energy conservation | Fourier solver energy balance | 0.00% error |
| Reproducibility | Seeded, deterministic, manifested | Verified |
| Examples | All 6 research scripts | All clean |

See [VALIDATION.md](VALIDATION.md) for the full methodology and reference sources.

## Scope and Limitations

Aethermor operates at the **thermal and energy level** — not at the transistor or
circuit level. It uses published material properties and standard physics (Fourier's
law, CMOS voltage scaling, Landauer's principle) but has not been validated against
fabricated hardware.

See [LIMITATIONS.md](LIMITATIONS.md) for the full discussion of scope,
model simplifications, and the path to hardware validation.

## Documentation

| Document | Purpose |
|----------|---------|
| [VALIDATION.md](VALIDATION.md) | Physics validation methodology & references |
| [LIMITATIONS.md](LIMITATIONS.md) | Scope, known limitations, future work |
| [HONEST_REVIEW.md](HONEST_REVIEW.md) | Self-audit with grades and competitive comparison |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [RELEASE_NOTES_v0.1.0.md](RELEASE_NOTES_v0.1.0.md) | v0.1.0 release details |

## Contributing

Contributions that extend the physics — new materials, new energy models,
anisotropic transport, interconnect power — are especially welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
