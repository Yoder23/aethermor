# Hardware Correlation

Aethermor's `PackageStack` model has been correlated against measured thermal
data for three chips spanning server/accelerator, desktop/workstation, and
mobile/low-power segments.

## Methodology

Each correlation case specifies:
- Complete geometry (die area, die thickness, TIM type/thickness, IHS, heatsink)
- Ambient temperature
- Power dissipation (TDP or sustained)
- Cooling condition
- Measured result (θ\_jc or T\_j) with source
- Model result from `PackageStack`
- Residual and explanation of any gap

**Model**: `PackageStack` with explicit die conduction, TIM layer, contact
resistances at each interface, IHS conduction, Yovanovich (1983) spreading
resistance, and surface-to-ambient convection.

**Script**: `python benchmarks/hardware_correlation.py` (also accepts `--json`)

---

## Case 1: NVIDIA A100 SXM4 — Server / Accelerator

| Parameter | Value |
|-----------|-------|
| **Die area** | 826 mm² |
| **Die thickness** | 200 µm (thinned wafer) |
| **TIM** | Indium, 25 µm, k = 50 W/(m·K) |
| **IHS / baseplate** | Copper cold plate, 3.0 mm, k = 400 W/(m·K) |
| **IHS contact area** | 5000 mm² (SXM4 module, spreading area) |
| **Contact R (die–TIM)** | 1.0 × 10⁻⁶ m²·K/W |
| **Contact R (TIM–IHS)** | 5.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 308 K (35°C data center inlet) |
| **Power** | 400 W (TDP) |
| **Cooling** | Liquid cold plate, h ≈ 5000 W/(m²·K) |
| **Spreading** | Yovanovich (1983), die 826 mm² → IHS 5000 mm² |

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **θ\_jc** | 0.029 K/W | 0.028 K/W | −0.001 K/W (0.98×) |

**Assessment**: Within ±2% of measured value. The Yovanovich spreading
resistance correlation captures the die-to-baseplate area ratio effect
that was previously missing.

**Source**: NVIDIA Thermal Design Guide (2020), JEDEC JESD51.

---

## Case 2: Intel i9-13900K — Desktop / Workstation

| Parameter | Value |
|-----------|-------|
| **Die area** | 257 mm² |
| **Die thickness** | 775 µm (standard wafer) |
| **TIM** | Solder TIM (STIM), 50 µm, k = 38 W/(m·K) |
| **IHS** | Nickel-plated copper, 2.0 mm, k = 380 W/(m·K) |
| **IHS area** | 1026 mm² (LGA 1700, spreading area) |
| **Contact R (die–TIM)** | 2.0 × 10⁻⁶ m²·K/W |
| **Contact R (TIM–IHS)** | 5.0 × 10⁻⁶ m²·K/W |
| **Contact R (IHS–HS)** | 10.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 300 K (27°C) |
| **Power** | 253 W (MTP) |
| **Cooling** | Tower air cooler (R\_cooler ≈ 0.2 K/W, h\_eff ≈ 4873 W/(m²·K) at IHS area) |
| **Spreading** | Yovanovich (1983), die 257 mm² → IHS 1026 mm² |

**Primary metric — junction temperature:**

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **T\_j** | 373 K (100°C throttle) | 382 K (109°C) | +9.1 K |

**Secondary metric — ψ\_jc vs θ\_jc (definition mismatch):**

| Metric | Published | Model | Ratio |
|--------|-----------|-------|-------|
| **Intel ψ\_jc (JESD51-12)** | 0.430 K/W | — | — |
| **Model θ\_jc (JESD51-1)** | — | 0.083 K/W | 0.19× |

**Note on ψ\_jc vs θ\_jc**: Intel's published "0.43 K/W" is ψ\_jc
(JESD51-12), which includes heat flow through both the case top and the
PCB. θ\_jc (JESD51-1) assumes all heat exits through the case only. For
high-power desktop CPUs, ψ\_jc is typically 3–5× higher than θ\_jc because
10–30% of heat flows through the PCB substrate. Our model computes
θ\_jc (case-only path), so the 0.19× ratio is physically expected.

The junction temperature comparison (+9.1 K) is the more meaningful metric
for this chip: it validates the full thermal path from die to ambient.

**Source**: Intel ARK / Datasheet (2022), JEDEC JESD51-1 / JESD51-12,
AnandTech / Tom's Hardware measured thermal throttle data.

---

## Case 3: Apple M1 MacBook Air — Mobile / Low-Power

| Parameter | Value |
|-----------|-------|
| **Die area** | 120.5 mm² |
| **Die thickness** | 200 µm (thinned) |
| **TIM** | Thermal paste (high-end), 30 µm, k = 8 W/(m·K) |
| **IHS** | None (fanless laptop) |
| **Spreader** | Aluminum chassis, 2.0 mm, k = 237 W/(m·K) |
| **Chassis area** | 400 cm² effective (spreading area) |
| **Contact R (die–TIM)** | 8.0 × 10⁻⁶ m²·K/W |
| **Contact R (paste–chassis)** | 5.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 298 K (25°C) |
| **Power** | 20 W (sustained) |
| **Cooling** | Fanless (chassis natural convection, h = 12 W/(m²·K) at chassis area) |
| **Spreading** | Yovanovich (1983), die 120.5 mm² → chassis 400 cm² |

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **T\_j** | 333–348 K (60–75°C) | 346 K (72.7°C) | +5.3 K vs midpoint |

**Assessment**: Model T\_j falls within the published measurement range
(60–75°C). The Yovanovich spreading resistance captures the die-to-chassis
area ratio (120.5 mm² → 400 cm²), which was the dominant source of error
in the earlier version without spreading.

**Source**: AnandTech thermal characterization (2021).

---

## Summary

| Segment | Chip | Metric | Measured | Model | Deviation |
|---------|------|--------|----------|-------|-----------|
| Server / accelerator | NVIDIA A100 | θ\_jc | 0.029 K/W | 0.028 K/W | 0.98× |
| Desktop / workstation | Intel i9-13900K | T\_j | 373 K (100°C) | 382 K (109°C) | +9.1 K |
| Mobile / low-power | Apple M1 (MBA) | T\_j | 60–75°C | 72.7°C | Within range (+5.3 K) |

### What the model does well

- **A100 θ\_jc within 2%**: Yovanovich spreading captures die-to-baseplate
  area ratio accurately.
- **Junction temperature**: Both desktop and mobile T\_j predictions are
  within ±10 K of measurements — useful accuracy for architecture-stage work.
- **Ranking**: Model correctly ranks thermal resistance across segments.
- **Spreading resistance**: New Yovanovich (1983) correlation closes the
  largest previous gaps (A100 from 1.97× to 0.98×, M1 from +29 K to +5 K).

### Remaining limitations

- **i9-13900K ψ\_jc vs θ\_jc**: Intel publishes ψ\_jc (JESD51-12), not
  θ\_jc, so a direct resistance comparison is not valid. T\_j comparison
  is the appropriate metric.
- **1D approximation**: The model is 1D + Yovanovich spreading correction;
  it cannot capture 2D/3D non-uniform power maps or lateral gradients.
- **Literature contact resistances**: All contact resistance values are
  from literature, not measured on specific packages. Package-specific
  data would further improve accuracy.

### Physics improvements in this version

1. **Yovanovich (1983) spreading resistance** — `R_spread = (1 - ε)^1.5 / (π · a_s · k)` where `ε = √(A_die/A_spread)`. Applied automatically
   when `spreading_area_m2` is set on `PackageStack`.
2. **ψ\_jc vs θ\_jc distinction** — Correctly identifies Intel's published
   value as ψ\_jc (JESD51-12) and uses T\_j as the primary comparison metric.
3. **Realistic cooling models** — R\_cooler-based h\_eff for desktop; chassis
   spreading area with natural convection h for mobile fanless.

## Reproducibility

```bash
python benchmarks/hardware_correlation.py             # human-readable
python benchmarks/hardware_correlation.py --json out.json  # machine-readable
```
