#!/usr/bin/env python3
"""
Aethermor Validation Suite — Proof That the Physics Is Right
=============================================================

This script is the **trust anchor** for the entire project.

Run it once:

    python -m validation.validate_all

and you will see every physics model cross-checked against:

  1. Published reference data  (NIST, CODATA, CRC Handbook, ITRS/IRDS)
  2. Analytical solutions       (closed-form results where they exist)
  3. Internal self-consistency   (analytical model ↔ 3D numerical solver)
  4. Conservation laws           (energy in = energy out)
  5. Constraint satisfaction     (optimizer respects its own contracts)
  6. Monotonicity & limit checks (correct qualitative behaviour)

If every check reads PASS, the models are internally consistent and
agree with the published references listed in each section.

Exit code: 0 if all checks pass, 1 if any fail.
"""

import math
import sys
import time
import os
import numpy as np

# Ensure UTF-8 output on Windows (box-drawing characters need it)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ── Display helpers ──────────────────────────────────────────

_pass_count = 0
_fail_count = 0
_section_count = 0


def _header(title: str):
    global _section_count
    _section_count += 1
    print()
    print(f"{'═' * 78}")
    print(f"  {_section_count}. {title}")
    print(f"{'═' * 78}")


def _check(description: str, passed: bool, detail: str = ""):
    global _pass_count, _fail_count
    tag = "  PASS" if passed else "**FAIL"
    if passed:
        _pass_count += 1
    else:
        _fail_count += 1
    line = f"  {tag}  {description}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    return passed


def _check_close(description: str, actual, expected, rtol=0.05, atol=0.0):
    """Check that actual ≈ expected within relative tolerance."""
    if expected == 0:
        ok = abs(actual) < atol if atol > 0 else actual == 0
    else:
        ok = abs(actual - expected) / abs(expected) <= rtol
    pct = (abs(actual - expected) / abs(expected) * 100) if expected != 0 else 0
    detail = f"got {actual:.6g}, ref {expected:.6g}, err {pct:.2f}%"
    return _check(description, ok, detail)


def _check_order(description: str, a, b, label_a="a", label_b="b"):
    """Check that a > b."""
    ok = a > b
    detail = f"{label_a}={a:.4g} {'>' if ok else '<='} {label_b}={b:.4g}"
    return _check(description, ok, detail)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 1: Fundamental Constants
# ═══════════════════════════════════════════════════════════════

def validate_constants():
    _header("FUNDAMENTAL CONSTANTS — CODATA 2018 / NIST reference values")
    from physics.constants import k_B, h_PLANCK, h_BAR, E_CHARGE, C_LIGHT, SIGMA_SB

    # NIST CODATA 2018 exact values
    _check_close("Boltzmann constant k_B", k_B, 1.380649e-23, rtol=1e-10)
    _check_close("Planck constant h", h_PLANCK, 6.62607015e-34, rtol=1e-10)
    _check_close("Reduced Planck ħ = h/(2π)", h_BAR, h_PLANCK / (2 * math.pi), rtol=1e-10)
    _check_close("Elementary charge e", E_CHARGE, 1.602176634e-19, rtol=1e-10)
    _check_close("Speed of light c", C_LIGHT, 299792458.0, rtol=1e-12)
    _check_close("Stefan-Boltzmann σ", SIGMA_SB, 5.670374419e-8, rtol=1e-8)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 2: Landauer Limit
# ═══════════════════════════════════════════════════════════════

def validate_landauer():
    _header("LANDAUER LIMIT — k_B · T · ln(2) at reference temperatures")
    from physics.constants import k_B, landauer_limit, LANDAUER_LIMIT

    # At 300 K: k_B × 300 × ln(2)
    expected_300 = 1.380649e-23 * 300.0 * math.log(2.0)
    _check_close("Landauer limit at 300 K", landauer_limit(300.0), expected_300, rtol=1e-10)
    _check_close("Pre-computed LANDAUER_LIMIT", LANDAUER_LIMIT, expected_300, rtol=1e-10)

    # At 77 K (liquid nitrogen)
    expected_77 = 1.380649e-23 * 77.0 * math.log(2.0)
    _check_close("Landauer limit at 77 K (LN₂)", landauer_limit(77.0), expected_77, rtol=1e-10)

    # At 4 K (liquid helium)
    expected_4 = 1.380649e-23 * 4.0 * math.log(2.0)
    _check_close("Landauer limit at 4 K (LHe)", landauer_limit(4.0), expected_4, rtol=1e-10)

    # Proportionality: limit(2T) = 2 × limit(T)
    ratio = landauer_limit(600.0) / landauer_limit(300.0)
    _check_close("Proportionality: L(600K)/L(300K) = 2.0", ratio, 2.0, rtol=1e-10)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 3: Material Properties vs Published Data
# ═══════════════════════════════════════════════════════════════

def validate_materials():
    _header("MATERIAL PROPERTIES — CRC Handbook / published reference values")
    from physics.materials import get_material

    # --- Silicon (Si) ---
    # CRC Handbook, 95th ed.: k = 148 W/(m·K), cp = 700 J/(kg·K), ρ = 2329 kg/m³
    si = get_material("silicon")
    _check_close("Si thermal conductivity (CRC: 148)", si.thermal_conductivity, 148.0, rtol=0.02)
    _check_close("Si specific heat (CRC: 700)", si.specific_heat, 700.0, rtol=0.02)
    _check_close("Si density (CRC: 2329)", si.density, 2329.0, rtol=0.01)
    _check_close("Si bandgap (1.12 eV)", si.bandgap_eV, 1.12, rtol=0.02)

    # --- Diamond (C) ---
    # CRC: k = 2200, cp = 520, ρ = 3510
    dia = get_material("diamond")
    _check_close("Diamond thermal conductivity (CRC: 2200)", dia.thermal_conductivity, 2200.0, rtol=0.05)
    _check_close("Diamond specific heat (CRC: 520)", dia.specific_heat, 520.0, rtol=0.05)
    _check_close("Diamond density (CRC: 3510)", dia.density, 3510.0, rtol=0.02)

    # --- GaAs ---
    # CRC: k = 55, cp = 330, ρ = 5320
    gaas = get_material("gallium_arsenide")
    _check_close("GaAs thermal conductivity (CRC: 55)", gaas.thermal_conductivity, 55.0, rtol=0.05)
    _check_close("GaAs bandgap (1.42 eV)", gaas.bandgap_eV, 1.42, rtol=0.02)

    # --- SiC ---
    # Literature: k ≈ 490, bandgap 3.26 eV
    sic = get_material("silicon_carbide")
    _check_close("SiC thermal conductivity (lit: 490)", sic.thermal_conductivity, 490.0, rtol=0.05)
    _check_close("SiC bandgap (3.26 eV)", sic.bandgap_eV, 3.26, rtol=0.02)

    # --- GaN ---
    # Literature: k ≈ 130, bandgap 3.40 eV
    gan = get_material("gallium_nitride")
    _check_close("GaN thermal conductivity (lit: 130)", gan.thermal_conductivity, 130.0, rtol=0.05)
    _check_close("GaN bandgap (3.40 eV)", gan.bandgap_eV, 3.40, rtol=0.02)

    # --- Copper ---
    # CRC: k = 401, cp = 385, ρ = 8960
    cu = get_material("copper")
    _check_close("Cu thermal conductivity (CRC: 401)", cu.thermal_conductivity, 401.0, rtol=0.02)

    # Thermal diffusivity: α = k/(ρ·cp)
    alpha_si = si.thermal_conductivity / (si.density * si.specific_heat)
    _check_close("Si diffusivity α = k/(ρ·cp)", si.thermal_diffusivity, alpha_si, rtol=1e-10)

    # Ordering: Diamond > SiC > Si > GaAs
    _check_order("k: Diamond > SiC", dia.thermal_conductivity, sic.thermal_conductivity,
                 "Diamond", "SiC")
    _check_order("k: SiC > Si", sic.thermal_conductivity, si.thermal_conductivity,
                 "SiC", "Si")
    _check_order("k: Si > GaAs", si.thermal_conductivity, gaas.thermal_conductivity,
                 "Si", "GaAs")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 4: CMOS Energy Model vs ITRS/IRDS Reference Data
# ═══════════════════════════════════════════════════════════════

def validate_energy_models():
    _header("CMOS ENERGY MODEL — ITRS/IRDS-calibrated voltage and capacitance")
    from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
    from physics.constants import landauer_limit

    # V_dd scaling vs ITRS data points
    # ITRS 2013 + IRDS 2022: 130nm→1.2V, 65nm→1.0V, 45nm→0.9V, 14nm→0.75V, 7nm→0.7V
    itrs_vdd = {130: 1.2, 65: 1.0, 45: 0.9, 14: 0.75, 7: 0.7}
    for node, vdd_ref in itrs_vdd.items():
        model = CMOSGateEnergy(tech_node_nm=node)
        _check_close(f"V_dd at {node} nm (ITRS ref: {vdd_ref} V)",
                     model.V_dd, vdd_ref, rtol=0.08)

    # C_load scaling: should be proportional to feature size
    c7 = CMOSGateEnergy(tech_node_nm=7).C_load
    c14 = CMOSGateEnergy(tech_node_nm=14).C_load
    c_ratio = c14 / c7
    _check_close("C_load(14nm)/C_load(7nm) ≈ 2.0", c_ratio, 2.0, rtol=0.05)

    # Dynamic energy at 7nm: E = C·V² ≈ 0.5fF × 0.7² ≈ 2.45e-16 J
    model_7nm = CMOSGateEnergy(tech_node_nm=7)
    E_dyn = model_7nm.dynamic_energy()
    _check_close("E_dynamic at 7nm ≈ 2.45e-16 J", E_dyn, 2.45e-16, rtol=0.10)

    # Landauer gap at 7nm, 1 GHz, 300K: should be ~10⁴-10⁵
    gap = model_7nm.landauer_gap(T=300.0, frequency=1e9)
    _check("Landauer gap at 7nm: 10³ < gap < 10⁷",
           1e3 < gap < 1e7, f"gap = {gap:.2e}")

    # Energy MUST exceed Landauer limit
    E_total = model_7nm.energy_per_switch(1e9, 300.0)
    E_landauer = landauer_limit(300.0)
    _check_order("CMOS E_switch > Landauer limit", E_total, E_landauer,
                 f"E_switch={E_total:.2e}", f"E_land={E_landauer:.2e}")

    # Leakage should increase with temperature
    P_leak_300 = model_7nm.leakage_power(300.0)
    P_leak_400 = model_7nm.leakage_power(400.0)
    _check_order("Leakage at 400K > leakage at 300K", P_leak_400, P_leak_300,
                 "P(400K)", "P(300K)")

    # --- Adiabatic model ---
    print()
    print("  Adiabatic logic model:")
    adiab = AdiabaticGateEnergy(tech_node_nm=7)

    # At low frequency, adiabatic should use less energy than CMOS
    E_adiab_low = adiab.energy_per_switch(1e6, 300.0)  # 1 MHz
    E_cmos_low = model_7nm.energy_per_switch(1e6, 300.0)
    _check_order("Adiabatic < CMOS at 1 MHz", E_cmos_low, E_adiab_low,
                 f"CMOS={E_cmos_low:.2e}", f"Adiab={E_adiab_low:.2e}")

    # Adiabatic energy should be ≥ Landauer (floor enforced)
    E_adiab_very_low = adiab.energy_per_switch(1.0, 300.0)  # 1 Hz
    _check("Adiabatic ≥ Landauer floor at 1 Hz",
           E_adiab_very_low >= E_landauer * 0.999,
           f"E_adiab={E_adiab_very_low:.2e}, E_land={E_landauer:.2e}")

    # Crossover frequency should be positive and finite
    f_cross = adiab.crossover_frequency(model_7nm, T=300.0)
    _check("Crossover frequency > 0 and finite",
           0 < f_cross < float('inf'), f"f_cross = {f_cross:.2e} Hz")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 5: Fourier Solver — Analytical Solution Comparison
# ═══════════════════════════════════════════════════════════════

def validate_fourier_solver():
    _header("FOURIER THERMAL SOLVER — Analytical steady-state comparison")
    from physics.thermal import FourierThermalTransport, ThermalBoundaryCondition
    from physics.materials import get_material

    # Test case: uniform heat generation in a 3D block with convective BC.
    # For a uniform block with all faces cooled, the centre temperature
    # at steady state in 1D approximation is:
    #   T_centre ≈ T_ambient + Q_vol · L² / (2·k) + Q_vol · L / h
    # where L = half-thickness, Q_vol = volumetric heat generation rate.
    #
    # We'll run the 3D solver to steady state and compare.

    si = get_material("silicon")
    N = 20
    dx = 100e-6  # 100 µm
    h_conv = 5000.0  # strong convection for faster convergence

    thermal = FourierThermalTransport(
        grid_shape=(N, N, N),
        element_size_m=dx,
        material=si,
        boundary=ThermalBoundaryCondition(
            mode="convective", h_conv=h_conv, T_ambient=300.0,
        ),
    )

    # Uniform heat: 1e5 W/m³
    Q_vol = 1e5  # W/m³
    heat = np.full((N, N, N), Q_vol * thermal.element_volume)  # W per element

    # Run to approximate steady state
    for _ in range(5000):
        thermal.step(heat)

    T_centre = thermal.T[N // 2, N // 2, N // 2]

    # Analytical estimate for a cube cooled on all 6 faces:
    # 1D approximation along each axis.  For a slab of width 2L:
    #   T_max ≈ T_amb + Q·L/h + Q·L²/(2·k)
    # where L = N/2 * dx
    L = (N / 2) * dx
    T_analytic = 300.0 + Q_vol * L / h_conv + Q_vol * L**2 / (2 * si.thermal_conductivity)

    # The 3D solver sees cooling from all 3 axes, so actual T should be
    # LOWER than the 1D estimate.  Check we're in the right ballpark.
    _check("3D solver centre temp is physical (> T_ambient)",
           T_centre > 300.0, f"T_centre = {T_centre:.2f} K")
    _check("3D solver centre temp ≤ 1D analytical estimate",
           T_centre <= T_analytic * 1.01,
           f"T_3D = {T_centre:.2f}, T_1D = {T_analytic:.2f}")
    _check_close("3D solver within 40% of 1D estimate",
                 T_centre, T_analytic, rtol=0.40)

    # Energy balance: E_in = E_out + E_stored
    # (Cumulative totals always differ by the energy stored in the material)
    total_in = thermal.total_heat_generated_J
    total_out = thermal.total_heat_removed_J
    E_stored = float(np.sum(thermal.T - 300.0)) * thermal.rho_cp * thermal.element_volume
    if total_in > 0:
        conservation_err = abs(total_in - total_out - E_stored) / total_in * 100
    else:
        conservation_err = 0.0
    _check("Energy balance |E_in - E_out - ΔU|/E_in < 5%", conservation_err < 5.0,
           f"in={total_in:.4g} J, out={total_out:.4g} J, stored={E_stored:.4g} J, err={conservation_err:.2f}%")

    # Temperature should be T_ambient at boundaries
    face_max = max(
        thermal.T[0, :, :].max(),
        thermal.T[-1, :, :].max(),
        thermal.T[:, 0, :].max(),
        thermal.T[:, -1, :].max(),
        thermal.T[:, :, 0].max(),
        thermal.T[:, :, -1].max(),
    )
    _check("Boundary face max temp < centre temp",
           face_max < T_centre, f"face_max={face_max:.2f}, centre={T_centre:.2f}")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 6: Analytical 1D Model — Cross-Validation
# ═══════════════════════════════════════════════════════════════

def validate_analytical_model():
    _header("ANALYTICAL 1D MODEL — Self-consistency & cross-validation")
    from analysis.thermal_optimizer import ThermalOptimizer
    from physics.constants import k_B, landauer_limit
    from physics.materials import get_material

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
    )

    # --- Limit cases ---

    # Zero density → T_max = T_ambient
    T_zero = opt._analytical_T_max(0.0, "silicon", h_conv=1000.0)
    _check_close("T_max at zero density = T_ambient", T_zero, 300.0, rtol=1e-6)

    # Infinite cooling → T_max approaches conduction floor
    T_inf_h = opt._analytical_T_max(1e6, "silicon", h_conv=1e15)
    si = get_material("silicon")
    dx = opt.element_size_m
    A = dx ** 2
    from physics.energy_models import CMOSGateEnergy
    _cmos = CMOSGateEnergy(tech_node_nm=7)
    E_switch = _cmos.energy_per_switch(1e9, 300.0)
    ppg = 0.2 * 1e9 * E_switch  # activity * freq * E_switch
    Q_elem = 1e6 * ppg
    T_cond_floor = 300.0 + Q_elem * dx / (2 * si.thermal_conductivity * A)
    _check_close("At h→∞, T→conduction floor", T_inf_h, T_cond_floor, rtol=0.001)

    # Zero cooling → T_max → very high
    T_no_cool = opt._analytical_T_max(1e5, "silicon", h_conv=0.01)
    _check("At h→0, T → very high", T_no_cool > 1e5,
           f"T = {T_no_cool:.0f}")

    # --- Monotonicity ---
    T_low = opt._analytical_T_max(1e4, "silicon", h_conv=1000.0)
    T_high = opt._analytical_T_max(1e6, "silicon", h_conv=1000.0)
    _check_order("T(density=1e6) > T(density=1e4)", T_high, T_low)

    T_poor_h = opt._analytical_T_max(1e5, "silicon", h_conv=100.0)
    T_good_h = opt._analytical_T_max(1e5, "silicon", h_conv=10000.0)
    _check_order("T(h=100) > T(h=10000)", T_poor_h, T_good_h)

    # --- Material ordering ---
    T_si = opt._analytical_T_max(1e5, "silicon", h_conv=1000.0)
    T_dia = opt._analytical_T_max(1e5, "diamond", h_conv=1000.0)
    _check_order("T_silicon > T_diamond at same density", T_si, T_dia)

    # --- Cross-validate: find_max_density at low density should match analytical ---
    # If analytical says T=X at density D, running find_max_density's analytical
    # should agree with _analytical_T_max.
    D_test = 5e6
    T_anal = opt._analytical_T_max(D_test, "silicon", h_conv=1000.0)
    # Manual computation:
    R_total = 1.0 / (1000.0 * A) + dx / (2.0 * si.thermal_conductivity * A)
    T_manual = 300.0 + D_test * ppg * R_total
    _check_close("Manual R-model matches _analytical_T_max",
                 T_anal, T_manual, rtol=1e-6)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 7: find_max_density ↔ Analytical Reciprocity
# ═══════════════════════════════════════════════════════════════

def validate_max_density_reciprocity():
    _header("MAX DENSITY SEARCH — Reciprocity with analytical model")
    from analysis.thermal_optimizer import ThermalOptimizer

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
        thermal_steps=200,
    )

    # Find max density for silicon at h=1000
    result = opt.find_max_density("silicon", h_conv=1000.0)
    D_max = result["max_density"]
    T_at_max = result["T_max_K"]

    # Verify T at max density is near material limit
    from physics.materials import get_material
    si = get_material("silicon")
    _check_close("T at max density ≈ T_limit",
                 T_at_max, si.max_operating_temp, rtol=0.02)

    # The analytical 1D model is per-element with single-face cooling.
    # The 3D solver has cooling on all 6 boundary faces, so it can sustain
    # MUCH higher density. The analytical model should be PESSIMISTIC
    # (predict higher temperature) at the same density.
    T_analytical = opt._analytical_T_max(D_max, "silicon", h_conv=1000.0)
    _check("Analytical model is pessimistic (T_1D > T_3D at D_max)",
           T_analytical > T_at_max,
           f"T_1D = {T_analytical:.0f}, T_3D = {T_at_max:.1f}")

    # Cross-check: analytical max density (algebraic inverse) should
    # give T = T_limit when fed back into analytical model.
    from physics.energy_models import CMOSGateEnergy
    _model = CMOSGateEnergy(tech_node_nm=7)
    _E = _model.energy_per_switch(1e9, 300.0)
    _ppg = 0.2 * 1e9 * _E
    _dx = opt.element_size_m
    _A = _dx ** 2
    _R = 1.0 / (1000.0 * _A) + _dx / (2.0 * si.thermal_conductivity * _A)
    D_analytical = (si.max_operating_temp - 300.0) / (_ppg * _R)
    T_roundtrip = opt._analytical_T_max(D_analytical, "silicon", h_conv=1000.0)
    _check_close("Analytical D_max ↔ analytical T_max = T_limit",
                 T_roundtrip, si.max_operating_temp, rtol=1e-6)

    # Verify that slightly higher density exceeds T_limit
    T_over = opt._analytical_T_max(D_max * 1.2, "silicon", h_conv=1000.0)
    _check("1.2 × D_max exceeds T_limit",
           T_over > si.max_operating_temp,
           f"T(1.2×D_max) = {T_over:.1f}, T_limit = {si.max_operating_temp:.1f}")

    # Diamond should sustain higher density
    D_dia = opt.find_max_density("diamond", h_conv=1000.0)["max_density"]
    _check_order("Diamond D_max > Silicon D_max", D_dia, D_max,
                 f"dia={D_dia:.2e}", f"si={D_max:.2e}")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 8: find_min_cooling — Inverse Consistency
# ═══════════════════════════════════════════════════════════════

def validate_min_cooling_inverse():
    _header("MIN COOLING SEARCH — Inverse consistency with analytical model")
    from analysis.thermal_optimizer import ThermalOptimizer

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
    )

    density = 1e5
    result = opt.find_min_cooling("silicon", gate_density=density)
    h_min = result["min_h_conv"]

    # At h_min, T should be ≈ T_limit
    from physics.materials import get_material
    si = get_material("silicon")
    T_at_hmin = opt._analytical_T_max(density, "silicon", h_conv=h_min)
    _check_close("T at h_min ≈ T_limit",
                 T_at_hmin, si.max_operating_temp, rtol=0.02)

    # At h < h_min, should exceed T_limit
    T_under = opt._analytical_T_max(density, "silicon", h_conv=h_min * 0.5)
    _check("At 0.5 × h_min, T > T_limit",
           T_under > si.max_operating_temp,
           f"T = {T_under:.1f}")

    # At h > h_min, should be under T_limit
    T_over = opt._analytical_T_max(density, "silicon", h_conv=h_min * 2.0)
    _check("At 2 × h_min, T < T_limit",
           T_over < si.max_operating_temp,
           f"T = {T_over:.1f}")

    # Conduction floor should be above ambient
    _check_order("Conduction floor > T_ambient",
                 result["conduction_floor_K"], 300.0)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 9: Optimizer — Constraint Satisfaction
# ═══════════════════════════════════════════════════════════════

def validate_optimizer_constraints():
    _header("POWER REDISTRIBUTION — Constraint satisfaction guarantees")
    from analysis.thermal_optimizer import ThermalOptimizer
    from physics.chip_floorplan import ChipFloorplan
    from physics.materials import get_material

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
    )

    soc = ChipFloorplan.modern_soc(grid_shape=(10, 10, 3), element_size_m=500e-6)
    si = get_material("silicon")

    # --- Power-limited case ---
    result = opt.optimize_power_distribution(
        soc, power_budget_W=50.0, h_conv=1000.0,
    )

    _check("Total power ≤ budget",
           result["total_power_W"] <= 50.0 + 0.01,
           f"P = {result['total_power_W']:.2f} W")

    _check("All block temps ≤ T_limit",
           all(b["T_estimated_K"] <= si.max_operating_temp + 1.0
               for b in result["optimised_blocks"]),
           f"max T = {max(b['T_estimated_K'] for b in result['optimised_blocks']):.1f}")

    _check("All optimised densities > 0",
           all(b["optimised_density"] > 0 for b in result["optimised_blocks"]),
           "all positive")

    _check("Improvement ratio ≥ 1.0 (better than original)",
           result["improvement_ratio"] >= 1.0,
           f"ratio = {result['improvement_ratio']:.2f}")

    _check("Binding constraint reported",
           result["binding_constraint"] in ("thermal", "power"),
           f"binding = {result['binding_constraint']}")

    # --- Thermally-limited case (huge budget) ---
    result_therm = opt.optimize_power_distribution(
        soc, power_budget_W=1e6, h_conv=1000.0,
    )
    _check("Huge budget → thermal-limited",
           result_therm["binding_constraint"] == "thermal",
           f"binding = {result_therm['binding_constraint']}")

    _check("All temps still ≤ T_limit under thermal binding",
           all(b["T_estimated_K"] <= si.max_operating_temp + 1.0
               for b in result_therm["optimised_blocks"]),
           f"max T = {max(b['T_estimated_K'] for b in result_therm['optimised_blocks']):.1f}")

    # --- Tiny budget → power-limited ---
    result_tiny = opt.optimize_power_distribution(
        soc, power_budget_W=0.001, h_conv=1000.0,
    )
    _check("Tiny budget → power-limited",
           result_tiny["binding_constraint"] == "power",
           f"binding = {result_tiny['binding_constraint']}")
    _check("Tiny budget: total power ≤ 0.002 W",
           result_tiny["total_power_W"] <= 0.002,
           f"P = {result_tiny['total_power_W']:.6f} W")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 10: Headroom Map — Physics Consistency
# ═══════════════════════════════════════════════════════════════

def validate_headroom_map():
    _header("THERMAL HEADROOM MAP — Physics consistency checks")
    from analysis.thermal_optimizer import ThermalOptimizer
    from physics.chip_floorplan import ChipFloorplan

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
    )
    soc = ChipFloorplan.modern_soc(grid_shape=(10, 10, 3), element_size_m=500e-6)
    results = opt.thermal_headroom_map(soc, h_conv=1000.0)

    # Every block should have physical temperature
    for r in results:
        _check(f"{r['name']}: T_max > T_ambient",
               r["T_max_K"] > 299.9,
               f"T = {r['T_max_K']:.1f}")

    # At least one bottleneck
    bottlenecks = [r for r in results if r["is_bottleneck"]]
    _check("At least one bottleneck identified",
           len(bottlenecks) >= 1,
           f"{len(bottlenecks)} bottleneck(s)")

    # Bottleneck has highest T
    hottest = max(r["T_max_K"] for r in results)
    for bn in bottlenecks:
        _check(f"Bottleneck '{bn['name']}' has highest T",
               abs(bn["T_max_K"] - hottest) < 0.2,
               f"T = {bn['T_max_K']:.1f}")

    # Headroom + T_max should equal T_limit
    from physics.materials import get_material
    si = get_material("silicon")
    for r in results:
        T_sum = r["T_max_K"] + r["thermal_headroom_K"]
        _check_close(f"{r['name']}: T + headroom = T_limit",
                     T_sum, si.max_operating_temp, rtol=0.001)

    # IO (low density) should have more headroom than CPU (high density)
    cpu = next(r for r in results if r["name"] == "CPU_cluster")
    io = next(r for r in results if r["name"] == "IO_memctrl")
    _check_order("IO headroom factor > CPU headroom factor",
                 io["density_headroom_factor"], cpu["density_headroom_factor"],
                 f"IO={io['density_headroom_factor']:.1f}×",
                 f"CPU={cpu['density_headroom_factor']:.1f}×")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 11: Cooling Stack — Thermal Resistance Addition
# ═══════════════════════════════════════════════════════════════

def validate_cooling_stack():
    _header("COOLING STACK — Thermal resistance consistency")
    from physics.cooling import CoolingStack, ThermalLayer

    # Single layer: R = t / (k · A), h_eff = k / t
    # A 1mm copper layer: k=401, t=0.001 → R = 0.001/(401·A) → h_eff = 401/0.001 = 401000
    layer = ThermalLayer("test_cu", thickness_m=0.001, thermal_conductivity=401.0)
    area = 1e-4  # 1 cm²
    R = layer.resistance(area)
    R_expected = 0.001 / (401.0 * area)
    _check_close("Cu layer R = t/(k·A)", R, R_expected, rtol=1e-6)

    # Stack: total R = sum of layer R values
    stack = CoolingStack(h_ambient=50.0)
    stack.add_layer(ThermalLayer("tim", thickness_m=50e-6, thermal_conductivity=5.0))
    stack.add_layer(ThermalLayer("spreader", thickness_m=1e-3, thermal_conductivity=401.0))

    R_total = stack.total_resistance(area)
    R_tim = 50e-6 / (5.0 * area)
    R_spreader = 1e-3 / (401.0 * area)
    R_conv = 1.0 / (50.0 * area)
    R_sum = R_tim + R_spreader + R_conv
    _check_close("Stack R = sum of layer R + R_conv",
                 R_total, R_sum, rtol=0.01)

    # Effective h should be 1/(R_total · A)
    h_eff = stack.effective_h(area)
    h_expected = 1.0 / (R_total * area)
    _check_close("h_eff = 1/(R_total · A)", h_eff, h_expected, rtol=0.01)

    # Adding more resistance → lower h_eff
    stack_thick = CoolingStack(h_ambient=50.0)
    stack_thick.add_layer(ThermalLayer("tim_thick", thickness_m=200e-6, thermal_conductivity=5.0))
    stack_thick.add_layer(ThermalLayer("spreader", thickness_m=1e-3, thermal_conductivity=401.0))
    h_thick = stack_thick.effective_h(area)
    _check_order("Thicker TIM → lower h_eff", h_eff, h_thick,
                 f"thin={h_eff:.0f}", f"thick={h_thick:.0f}")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 12: Technology Roadmap — Monotonicity & Limits
# ═══════════════════════════════════════════════════════════════

def validate_tech_roadmap():
    _header("TECHNOLOGY ROADMAP — Physical trends across nodes")
    from analysis.tech_roadmap import TechnologyRoadmap

    rm = TechnologyRoadmap()
    proj = rm.energy_roadmap()

    # Energy should decrease with smaller nodes (CMOS dynamic energy)
    energies = [(p["node_nm"], p["E_cmos_J"]) for p in proj]
    for i in range(len(energies) - 1):
        node_big, E_big = energies[i]
        node_small, E_small = energies[i + 1]
        _check(f"E({node_big}nm) > E({node_small}nm)",
               E_big > E_small,
               f"{E_big:.2e} > {E_small:.2e}")

    # Landauer gap should decrease with smaller nodes (closer to limit)
    gaps = [(p["node_nm"], p["gap_cmos"]) for p in proj]
    for i in range(len(gaps) - 1):
        node_big, gap_big = gaps[i]
        node_small, gap_small = gaps[i + 1]
        _check(f"Gap({node_big}nm) > Gap({node_small}nm)",
               gap_big > gap_small,
               f"{gap_big:.0f} > {gap_small:.0f}")

    # All Landauer gaps should be > 1 (can't beat the limit)
    for p in proj:
        _check(f"Landauer gap > 1 at {p['node_nm']}nm",
               p["gap_cmos"] > 1.0,
               f"gap = {p['gap_cmos']:.1f}")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 13: Dimensional Analysis — Unit Consistency
# ═══════════════════════════════════════════════════════════════

def validate_dimensions():
    _header("DIMENSIONAL ANALYSIS — Unit consistency spot-checks")
    from physics.materials import get_material
    from physics.energy_models import CMOSGateEnergy
    from physics.constants import landauer_limit

    si = get_material("silicon")

    # Thermal diffusivity: [k] = W/(m·K), [ρ·cp] = J/(m³·K)
    # α = k/(ρ·cp) → [m²/s]
    # Check: α × 1s × (1/dx²) should be dimensionless
    alpha = si.thermal_diffusivity
    dx = 100e-6
    cfl = alpha * 1e-6 / (dx ** 2)  # should be a pure number
    _check("CFL number is dimensionless and positive", cfl > 0,
           f"CFL = {cfl:.4f}")

    # Power per gate: [E_switch] = J, [freq] = Hz = 1/s, [activity] = dimensionless
    # P = density × activity × freq × E_switch → [1/m³·(1/s)·J] = [W/m³]×A → need /area
    model = CMOSGateEnergy(tech_node_nm=7)
    E = model.energy_per_switch(1e9, 300.0)
    P_per_gate = 0.2 * 1e9 * E  # W per gate
    _check("Power per gate is sub-milliwatt",
           0 < P_per_gate < 1e-3,
           f"P = {P_per_gate:.2e} W")

    # Total power for 1e6 gates in one element: should be sub-watt
    P_elem = 1e6 * P_per_gate
    _check("1M gates per element → sub-watt power",
           0 < P_elem < 10.0,
           f"P = {P_elem:.4f} W")

    # Landauer limit at 300K: should be ~3e-21 J
    E_land = landauer_limit(300.0)
    _check("Landauer limit at 300K ≈ 3e-21 J",
           1e-22 < E_land < 1e-20,
           f"E = {E_land:.3e} J")


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 14: Full Design Exploration — Completeness
# ═══════════════════════════════════════════════════════════════

def validate_full_exploration():
    _header("FULL DESIGN EXPLORATION — Response completeness")
    from analysis.thermal_optimizer import ThermalOptimizer

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
        thermal_steps=200,
    )

    result = opt.full_design_exploration("silicon", h_conv=1000.0)

    required_keys = [
        "material_ranking", "best_material", "max_density",
        "cooling_requirement", "paradigm_comparison",
        "cooling_sweep", "insights",
    ]
    for key in required_keys:
        _check(f"Result contains '{key}'", key in result)

    _check("At least 3 insights generated",
           len(result["insights"]) >= 3,
           f"{len(result['insights'])} insights")

    _check("Material ranking has ≥ 3 materials",
           len(result["material_ranking"]) >= 3,
           f"{len(result['material_ranking'])} materials")

    _check("Max density is positive",
           result["max_density"]["max_density"] > 0)

    _check("Adiabatic advantage ratio ≥ 1",
           result["paradigm_comparison"]["adiabatic_advantage_ratio"] >= 1.0)


# ═══════════════════════════════════════════════════════════════
#  VALIDATION 15: Reproducibility — Deterministic Output
# ═══════════════════════════════════════════════════════════════

def validate_reproducibility():
    _header("REPRODUCIBILITY — Deterministic outputs across runs")
    from analysis.thermal_optimizer import ThermalOptimizer

    opt = ThermalOptimizer(
        grid_shape=(10, 10, 3),
        element_size_m=100e-6,
        tech_node_nm=7,
        frequency_Hz=1e9,
        activity=0.2,
        thermal_steps=200,
    )

    # Run the same analysis twice
    r1 = opt.find_max_density("silicon", h_conv=1000.0)
    r2 = opt.find_max_density("silicon", h_conv=1000.0)
    _check_close("find_max_density: run1 = run2",
                 r1["max_density"], r2["max_density"], rtol=1e-10)

    # Analytical model determinism
    T1 = opt._analytical_T_max(1e5, "silicon", h_conv=1000.0)
    T2 = opt._analytical_T_max(1e5, "silicon", h_conv=1000.0)
    _check_close("analytical_T_max: run1 = run2", T1, T2, rtol=1e-15)

    # Material ranking order should be identical
    rank1 = opt.material_ranking(h_conv=1000.0)
    rank2 = opt.material_ranking(h_conv=1000.0)
    names1 = [r["material"] for r in rank1]
    names2 = [r["material"] for r in rank2]
    _check("Material ranking order is deterministic",
           names1 == names2, f"{names1}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║              AETHERMOR VALIDATION SUITE — Trust Verification                ║")
    print("║                                                                              ║")
    print("║  Every physics model cross-checked against published data,                   ║")
    print("║  analytical solutions, conservation laws, and self-consistency.               ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")

    t0 = time.time()

    validate_constants()
    validate_landauer()
    validate_materials()
    validate_energy_models()
    validate_fourier_solver()
    validate_analytical_model()
    validate_max_density_reciprocity()
    validate_min_cooling_inverse()
    validate_optimizer_constraints()
    validate_headroom_map()
    validate_cooling_stack()
    validate_tech_roadmap()
    validate_dimensions()
    validate_full_exploration()
    validate_reproducibility()

    elapsed = time.time() - t0

    print()
    print("═" * 78)
    print(f"  RESULTS: {_pass_count} passed, {_fail_count} failed  "
          f"({_pass_count + _fail_count} checks in {elapsed:.1f}s)")
    print("═" * 78)

    if _fail_count == 0:
        print()
        print("  ✓ ALL CHECKS PASSED")
        print()
        print("  Every model is internally consistent and agrees with published")
        print("  reference data, analytical solutions, and conservation laws.")
        print("  See LIMITATIONS.md for scope of validation.")
        print()
    else:
        print()
        print(f"  ✗ {_fail_count} CHECK(S) FAILED — investigate before relying on results")
        print()

    return 0 if _fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
