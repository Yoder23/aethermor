# Accuracy Envelope

Defines the operating envelope where Aethermor's accuracy claims apply, the
sample set used to derive them, and explicit "outside this envelope" cases.

## Operating Envelope

The accuracy numbers below apply within this envelope:

| Parameter | Valid Range | Basis |
|-----------|-------------|-------|
| Power density | 0.1–200 W/cm² | Validated against 15 chips spanning 0.5–130 W/cm² |
| Die area | 10–900 mm² | Validated: 71 mm² (7950X) to 826 mm² (A100) |
| Die thickness | 50–800 µm | Validated: 100 µm (thinned) to 775 µm (i9-13900K) |
| h\_conv (effective) | 10–20,000 W/(m²·K) | Validated: natural air to direct liquid |
| Ambient temperature | 250–370 K | Physics validated at cryogenic (4 K) and 400 K; recommend 270–350 K for production use |
| Material conductivity | 1.4–5000 W/(m·K) | 9 materials validated: SiO₂ (1.4) to graphene (5000) |

## Accuracy by Output Type

### 1. Relative Ranking

| Metric | Envelope | Sample Size | Median Residual | Worst Case |
|--------|----------|-------------|-----------------|------------|
| Material ranking (by max density) | All 9 validated materials | 93 checks | 0% | 0% (ordering is physics-exact) |
| Cooling regime ranking | h = 10–20,000 W/(m²·K) | 6 factory configurations | 0% | 0% |
| Paradigm crossover (CMOS vs adiabatic) | 7 nm, f = 1 kHz–10 GHz | 16 checks | 0% | 0% (analytical comparison) |

**Basis**: Rankings depend only on material properties and energy model ratios,
which are validated to < 5% against published references. Ordering is invariant
to absolute accuracy.

### 2. Absolute Junction Temperature

| Metric | Envelope | Sample Size | Median Residual | Worst Case |
|--------|----------|-------------|-----------------|------------|
| T\_j (die-only 1D model) | 15 production chips, h = 50–20,000 | 33 checks | ±10% of ΔT | ±15% |
| T\_j (PackageStack + spreading) | 3 chips, Yovanovich spreading | 3 cases | +5 K | +9 K (i9-13900K) |
| T\_j vs published experiments | Kandlikar, Bar-Cohen | 4 checks | Within published range | Within 2× of published range |

**Sample set**: NVIDIA A100, Intel i9-13900K, AMD Ryzen 7950X, Apple M1,
AMD EPYC 9654, plus Kandlikar (2003) and Bar-Cohen & Wang (2009) published
experimental data.

**Median residual derivation**: Die-only 1D model: median
|T\_model − T\_measured| / ΔT across 15-chip plausibility checks = ~10%.
PackageStack model with Yovanovich spreading: A100 θ\_jc 0.98×, i9 T\_j +9 K,
M1 T\_j within published 60–75°C range (+5 K vs midpoint).

### 3. Cooling Requirement Estimation

| Metric | Envelope | Sample Size | Median Residual | Worst Case |
|--------|----------|-------------|-----------------|------------|
| Minimum h\_conv for T\_max target | All 9 materials, 6 cooling configs | 82 chip DB checks | ±15% | ±20% |
| Cooling regime classification | Natural air / forced / liquid / direct | 6 factory presets | Correct | Correct |

**Basis**: Cooling requirement is a 1D analytical inversion: given T\_max and
power, solve for h. Error is dominated by the same conduction + convection
model used for T\_j, plus any mismatch in published material properties (< 5%).

### 4. Package-Path Thermal Resistance (θ\_jc)

| Metric | Envelope | Sample Size | Median Residual | Worst Case |
|--------|----------|-------------|-----------------|------------|
| θ\_jc (PackageStack + Yovanovich) | A100 JEDEC-measured θ\_jc | 1 case | 0.98× | 0.98× |
| T\_j (PackageStack + Yovanovich) | i9-13900K, M1 | 2 cases | +5 K | +9 K |
| θ\_jc ordering | Multi-chip comparison | 3 cases | Correct | Correct |

**Derivation** (Yovanovich spreading resistance model):

| Chip | Measured | Model | Ratio/Residual |
|------|----------|-------|----------------|
| NVIDIA A100 | θ\_jc = 0.029 K/W | θ\_jc = 0.028 K/W | 0.98× |
| Intel i9-13900K | T\_j = 100°C (throttle) | T\_j = 109°C | +9 K |
| Apple M1 | T\_j = 60–75°C | T\_j = 73°C | +5 K (within range) |

Note: Intel publishes ψ\_jc = 0.43 K/W (JESD51-12 characteristic parameter,
includes board-side heat flow). Our model computes θ\_jc (JESD51-1,
case-only path) = 0.083 K/W. The ψ\_jc vs θ\_jc mismatch is expected;
we use T\_j as the primary comparison metric for the i9 case.

## Outside This Envelope

Results are **unreliable** when:

| Condition | Why | What Happens |
|-----------|-----|-------------|
| Power density > 200 W/cm² | Beyond validated range; hotspot physics dominate | T\_j may underpredict (no spreading resistance in 1D) |
| Die thickness > 1 mm | 3D lateral spreading dominates; 1D assumption breaks | θ\_jc underpredicted (see i9-13900K case) |
| Phase-change cooling | CoolingStack / PackageStack are single-phase | h\_eff approximation invalid |
| Transient operation | Steady-state model only | No time-dependent predictions |
| Sub-10 nm features | Fourier's law breaks down | Ballistic transport not modeled |
| Board-level thermal paths | Die-only model | PCB conduction, radiation ignored |
| Non-uniform TIM (voiding > 20%) | Uniform layer assumption | R\_TIM underestimated |

## Reproducibility

The numbers above can be reproduced with:

```bash
python benchmarks/hardware_correlation.py    # θ_jc correlation (3 cases)
python benchmarks/experimental_validation.py # published measurement checks (18)
python benchmarks/chip_thermal_database.py   # 15-chip plausibility (82 checks)
python benchmarks/material_cross_validation.py  # material accuracy (93 checks)
```
