# Aethermor Accuracy Statement

**Version**: 1.0.0
**Date**: 2026-03-26
**Status**: Analytically validated for architecture-stage thermal engineering

---

## Benchmark Corpus Summary

| Category | Cases | Chip Families | Materials | Paradigms | Cooling Stacks |
|----------|-------|---------------|-----------|-----------|----------------|
| Chip thermal database | 82 | 12 (A100, H100, MI300X, EPYC, Xeon, i9, Ryzen, M1, M2 Pro, Snapdragon, etc.) | 1 (Si) | 1 (CMOS) | 4 segments |
| Material cross-validation | 93 | — | 9 (Si, SiO₂, GaAs, Diamond, Graphene, Cu, InP, SiC, GaN) | — | — |
| Real-world chip validation | 33 | 4 (A100, M1, EPYC 9654, i9-13900K) | 1 | 1 | Air + liquid |
| Experimental measurement | 18 | 3 (A100, i9-13900K, Ryzen 7950X) | 1 | 1 | Package-level |
| Literature / analytical | 20 | — | — | — | — |
| Physics cross-checks | 133 | — | 9 | 4 | 6 factory configs |
| Unit + integration tests | 308 | — | 9 | 4 | 6 factory configs |
| Engineering case studies | 46 | — | 5 | 2 | 3 configs |

**Total: 700+ independently validated checks.** See [VERIFICATION_LAYERS.md](VERIFICATION_LAYERS.md).

---

## Error Metrics by Benchmark Family

### 1. Fundamental Constants

| Quantity | Reference Source | Model Value | Absolute Error |
|----------|----------------|-------------|----------------|
| Boltzmann constant k_B | CODATA 2018 | 1.380649 × 10⁻²³ J/K | 0.00% |
| Planck constant h | CODATA 2018 | 6.62607015 × 10⁻³⁴ J·s | 0.00% |
| Landauer limit (300 K) | k_B · T · ln 2 | 2.870979 × 10⁻²¹ J | 0.00% |

**These are exact-match values (CODATA 2018 definitions).**

### 2. Material Thermal Properties (8 materials vs CRC Handbook 97th ed.)

| Metric | Thermal Conductivity (k) | Specific Heat (c_p) | Density (ρ) | All Properties |
|--------|--------------------------|----------------------|-------------|----------------|
| Median error | 0.00% | 0.00% | 0.00% | 0.00% |
| P90 error | 0.00% | 1.69% | 0.05% | 0.05% |
| Worst case | 0.00% | 8.00% (SiC c_p) | 0.06% | 8.00% |
| Total checks | 8 | 8 | 8 | 24 |

**Worst case**: SiC specific heat (810 J/kg·K vs CRC 750 J/kg·K, 8.0% delta).
This is within the range of published values for α-SiC across different
polytypes and measurement conditions. All thermal conductivities are exact
matches to CRC reference values.

#### Per-Material Source Attribution

| Material | k Source | c_p Source | ρ Source | Notes |
|----------|---------|-----------|---------|-------|
| Silicon | CRC 97th ed. | CRC 97th ed. | CRC 97th ed. | Standard reference wafer |
| Silicon Dioxide | CRC 97th ed. | CRC 97th ed. | CRC 97th ed. | Amorphous (thermal oxide) |
| Gallium Arsenide | CRC 97th ed. | CRC 97th ed. | CRC 97th ed. | Semi-insulating bulk |
| Diamond | CRC 97th ed. | CRC 97th ed. | CRC 97th ed. | Type IIa single-crystal |
| Graphene | Balandin (2008) | Nika (2009) | Calculated | Effective monolayer on SiO₂ |
| Copper | CRC 97th ed. | CRC 97th ed. | CRC 97th ed. | OFHC grade |
| Indium Phosphide | CRC 97th ed. | Ioffe Institute | CRC 97th ed. | Semi-insulating |
| Silicon Carbide | CRC 97th ed. | CRC / Ioffe | CRC 97th ed. | α-SiC (6H polytype) |
| Gallium Nitride | CRC 97th ed. | Ioffe Institute | CRC 97th ed. | Wurtzite |

All values at 300 K. Properties are temperature-independent in the model;
see LIMITATIONS.md §9 for the impact above 400 K.

#### Accumulated Error: Thermal Diffusivity

Thermal diffusivity α = k / (ρ · c_p) compounds errors from three properties.
Worst-case accumulated error (SiC): k=0%, c_p=8%, ρ=0.06% → α ≈ 8% error.
For all other materials, accumulated α error is < 2%.

### 3. JEDEC θ_jc / T_j Thermal Resistance (Model vs Published Measurement)

With Yovanovich (1983) spreading resistance enabled, `PackageStack` models
the full die → TIM → IHS → spreading → convection path:

| Chip | Metric | Measured | Model | Residual |
|------|--------|----------|-------|----------|
| NVIDIA A100 | θ_jc | 0.029 K/W | 0.028 K/W | 0.98× (±2%) |
| Intel i9-13900K | T_j | 373 K (100°C) | 382 K (109°C) | +9.1 K |
| Apple M1 (MBA) | T_j | 333–348 K (60–75°C) | 346 K (72.7°C) | +5.3 K (within range) |

**Note on Intel ψ_jc vs θ_jc**: Intel publishes ψ_jc (JESD51-12, includes
PCB heat path), not θ_jc (JESD51-1, case-only). For desktop CPUs, ψ_jc is
typically 3–5× higher than θ_jc. T_j is the appropriate comparison metric.

**Summary**: A100 θ_jc within ±2%. Junction temperatures within ±10 K
across all segments. This is useful accuracy for architecture-stage thermal
analysis. See docs/HARDWARE_CORRELATION.md for full case details.

### 4. Real-World Chip Thermal Predictions

All 33 checks pass: junction temperatures, cooling requirements, density
limits, and analytical correlations are physically consistent across
4 chip designs (NVIDIA A100, Apple M1, AMD EPYC 9654, Intel i9-13900K).

### 5. Analytical Solutions (Exact)

| Solution | Method | Error |
|----------|--------|-------|
| Plane wall conduction | Fourier's law: Q = kAΔT/L | 0.00% |
| Thermal resistance | R = L/(kA) | 0.00% |
| Incropera plane wall | Carslaw & Jaeger | 0.00% |
| Biot number lumped capacitance | Bi = hL/k | 0.00% |
| Fin efficiency (COMSOL-verified) | Analytical η | 0.00% |

### 6. 3D Fourier Solver

| Metric | Value |
|--------|-------|
| Energy conservation error | 0.00% |
| CFL stability | Auto-enforced (α·dt/dx² < 1/6) |
| Boundary conditions | Convective, fixed, adiabatic |

---

## Supported Operating Envelope

### Where These Numbers Apply

| Parameter | Valid Range | Notes |
|-----------|------------|-------|
| Thermal regime | Steady-state | Primary use case |
| Quasi-static | Slow transients only | Step-change analysis acceptable |
| Power density | 10⁴ – 10⁸ W/m² | Typical chip range; tested across all paradigms |
| Cooling coefficient | 10 – 50,000 W/(m²·K) | Natural air through microchannel |
| Temperature range | 250 – 700 K | Below material max operating temps |
| Technology nodes | 1.4 nm – 130 nm | Validated in roadmap projections |
| Substrates | Si, SiO₂, GaAs, Diamond, Graphene, Cu, InP, SiC, GaN | Extensible to custom materials |
| Paradigms | CMOS, adiabatic, reversible, Landauer floor | Extensible to custom paradigms |
| Chip abstraction | Gate-level energy × density × activity × frequency | Not circuit-level or transistor-level |

### Where Aethermor Is Safe to Use

- Architecture-stage thermal exploration and design-space sweeps
- Substrate / material comparison under identical constraints
- Cooling strategy screening (air → liquid → microchannel)
- Compute-density limit estimation for given thermal budgets
- Paradigm crossover analysis (CMOS vs adiabatic)
- Hotspot and headroom ranking on heterogeneous SoCs
- Technology roadmap projections (energy, gap, thermal wall)

### Where Results Should Be Used with Caution

- Absolute junction temperature predictions (model captures physics;
  `CoolingStack` uses 1D layers without contact resistances; use `PackageStack`
  for explicit die/TIM/IHS contact resistance modeling)
- Vendor-specific cooling-stack edge cases (use measured layer data)
- Chips with highly non-uniform power maps (use floorplan model)

### Where Aethermor Is Not Intended

- Sign-off thermal closure
- Layout-level or transistor-level thermal verification
- Transient package verification (power gating, workload transitions)
- Process-specific reliability prediction
- Replacing COMSOL/ANSYS for detailed-design FEM

---

## How to Reproduce These Numbers

```bash
# Full validation suite (700+ checks, ~3 minutes)
python run_all_validations.py

# Individual benchmark families
python benchmarks/chip_thermal_database.py        # 82 checks
python benchmarks/material_cross_validation.py    # 93 checks
python benchmarks/real_world_validation.py        # 33 checks
python benchmarks/experimental_validation.py      # 18 checks
python benchmarks/literature_validation.py        # 20 checks
python -m aethermor.validation.validate_all                 # 133 checks

# Accuracy metrics script
python scripts/gather_accuracy_metrics.py
```

---

## Summary

A reader can answer from this page:

1. **What was benchmarked**: 700+ checks across 12 production chips, 9 materials,
   4 paradigms, JEDEC measurements, IR thermal imaging, HotSpot benchmarks,
   textbook analytical solutions, and CODATA fundamental constants.

2. **How wrong the tool is**: Material properties median 0.00% error (max 8.0%
   on SiC c_p). Constants 0.00%. Analytical solutions 0.00%. θ_jc model
   captures conductive path with Yovanovich spreading (A100 0.98×, T_j ±10 K).
   Energy conservation 0.00%.

3. **Where it is safe to use**: Architecture-stage thermal exploration,
   material comparison, cooling tradeoffs, density limits, paradigm crossover,
   headroom analysis, technology roadmaps.

4. **Where it is not**: Sign-off, layout closure, transient package verification,
   transistor-level reliability.
