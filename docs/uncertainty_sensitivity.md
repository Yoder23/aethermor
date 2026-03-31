# Uncertainty & Sensitivity Analysis

## Uncertainty Propagation

Aethermor's 1D thermal model has three primary input parameters with
associated uncertainty:

```
Tj = T_amb + TDP × (R_cond + R_conv)
   = T_amb + TDP × (t / (k × A_die) + 1 / (h_conv × A_pkg))
```

### Input Uncertainties

| Parameter | Typical Range | Source of Uncertainty |
|-----------|--------------|---------------------|
| k (thermal conductivity) | ±5% | Material purity, temperature dependence, crystal orientation |
| h_conv (convection coefficient) | ±20–30% | Flow conditions, mounting pressure, TIM variation |
| TDP (thermal design power) | ±10% | Workload variation, voltage/frequency scaling |
| Die/package area | ±2% | Manufacturing tolerance (negligible) |

### Propagation Example: Intel i9-13900K

Base case: TDP = 253W, k_Si = 150 W/(m·K), h_conv = 4000 W/(m²·K) → **Tj = 93.7°C**

```python
import numpy as np
from aethermor.physics.materials import get_material
from aethermor.physics.thermal import FourierThermalTransport

# Monte Carlo uncertainty propagation
np.random.seed(42)
N = 10000
T_amb = 300.0
die_area = 257e-6    # m²
pkg_area = 1026e-6   # m²
t_die = 0.000775     # m

tdp_samples = np.random.normal(253, 253 * 0.10, N)    # ±10%
k_samples = np.random.normal(150, 150 * 0.05, N)      # ±5%
h_samples = np.random.normal(4000, 4000 * 0.25, N)    # ±25%

R_cond = t_die / (k_samples * die_area)
R_conv = 1.0 / (h_samples * pkg_area)
Tj = T_amb + tdp_samples * (R_cond + R_conv) - 273.15  # °C

print(f"Tj: {np.mean(Tj):.1f} ± {np.std(Tj):.1f} °C")
print(f"95% CI: [{np.percentile(Tj, 2.5):.1f}, {np.percentile(Tj, 97.5):.1f}] °C")
```

**Result**: Tj = 95.4 ± 13.8°C (95% CI: [71.4, 126.4°C])

The dominant uncertainty source is h_conv (±25% drives most of the spread).

---

## Sensitivity Analysis

Which input parameters matter most for junction temperature?

### One-at-a-time (OAT) Sensitivity

Perturbing each parameter by ±10% while holding others fixed:

| Parameter | -10% Tj (°C) | Base Tj (°C) | +10% Tj (°C) | Sensitivity |
|-----------|-------------|-------------|-------------|-------------|
| TDP (253W) | 87.0 | 93.7 | 100.4 | **High** |
| h_conv (4000) | 100.5 | 93.7 | 87.8 | **High** |
| k_Si (150) | 93.9 | 93.7 | 93.5 | Low |
| A_die (257 mm²) | 93.9 | 93.7 | 93.5 | Low |
| A_package (1026 mm²) | 100.5 | 93.7 | 87.8 | **High** |

### Key Insight

For the i9-13900K (and most air/liquid-cooled desktop/server chips):

1. **h_conv and package area dominate** — convection resistance (R_conv) is
   10–15× larger than conduction resistance (R_cond)
2. **Material conductivity (k) barely matters** — this is the "conduction
   floor" effect. Upgrading from silicon to diamond changes Tj by < 1°C
   when R_conv dominates
3. **The conduction floor becomes important** when h_conv is very high
   (> 5000 W/m²·K, i.e. aggressive liquid cooling), at which point R_cond
   and R_conv become comparable and substrate choice starts to matter

This is why Aethermor's core insight — that substrate thermal conductivity
matters more at high cooling levels — is physically robust: it's a direct
consequence of the relative magnitudes of R_cond and R_conv.

### When Does Substrate Matter?

```
R_conv >> R_cond  →  Cooling-limited regime  →  k doesn't matter
R_conv ≈  R_cond  →  Balanced regime          →  Both matter
R_conv << R_cond  →  Conduction-limited regime →  k dominates
```

Aethermor's `cooling_sweep()` detects this transition automatically and
reports the conduction floor — the maximum cooling benefit achievable for
a given substrate.

---

## Transient Thermal Modeling (Roadmap)

Aethermor v1.0 provides **steady-state** thermal analysis only. Transient
thermal dynamics — how temperature evolves over time — are on the roadmap:

### What's Missing

- Time-dependent temperature response to power step changes
- Thermal time constants (τ = R × C) for die and package
- Worst-case transient temperature overshoot
- Duty-cycle aware thermal analysis

### Planned Approach

The existing 3D Fourier solver (`FourierThermalTransport`) already implements
time-stepping with CFL-stable timestep selection. Extending to transient
analysis requires:

1. **Power profile input**: time-varying TDP(t) instead of constant TDP
2. **Thermal capacitance model**: C = ρ × c_p × V for die and package layers
3. **Output**: T(t) trajectory, time-to-steady-state, peak overshoot

### Timeline

Transient support is planned for **v1.1** or **v1.2**. The 3D solver
infrastructure is in place; the main work is power profile handling and
validation against HotSpot transient mode.

For transient analysis today, use HotSpot or COMSOL — and use Aethermor's
steady-state results as the boundary condition.
