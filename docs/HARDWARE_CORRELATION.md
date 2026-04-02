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
resistances at each interface, IHS conduction, and surface-to-ambient convection.

**Script**: `python benchmarks/hardware_correlation.py` (also accepts `--json`)

---

## Case 1: NVIDIA A100 SXM4 — Server / Accelerator

| Parameter | Value |
|-----------|-------|
| **Die area** | 826 mm² |
| **Die thickness** | 200 µm (thinned wafer) |
| **TIM** | Indium, 25 µm, k = 50 W/(m·K) |
| **IHS / baseplate** | Copper cold plate, 3.0 mm, k = 400 W/(m·K) |
| **IHS contact area** | 5000 mm² (SXM4 module) |
| **Contact R (die–TIM)** | 1.0 × 10⁻⁶ m²·K/W |
| **Contact R (TIM–IHS)** | 5.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 308 K (35°C data center inlet) |
| **Power** | 400 W (TDP) |
| **Cooling** | Liquid cold plate, h ≈ 5000 W/(m²·K) |

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **θ\_jc** | 0.029 K/W | 0.057 K/W | +0.028 K/W (1.97×) |

**Gap explanation**: Model overpredicts by ~2× because the circular-source
spreading resistance approximation does not match the rectangular A100 die
geometry (26 × 32 mm), and the SXM4 baseplate is optimized for uniform
contact pressure.

**Source**: NVIDIA Thermal Design Guide (2020), JEDEC JESD51.

---

## Case 2: Intel i9-13900K — Desktop / Workstation

| Parameter | Value |
|-----------|-------|
| **Die area** | 257 mm² |
| **Die thickness** | 775 µm (standard wafer) |
| **TIM** | Solder TIM (STIM), 50 µm, k = 38 W/(m·K) |
| **IHS** | Nickel-plated copper, 2.0 mm, k = 380 W/(m·K) |
| **IHS area** | 1026 mm² (LGA 1700) |
| **Contact R (die–TIM)** | 2.0 × 10⁻⁶ m²·K/W |
| **Contact R (TIM–IHS)** | 5.0 × 10⁻⁶ m²·K/W |
| **Contact R (IHS–HS)** | 10.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 300 K (27°C) |
| **Power** | 253 W (MTP) |
| **Cooling** | Tower air cooler, h ≈ 50 W/(m²·K) at die-area ref |

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **θ\_jc** | 0.430 K/W | 0.146 K/W | −0.284 K/W (0.34×) |

**Gap explanation**: Model underpredicts by ~3× because JEDEC θ\_jc for
the i9-13900K includes die-edge effects, solder TIM micro-voiding, and
750 µm-thick die vertical + lateral resistance that the 1D model does not
capture. The contact resistance values used are literature-typical, not
measured for this specific package.

**Source**: Intel ARK / Datasheet (2022), JEDEC JESD51.

---

## Case 3: Apple M1 MacBook Air — Mobile / Low-Power

| Parameter | Value |
|-----------|-------|
| **Die area** | 120.5 mm² |
| **Die thickness** | 200 µm (thinned) |
| **TIM** | Thermal paste (high-end), 30 µm, k = 8 W/(m·K) |
| **IHS** | None (fanless laptop) |
| **Spreader** | Aluminum chassis, 2.0 mm, k = 237 W/(m·K) |
| **Contact R (die–TIM)** | 8.0 × 10⁻⁶ m²·K/W |
| **Contact R (paste–chassis)** | 5.0 × 10⁻⁶ m²·K/W |
| **Ambient** | 298 K (25°C) |
| **Power** | 20 W (sustained) |
| **Cooling** | Fanless (chassis natural convection, h\_eff ≈ 2490 W/(m²·K) at die-area ref) |

| Metric | Measured | Model | Residual |
|--------|----------|-------|----------|
| **T\_j** | 333–348 K (60–75°C) | 369 K (96°C) | +29 K vs midpoint |

**Gap explanation**: Model overpredicts because the 1D model does not capture
the large chassis spreading area (~250 cm²) that the MacBook Air uses for
natural convection. The effective h at die-area reference is an approximation;
real 2D spreading into the chassis lowers the effective resistance further.

**Source**: AnandTech thermal characterization (2021).

---

## Summary

| Segment | Chip | Metric | Measured | Model | Deviation |
|---------|------|--------|----------|-------|-----------|
| Server / accelerator | NVIDIA A100 | θ\_jc | 0.029 K/W | 0.057 K/W | 1.97× |
| Desktop / workstation | Intel i9-13900K | θ\_jc | 0.430 K/W | 0.146 K/W | 0.34× |
| Mobile / low-power | Apple M1 (MBA) | T\_j | 60–75°C | 96°C | +29 K |

### What the model does well

- **Ranking**: The model correctly ranks thermal resistance across segments
  (A100 < 7950X < i9-13900K), matching physical expectations.
- **Order of magnitude**: All θ\_jc predictions are within 3× of measured values.
- **Sensitivity**: Contact resistances visibly contribute to total R, matching
  the real-world observation that TIM quality dominates θ\_jc.

### Where gaps remain

- **i9-13900K**: Thick-die (775 µm) 3D spreading and solder voiding effects
  create a 3× gap. This is the largest known miss.
- **Mobile**: Chassis spreading geometry is not modeled in 1D; only
  approximated through effective h.
- **A100**: Rectangular die vs circular spreading assumption causes 2× error.

### How to close these gaps

1. **Rectangular spreading resistance** — replace circular-source approximation
   with Yovanovich rectangular solution.
2. **Multi-layer spreading** — solve 2D heat equation in the IHS to capture
   die-to-IHS area ratio effects.
3. **Measured contact resistance** — `PackageStack` now models contact
   resistances at die/TIM, TIM/IHS, and IHS/heatsink interfaces using
   literature values. Replacing these with package-specific measured data
   would further close residuals.

## Reproducibility

```bash
python benchmarks/hardware_correlation.py             # human-readable
python benchmarks/hardware_correlation.py --json out.json  # machine-readable
```
