# Release Benchmark Report — v1.0.0

**Date**: 2026-03-26
**Release**: v1.0.0 (Production/Stable)

---

## Summary

| Metric | Result |
|--------|--------|
| Production benchmark cases | 20/20 pass |
| Operating envelope (250–700 K) | 20/20 within envelope |
| Material cross-validation | Median 0.00%, max 0.00% error |
| Gold output regression | No regressions (baseline release) |
| Full validation suite | 12/12 suites, 680+ checks, all pass |
| Release gates | ALL PASS |

## Thermal Model

Each case uses a 1D conduction + convection model:

- **R_cond** = t_die / (k_Si × A_die) — conduction through silicon die
- **R_conv** = 1 / (h_conv × A_package) — convection at package/IHS surface
- **Tj** = T_ambient + TDP × (R_cond + R_conv)

Die thickness: 200 μm for nodes ≤ 7 nm, 775 μm for older nodes.
Convection uses the package/IHS area (not die area), reflecting heat
spreading through the integrated heat spreader. h_conv values are
per-chip estimates based on cooling type and published specifications.

Chiplet designs (EPYC 9654, EPYC 7763) are modeled per-CCD with the
full IHS area, matching the approach in `real_world_validation.py`.

## Accuracy vs Previous Release

This is the initial production release (v1.0.0). No previous release to
compare against.

## Benchmark Details

### Production Suite (20 cases)

All junction temperatures are within the declared operating envelope
(250–700 K / −23–427 °C).

| Chip | Segment | Tj (°C) | Power Density (W/m²) | Status |
|------|---------|---------|---------------------|--------|
| NVIDIA A100 | accelerator | 43.5 | 484,262 | PASS |
| NVIDIA H100 | accelerator | 56.0 | 859,951 | PASS |
| AMD MI300X | accelerator | 54.1 | 1,000,000 | PASS |
| AMD EPYC 9654 (1 CCD) | server | 41.2 | 416,667 | PASS |
| Intel Xeon w9-3495X | server | 92.8 | 875,000 | PASS |
| Intel i9-13900K | desktop | 93.7 | 984,436 | PASS |
| AMD Ryzen 9 7950X | desktop | 86.8 | 2,394,366 | PASS |
| Apple M1 | mobile | 52.1 | 166,667 | PASS |
| Apple M2 Pro | mobile | 57.0 | 131,579 | PASS |
| Snapdragon 8 Gen 2 | mobile | 127.0 | 97,561 | PASS |
| AMD Ryzen 7 5800X | desktop | 63.6 | 1,296,296 | PASS |
| Intel Xeon Platinum 8380 | server | 95.7 | 409,091 | PASS |
| Apple M1 Ultra | mobile | 60.4 | 142,857 | PASS |
| NVIDIA RTX 4090 | accelerator | 77.8 | 738,916 | PASS |
| AMD EPYC 7763 (1 CCD) | server | 43.5 | 432,099 | PASS |
| Heterogeneous SoC | soc | 77.5 | 500,000 | PASS |
| Adiabatic crossover | paradigm | 52.2 | 250,000 | PASS |
| Cooling tradeoff | cooling | 38.2 | 1,000,000 | PASS |
| Diamond spreader | material | 49.6 | 2,000,000 | PASS |
| SiC vs Si | material | 178.9 | 1,500,000 | PASS |

### Interpretation Notes

- **Liquid-cooled accelerators** (A100, H100, MI300X) show low Tj because
  high h_conv (5000 W/m²·K) on large package areas provides excellent heat
  removal. These results are consistent with published operating temperatures.
- **All 15 real chips** predict Tj below their published Tj_max. Per-chip
  h_conv values reflect the actual cooling solution each chip ships with
  (fanless, air tower, server heatsink, AIO liquid, etc.).
- **Chiplet designs** (EPYC 9654, EPYC 7763) are modeled as single CCDs
  sharing the full IHS, which gives realistic per-chiplet thermal behavior.
- **Synthetic stress cases** (SiC vs Si at 178.9°C) intentionally probe
  high-thermal-stress regimes to validate material-selection workflows.
  All remain within the 250–700 K operating envelope.

### Full Validation Suite (12 suites)

| Suite | Result | Time |
|-------|--------|------|
| Unit tests (pytest) | 278 pass | ~145s |
| Physics validation | 133 pass | ~11s |
| Literature validation | 20 pass | ~1s |
| Real-world chip validation | 33 pass | ~38s |
| Experimental validation | 18 pass | ~1s |
| Chip thermal database | 82 pass | ~1s |
| Material cross-validation | 93 pass | ~0.3s |
| Case study: datacenter | 13 pass | ~0.3s |
| Case study: mobile SoC | 10 pass | ~0.3s |
| Case study: cooling decision | pass | ~11s |
| Case study: substrate selection | pass | ~8s |
| Case study: SoC bottleneck | pass | ~3s |

## Release Gate Verdict

| Gate | Result |
|------|--------|
| All cases valid | PASS |
| All within operating envelope (250–700 K) | PASS |
| Material median error ≤ 1% | PASS (0.00%) |
| Material max error ≤ 10% | PASS (0.00%) |
| No gold output regressions | PASS |

**ALL GATES PASS.**
