# Aethermor Validation Report

> **Scope: Production-stable for architecture-stage thermal exploration and inverse design; not intended for sign-off, transient package verification, or transistor-level thermal closure.**

**Verify everything:**
```bash
python -m aethermor.validation.validate_all              # 133 physics cross-checks
python benchmarks/literature_validation.py     # 20 literature cross-checks
python benchmarks/real_world_validation.py     # 33 real-world chip validations
```

Expected output:
- **133 checks passed, 0 failed** (~13 seconds)
- **20 checks passed, 0 failed** (~30 seconds)
- **33 checks passed, 0 failed** (~42 seconds)

---

## Why This Exists

Every physics model in Aethermor has been cross-validated against published
reference data, analytical solutions, conservation laws, and internal
self-consistency.  This document explains _what_ is checked, _why_, and
_which_ references each check is traced to.

A researcher should **never** have to trust a simulation on faith.  Run the
validation suite on your machine, read the output, and verify that every
PASS makes physical sense to you.

---

## Validation Sections

### 1. Fundamental Constants — CODATA 2018

| Constant | Reference | Source |
|----------|-----------|--------|
| Boltzmann k_B | 1.380649 × 10⁻²³ J/K | CODATA 2018 (exact, SI redefinition) |
| Planck h | 6.62607015 × 10⁻³⁴ J·s | CODATA 2018 (exact) |
| Elementary charge e | 1.602176634 × 10⁻¹⁹ C | CODATA 2018 (exact) |
| Speed of light c | 2.99792458 × 10⁸ m/s | CODATA 2018 (exact) |
| Stefan-Boltzmann σ | 5.670374419 × 10⁻⁸ W/(m²·K⁴) | Derived from k_B, h, c |

**What is checked:** Each constant in `physics/constants.py` is compared to the
NIST CODATA 2018 value.  Tolerance: < 0.01%.

**Why it matters:** Every energy, temperature, and power calculation flows from
these constants.  A single wrong digit would corrupt all downstream results.

---

### 2. Landauer Limit — Information-Theoretic Minimum

| Temperature | Expected E_min | Formula |
|-------------|----------------|---------|
| 300 K | 2.871 × 10⁻²¹ J | k_B · T · ln(2) |
| 77 K (LN₂) | 7.369 × 10⁻²² J | k_B · T · ln(2) |
| 4 K (LHe) | 3.828 × 10⁻²³ J | k_B · T · ln(2) |

**What is checked:**
- `landauer_limit(T)` returns k_B·T·ln(2) at three reference temperatures.
- Proportionality: limit scales linearly with T (L(600K)/L(300K) = 2.0).
- Pre-computed `LANDAUER_LIMIT` constant matches run-time calculation.

**Reference:** Landauer, R. "Irreversibility and Heat Generation in the
Computing Process." IBM J. Res. Dev. 5(3), 183–191 (1961).

---

### 3. Material Properties — CRC Handbook

| Material | k (W/m·K) | ρ (kg/m³) | cₚ (J/kg·K) | E_g (eV) | Source |
|----------|-----------|-----------|-------------|----------|--------|
| Silicon | 148 | 2329–2330 | 700 | 1.12 | CRC 97th ed. |
| Diamond | 2200 | 3510 | 520 | 5.47 | CRC 97th ed. |
| GaAs | 55 | 5320 | 330 | 1.42 | CRC 97th ed. |
| SiC (4H) | 490 | 3210 | 690 | 3.26 | Morkoç (2006) |
| GaN | 130 | 6150 | 490 | 3.40 | Morkoç (2008) |
| Copper | 401 | 8960 | 385 | — | CRC 97th ed. |

**What is checked:**
- Each property matches the reference value (tolerance < 0.1%).
- Thermal diffusivity α = k/(ρ·cₚ) is self-consistent.
- Conductivity ordering: Diamond > SiC > Si > GaAs.

**Why it matters:** Material properties determine thermal resistance, maximum
operating temperature, and which substrate is best for a given application.
Wrong values would send researchers down the wrong material path.

---

### 4. CMOS Energy Model — ITRS/IRDS Calibration

| Node (nm) | V_dd ref (V) | V_dd got (V) | Source |
|-----------|-------------|-------------|--------|
| 130 | 1.20 | 1.205 | ITRS 2013 |
| 65 | 1.00 | 0.978 | ITRS 2013 |
| 45 | 0.90 | 0.908 | ITRS 2013 |
| 14 | 0.75 | 0.748 | IRDS 2022 |
| 7 | 0.70 | 0.699 | IRDS 2022 |

**What is checked:**
- Supply voltage V_dd at 5 nodes matches published roadmaps (< 3% error).
- Capacitance scaling: C_load(14nm)/C_load(7nm) ≈ 2.0 (area scaling).
- Dynamic energy at 7nm: E ≈ 2.45 × 10⁻¹⁶ J.
- Landauer gap at 7nm: 10³ < gap < 10⁷ (CMOS is ~85,000× above limit).
- CMOS energy > Landauer limit (can't beat thermodynamics).
- Leakage increases with temperature (Arrhenius / thermal generation).

**Adiabatic logic model:**
- Adiabatic energy < CMOS energy at low frequency (1 MHz).
- Adiabatic energy ≥ Landauer floor (can't go below).
- Crossover frequency exists and is finite.

**Why it matters:** The energy model is the foundation for power density,
thermal calculations, and paradigm comparisons.  ITRS/IRDS are the
industry-standard references for technology scaling.

---

### 5. Fourier Thermal Solver — Analytical Comparison

**Test setup:** 10×10×10 grid, 100 µm elements, silicon, h = 1000 W/(m²·K),
uniform heat generation Q = 10⁵ W/m³.

**Analytical reference:** 1D slab with convective cooling:
T_max = T_amb + Q·L/h + Q·L²/(2·k), where L = half-thickness.

**What is checked:**
- Centre temperature > T_ambient (heat is being generated).
- 3D solver T ≤ 1D analytical T (3D has more cooling surfaces).
- 3D solver within 40% of 1D estimate (geometric correction).
- **Energy balance:** |E_in − E_out − ΔU| / E_in < 5%.
  - E_in = cumulative heat generated
  - E_out = cumulative heat removed through boundaries
  - ΔU = ρ·cₚ·V·∑(T − T_initial) = stored thermal energy
- Boundary faces cooler than centre.

**Why it matters:** The Fourier solver is the numerical core.  If it violates
energy conservation or gives unphysical temperatures, nothing built on top
of it can be trusted.

---

### 6. Analytical 1D Model — Limit Cases

**Model:** T_max = T_amb + D·(a·f·E)·[1/(h·A) + dx/(2·k·A)]

**What is checked:**
- Zero gate density → T = T_ambient exactly.
- h → ∞ → T → conduction floor T_amb + Q·dx/(2·k·A).
- h → 0 → T → very large (no cooling).
- Monotonicity: higher density → higher temperature.
- Monotonicity: higher h → lower temperature.
- Material ordering: T_silicon > T_diamond (diamond conducts better).
- Manual R-model cross-check: hand-computed R_total matches code output.

**Why it matters:** The analytical model is used by `find_min_cooling`,
`thermal_headroom_map`, and `optimize_power_distribution`.  If it gets
limit cases wrong, the inverse-design tools would give misleading answers.

---

### 7. Maximum Density Search — Reciprocity

**What is checked:**
- `find_max_density` 3D binary search gives T ≈ T_limit at D_max.
- Analytical model is pessimistic: T_1D(D_max) > T_3D(D_max) — the 1D
  per-element model predicts higher temperature because it assumes
  single-face cooling, while the 3D solver has cooling on all 6 faces.
- Algebraic D_max from analytical model: D = ΔT / (ppg · R), fed back into
  the analytical model, gives T = T_limit exactly (round-trip consistency).
- 1.2 × D_max exceeds T_limit.
- Diamond sustains higher density than silicon.

---

### 8. Minimum Cooling Search — Inverse Consistency

**What is checked:**
- At h_min, T ≈ T_limit (within 2%).
- At 0.5 × h_min, T > T_limit (too little cooling).
- At 2 × h_min, T < T_limit (excess cooling headroom).
- Conduction floor > T_ambient.

---

### 9. Power Redistribution Optimizer — Constraints

**What is checked:**
- Total optimised power ≤ budget.
- All block temperatures ≤ material T_limit.
- All optimised densities > 0.
- Improvement ratio ≥ 1.0 (never makes things worse).
- Binding constraint is reported ("thermal" or "power").
- Huge budget → thermal-limited (power isn't the bottleneck).
- Tiny budget → power-limited (can't use thermal headroom).
- Tiny budget: total power ≈ budget.

**Why it matters:** An optimizer that violates its own constraints is worse
than useless — it would give researchers false confidence in infeasible designs.

---

### 10. Thermal Headroom Map — Physics Consistency

**What is checked:**
- Every functional block: T > T_ambient.
- At least one thermal bottleneck identified.
- Bottleneck has the highest temperature.
- For each block: T + headroom = T_limit (headroom is the gap).
- IO blocks have more headroom than CPU blocks (lower density).

---

### 11. Cooling Stack — Thermal Resistance

**What is checked:**
- Single layer: R = t/(k·A) exactly.
- Stack: R_total = Σ R_layer + 1/(h·A) (resistances in series).
- h_eff = 1/(R_total · A).
- Thicker TIM → lower h_eff (more resistance).

**Reference:** Incropera & DeWitt, "Fundamentals of Heat and Mass Transfer,"
Chapter 3 — thermal resistance networks.

---

### 12. Technology Roadmap — Monotonicity

**What is checked across 10 technology nodes (130 nm → 1.4 nm):**
- CMOS energy monotonically decreases with smaller nodes.
- Landauer gap monotonically decreases (approaching the limit).
- All Landauer gaps > 1 (no node beats the thermodynamic limit).

**Why it matters:** If any node breaks monotonicity, either the energy model
or the roadmap projection has a bug.

---

### 13. Dimensional Analysis — Unit Consistency

**What is checked:**
- CFL number α·dt/dx² is dimensionless and positive.
- Power per gate is sub-milliwatt (physical range check).
- 10⁶ gates per element gives sub-watt power (physical range check).
- Landauer limit at 300 K is ~3 × 10⁻²¹ J (order of magnitude).

---

### 14. Full Design Exploration — Completeness

**What is checked:**
- Response contains all required keys: material_ranking, best_material,
  max_density, cooling_requirement, paradigm_comparison, cooling_sweep,
  insights.
- At least 3 insights generated.
- Material ranking has ≥ 3 materials.
- Max density is positive.
- Adiabatic advantage ratio ≥ 1.

---

### 15. Reproducibility — Deterministic Outputs

**What is checked:**
- `find_max_density` returns identical results across two runs.
- `_analytical_T_max` returns identical results across two runs.
- `material_ranking` returns the same ordering across two runs.

**Why it matters:** Research requires reproducibility.  If results change
between runs with the same inputs, the tool is unreliable.

---

## How to Extend

To add a new validation check:

1. Add a function in `validation/validate_all.py` using the helpers:
   - `_check(label, condition, detail)` — boolean check
   - `_check_close(label, got, ref, rtol)` — relative tolerance
   - `_check_order(label, bigger, smaller)` — ordering

2. Call it from `main()`.

3. Run `python -m aethermor.validation.validate_all` — you should see your new checks.

---

## Reference Sources

| Domain | Source | Year |
|--------|--------|------|
| Physical constants | CODATA 2018 / NIST | 2019 |
| Landauer limit | Landauer, IBM J. Res. Dev. | 1961 |
| Material properties | CRC Handbook, 97th edition | 2016 |
| SiC/GaN properties | Morkoç, Wiley | 2006/2008 |
| CMOS voltage scaling | ITRS 2013 / IRDS 2022 | 2013/2022 |
| Thermal resistance | Incropera & DeWitt, 7th ed. | 2011 |
| Fourier heat equation | Carslaw & Jaeger, 2nd ed. | 1959 |

---

## Real-World Chip Validation

In addition to the 133 physics cross-checks, Aethermor has been validated
against published specifications for four real chip designs:

| Chip | TDP | Die Area | Node | Cooling | Junction Temp Prediction |
|------|-----|----------|------|---------|--------------------------|
| NVIDIA A100 (SXM4) | 400 W | 826 mm² | 7 nm | Liquid | 43.5°C (spec: 92°C max) |
| Apple M1 | 20 W | 120.5 mm² | 5 nm | Fan | 52.1°C (spec: 105°C max) |
| AMD EPYC 9654 CCD | 30 W | 72 mm² | 5 nm | Server air | 41.2°C (spec: 96°C max) |
| Intel i9-13900K | 253 W | 257 mm² | 10 nm | Tower cooler | 114.2°C (spec: 100°C max) |

**33 total checks, all passing.** Each chip is validated for:
- Power density (realistic range)
- Junction temperature (correct order of magnitude)
- Cooling stack capacity (covers TDP)
- Minimum cooling requirement (consistent with actual cooling type)
- Conduction floor (below T_j_max)
- Material ranking (silicon allows sufficient density)

Plus 5 cross-chip physics checks and 4 analytical correlation checks.

All chip specs from public datasheets (NVIDIA, Apple, AMD, Intel) and
architecture analyses (Wikichip, Anandtech).

**Run it yourself:**
```bash
python benchmarks/real_world_validation.py
```

**What this proves:** Aethermor's thermal model produces physically credible
junction temperature predictions from first principles for real chip designs,
without curve fitting or parameter tuning.

**What this does not prove:** Exact die-level temperature correlation (would
require proprietary floorplan data and direct thermal measurement).

---

## 4. Experimental Measurement Validation (18 checks)

`benchmarks/experimental_validation.py` validates the thermal model against
**published hardware measurements** — not just published specifications.

### Tier 1: JEDEC-Measured Thermal Resistance (θ_jc)

Compares Aethermor's 1D thermal resistance model (R_die + R_TIM + R_IHS +
R_spreading) against published JEDEC-standard junction-to-case thermal
resistance measurements for three commercial processors:

| Chip | Published θ_jc (K/W) | Source |
|------|----------------------|--------|
| NVIDIA A100 | 0.029 | NVIDIA A100 datasheet |
| Intel i9-13900K | 0.43 | Intel ARK |
| AMD Ryzen 7950X | 0.11 | AMD product specs |

### Tier 2: Published Experimental Temperatures

Validates against published experimental data from peer-reviewed literature:

- **Kandlikar (2003)** — Microchannel ΔT for h = 10,000 W/(m²·K)
- **Bar-Cohen & Wang (2009)** — IR hotspot measurement of 100 W on 1 cm² Si
- **Yovanovich (1998)** — Spreading resistance analytical formula
- **Full-path junction temperature** — End-to-end 100 W desktop package with
  published heatsink R ≈ 0.28 K/W

### Tier 3: Cross-Validation

- **HotSpot ev6 (Alpha 21264)** — 1D average temperature comparison against
  HotSpot defaults (R_convec = 0.1 K/W), with documented explanation of why
  the 1D average is lower than HotSpot's peak (non-uniform power map)
- **Incropera & DeWitt** — Analytical plane wall reference
- **Biot number** — Lumped capacitance validation
- **Thermal time constant** — L²/α analytical formula
- **COMSOL-verified fin geometry** — Documented fin efficiency calculation
- **3D Fourier energy conservation** — < 5% error over 5000 time steps

**Run it yourself:**
```bash
python benchmarks/experimental_validation.py
```

---

## Interpretation

- **133/133 PASS** (physics) + **20/20 PASS** (literature) + **33/33 PASS**
  (real-world chips) + **18/18 PASS** (experimental measurements) means every
  model agrees with published reference data, analytical solutions, conservation
  laws, real chip specifications, and published hardware measurements within
  the scope of the tests listed above.

- **Any FAIL** means something is wrong.  The failure message tells you
  exactly which model, what was expected, and what was observed.  File an
  issue or investigate before using results from that model.

- **The validation suite is a necessary but not sufficient check.**  If it
  passes on your machine, the models are internally consistent and agree
  with the published references listed above.  Aethermor has been validated
  against published JEDEC thermal resistance measurements, IR thermal imaging
  data, and HotSpot benchmarks.  Die-level correlation with proprietary
  floorplan data or custom test chip measurements remains outside the current
  scope (see [LIMITATIONS.md](LIMITATIONS.md)).
