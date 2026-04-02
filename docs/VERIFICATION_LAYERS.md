# Verification Layers

This table defines exactly what Aethermor validates and how the headline
numbers (308 tests, 133 physics checks, 700+ total) are computed.

## Verification Layer Table

| Layer | What It Covers | Count | Runner |
|-------|---------------|-------|--------|
| **Unit / integration / regression tests** | Every public class and method: `ThermalOptimizer`, `CoolingStack`, `PackageStack`, `ChipFloorplan`, `Material`, energy models, registries, CLI, dashboard imports. Edge cases, ordering checks, serialization round-trips, robustness/fuzz tests. | **308** | `python -m pytest tests/ -v` |
| **Physics cross-checks** | Fundamental constants vs CODATA 2018. Landauer limit at multiple temperatures. Material properties vs CRC Handbook. CMOS voltage/energy scaling vs ITRS/IRDS. 3D Fourier solver energy conservation. Analytical 1D model limit cases. | **133** | `python -m aethermor.validation.validate_all` |
| **Material cross-validation** | 9 substrate materials × 10+ properties each, cross-validated against CRC Handbook, ASM International, NIST, Ioffe Institute, and manufacturer datasheets. | **93** | `python benchmarks/material_cross_validation.py` |
| **Chip thermal database** | 12 production chips (A100, H100, MI300X, EPYC, Xeon, i9, Ryzen, M1, M2 Pro, Snapdragon, etc.) — power density, junction temperature, cooling capacity, conduction floor, material ranking. | **82** | `python benchmarks/chip_thermal_database.py` |
| **Real-world chip validation** | 4 published chip designs (A100, M1, EPYC 9654, i9-13900K) — 33 checks against manufacturer specifications. | **33** | `python benchmarks/real_world_validation.py` |
| **Literature cross-checks** | 20 checks against CODATA, CRC Handbook, ITRS/IRDS, Incropera & DeWitt textbook solutions. | **20** | `python benchmarks/literature_validation.py` |
| **Experimental measurements** | 18 checks vs JEDEC θ\_jc (A100, i9-13900K, 7950X), IR thermal imaging (Kandlikar, Bar-Cohen), HotSpot ev6, Incropera analytical. | **18** | `python benchmarks/experimental_validation.py` |
| **Hardware correlation** | 3 PackageStack cases (server, desktop, mobile) vs measured θ\_jc/T\_j with full geometry and gap analysis. | **3** | `python benchmarks/hardware_correlation.py` |
| **Engineering case studies** | Datacenter cooling strategy (13), mobile SoC thermal envelope (10), substrate selection (4+) — decision-driven checks. | **46+** | Individual benchmark scripts |
| **Uncertainty propagation** | Monte Carlo uncertainty on T\_j with one-at-a-time sensitivity for 9 input parameters. | **1 suite** | `python benchmarks/uncertainty_propagation.py` |

## How the Totals Are Computed

| Headline Number | Computation |
|----------------|-------------|
| **308 tests** | `pytest tests/` — unit + integration + regression + robustness tests |
| **133 physics checks** | `aethermor validate` — the built-in validation suite |
| **700+ total checks** | 308 + 133 + 93 + 82 + 33 + 20 + 18 + 3 + 46+ = **736+** checks across all layers |

The "700+" number is a conservative floor. The actual count is 736+ and grows
as new case studies are added.

## How to Run Everything

```bash
python run_all_validations.py    # master runner: all 12+ suites, ~3 min
```

Or individual layers:

```bash
python -m pytest tests/ -v                          # Layer 1: unit tests
python -m aethermor.validation.validate_all          # Layer 2: physics checks
python benchmarks/material_cross_validation.py       # Layer 3: materials
python benchmarks/chip_thermal_database.py           # Layer 4: chip database
python benchmarks/hardware_correlation.py            # Layer 5: hardware corr.
python benchmarks/uncertainty_propagation.py         # Layer 6: uncertainty
```

## Where These Numbers Appear

This table is the single source of truth. The following files reference it:

- [README.md](../README.md) — Verification section
- [VALIDATION.md](../VALIDATION.md) — Methodology
- [CONTRIBUTING.md](../CONTRIBUTING.md) — What to run before submitting
- CLI: `aethermor validate` runs the 133-check physics suite
