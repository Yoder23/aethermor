# Aethermor

**Thermal design tools for thermodynamic computing — explore hardware
trade-offs interactively or programmatically.**

Aethermor helps hardware engineers answer questions like:
- *"What gate density can my substrate sustain before thermal runaway?"*
- *"How much cooling do I actually need?"*
- *"Where is the thermal bottleneck in my SoC?"*
- *"When does adiabatic logic beat CMOS?"*

All models use real physics in SI units, cross-validated against CODATA 2018,
the CRC Handbook, and ITRS/IRDS roadmaps.

---

## 1. Install

```bash
git clone https://github.com/YOUR_ORG/aethermor.git
cd aethermor
pip install -e ".[dashboard]"      # installs core + interactive UI
```

> **Core only** (no UI): `pip install -e .`
> **Everything** (dev + UI): `pip install -e ".[all]"`

## 2. Launch the Explorer UI

```bash
python app.py
```

Open **http://127.0.0.1:8050** in your browser. You get five interactive tabs:

| Tab | What You Can Do |
|-----|-----------------|
| **Material Ranking** | Pick a tech node, frequency, and cooling — see which substrate lets you pack the most compute |
| **Cooling Analysis** | Set a material and gate density — see temperature vs. cooling with the conduction floor |
| **Paradigm Comparison** | Drag the frequency slider to watch the CMOS ↔ adiabatic crossover shift in real time |
| **Technology Roadmap** | Energy per gate and Landauer gap from 130 nm down to 1.4 nm |
| **SoC Thermal Map** | Thermal headroom per block on a heterogeneous CPU+GPU+cache+IO chip — find the bottleneck |

Every parameter is a slider or dropdown. Every chart updates live.

---

## 3. Use the Python API

If you prefer scripting, every capability in the UI is also available as a
Python function.

### Which material gives me the most compute density?

```python
from analysis.thermal_optimizer import ThermalOptimizer

opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=1e9)

ranking = opt.material_ranking(h_conv=1000.0)
for r in ranking:
    print(f"{r['material_name']:<25s}  {r['max_density']:.2e} gates/elem")
```

### How much cooling do I need?

```python
req = opt.find_min_cooling("silicon", gate_density=1e5)
print(f"Min h_conv: {req['min_h_conv']:.0f} W/(m²·K)  →  {req['cooling_category']}")
```

### Where is my SoC's thermal bottleneck?

```python
from physics.chip_floorplan import ChipFloorplan

soc = ChipFloorplan.modern_soc()
headroom = opt.thermal_headroom_map(soc, h_conv=1000.0)
for block in headroom:
    print(f"{block['name']:<20s}  T={block['T_max_K']:.0f} K  headroom={block['density_headroom_factor']:.1f}×")
```

### When does adiabatic logic beat CMOS?

```python
from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy

cmos = CMOSGateEnergy(tech_node_nm=7)
adiabatic = AdiabaticGateEnergy(tech_node_nm=7)
f_cross = adiabatic.crossover_frequency(cmos)
print(f"Adiabatic beats CMOS below {f_cross:.2e} Hz")
```

### How does scaling change things from 130 nm to 1.4 nm?

```python
from analysis.tech_roadmap import TechnologyRoadmap

roadmap = TechnologyRoadmap()
print(roadmap.full_report())
```

### Build a realistic cooling stack

```python
from physics.cooling import CoolingStack

stack = CoolingStack.server_liquid()
h_eff = stack.effective_h(die_area_m2=100e-6)
print(f"Effective h = {h_eff:.0f} W/(m²·K)")
print(f"Max power   = {stack.max_power_W(100e-6):.1f} W")
```

---

## 4. Run the Examples

Six ready-to-run scripts that each answer a specific research question:

```bash
python examples/optimal_density.py       # Thermal wall per substrate
python examples/adiabatic_crossover.py   # Paradigm crossover points
python examples/material_comparison.py   # Substrate comparison
python examples/heterogeneous_soc.py     # SoC hotspot analysis
python examples/technology_roadmap.py    # 130 nm → 1.4 nm projections
python examples/thermal_optimizer.py     # Inverse design: headroom + power redistribution
```

## 5. Run the Tests

```bash
python -m pytest tests/ -v              # 212 tests, ~2 minutes
python -m validation.validate_all       # 133 physics cross-checks, ~13 seconds
```

---

## What's Inside

### `physics/` — SI-Unit Thermodynamic Models

| Module | What It Does |
|--------|-------------|
| `constants.py` | Boltzmann k_B, Planck h, Landauer limit (CODATA 2018) |
| `materials.py` | 9 substrates: Si, SiO₂, GaAs, diamond, graphene, Cu, InP, SiC, GaN |
| `energy_models.py` | 4 paradigms: CMOS (ITRS-calibrated), adiabatic, reversible, Landauer floor |
| `thermal.py` | 3D Fourier heat diffusion with CFL-stable timestep, 0.00% energy conservation error |
| `cooling.py` | Multi-layer cooling stacks (TIM → IHS → heatsink → ambient), 6 presets |
| `chip_floorplan.py` | Heterogeneous SoC: CPU/GPU/cache/IO blocks with per-block paradigms |

### `analysis/` — Inverse Design & Research Tools

| Module | What It Does |
|--------|-------------|
| `thermal_optimizer.py` | 8 inverse design tools: max density, min cooling, material ranking, headroom map, power redistribution |
| `tech_roadmap.py` | Node projections (130 nm → 1.4 nm): energy, Landauer gap, paradigm crossover |
| `design_space.py` | Multi-dimensional parameter sweeps with Pareto extraction |
| `regime_map.py` | 5-regime classification: deep_classical → near_limit |
| `landauer_gap.py` | Distance-from-Landauer analysis |
| `thermal_map.py` | Hotspot detection, cooling efficiency maps |

### Project Layout

```
app.py                # Interactive Explorer UI — run this
physics/              # SI-unit thermodynamic models
analysis/             # Inverse design & research tools
validation/           # 133 physics cross-checks
examples/             # 6 ready-to-run research scripts
tests/                # 212 unit, integration, regression tests
```

---

## Trust & Validation

| Check | Result |
|-------|--------|
| Unit tests | 212 pass, 0 fail |
| Physics validation | 133 cross-checks vs CODATA, CRC, ITRS/IRDS | 
| Energy conservation | 0.00% error in Fourier solver |
| Reproducibility | Seeded, deterministic |
| Examples | 6/6 run clean |

See [VALIDATION.md](VALIDATION.md) for methodology and reference sources.

## Scope and Limitations

Aethermor operates at the **thermal and energy level** — not transistor or
circuit level. Models use published material properties and standard physics
(Fourier's law, CMOS scaling, Landauer's principle) but have not been validated
against fabricated hardware.

See [LIMITATIONS.md](LIMITATIONS.md) for the full discussion.

## Documentation

| Document | What It Covers |
|----------|---------------|
| [VALIDATION.md](VALIDATION.md) | Physics validation methodology & references |
| [LIMITATIONS.md](LIMITATIONS.md) | Scope, simplifications, path to hardware validation |
| [HONEST_REVIEW.md](HONEST_REVIEW.md) | Self-audit with grades and competitive comparison |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Contributing

Contributions that extend the physics — new materials, new energy models,
anisotropic transport, interconnect power — are especially welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
