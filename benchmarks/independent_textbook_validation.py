#!/usr/bin/env python3
"""
Independent Textbook Validation
================================

Validates Aethermor against published, independently verifiable thermal
engineering problems from standard references.  Every expected value in
this file can be reproduced with a calculator and the cited textbook.

Any engineer can independently verify these results without trusting the
developer — that is the purpose of this script.

References:
  [1] Incropera, DeWitt, Bergman, Lavine — "Fundamentals of Heat and
      Mass Transfer", 7th ed. (Wiley, 2011)
  [2] Cengel & Ghajar — "Heat and Mass Transfer", 5th ed. (McGraw-Hill, 2015)
  [3] Yovanovich — "Spreading Resistance of Isoflux Rectangles and Strips on
      Compound Flux Channels", J. Thermophysics & Heat Transfer 13(4), 1999

Run:
    python benchmarks/independent_textbook_validation.py
"""
import sys
import math

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aethermor.physics.cooling import (
    PackageStack, CoolingStack, ThermalLayer, THERMAL_LAYERS,
)
from aethermor.physics.materials import get_material

_pass = 0
_fail = 0


def check(name, expected, actual, tol_pct=5.0, tol_abs=None):
    """Compare actual vs expected with tolerance."""
    global _pass, _fail
    if tol_abs is not None:
        ok = abs(actual - expected) <= tol_abs
    else:
        if expected == 0:
            ok = abs(actual) < 1e-12
        else:
            ok = abs((actual - expected) / expected) * 100 <= tol_pct
    status = "PASS" if ok else "FAIL"
    if not ok:
        _fail += 1
    else:
        _pass += 1
    pct = ((actual - expected) / expected * 100) if expected != 0 else 0
    print(f"  [{status}] {name}")
    print(f"         Expected: {expected:.6g}   Got: {actual:.6g}   ({pct:+.2f}%)")


def section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


# ======================================================================
# TEST 1: 1D plane wall conduction — Incropera Example 3.1
# ======================================================================
def test_plane_wall():
    """
    Single-layer plane wall conduction.

    Reference: Incropera & DeWitt, 7th ed., Example 3.1
    A plane wall of thickness L = 0.3 m, k = 0.72 W/(m·K), area = 1 m²,
    internal surface T₁ = 400°C, external surface T₂ = 100°C.
    Expected: q = k·A·(T₁ - T₂)/L = 0.72 × 1 × 300 / 0.3 = 720 W
    Expected: R = L/(k·A) = 0.3/(0.72 × 1) = 0.4167 K/W
    """
    section("TEST 1: Plane Wall Conduction (Incropera Ex. 3.1)")

    layer = ThermalLayer("Test wall", 0.3, 0.72)
    R_model = layer.resistance(1.0)
    R_expected = 0.3 / (0.72 * 1.0)  # 0.4167 K/W
    check("R_wall (K/W)", R_expected, R_model, tol_pct=0.01)

    q_expected = (400 - 100) / R_expected  # 720 W
    q_model = (400 - 100) / R_model
    check("q (W)", q_expected, q_model, tol_pct=0.01)


# ======================================================================
# TEST 2: Series resistance — Incropera Example 3.3
# ======================================================================
def test_composite_wall():
    """
    Composite wall: three layers in series with convection boundaries.

    Reference: Incropera & DeWitt, 7th ed., Section 3.3.1
    Layer A: L=0.3 m, k=25 W/(m·K)
    Layer B: L=0.15 m, k=1.0 W/(m·K)
    Layer C: L=0.15 m, k=50 W/(m·K)
    Convection inside: h=10 W/m²K, outside: h=20 W/m²K
    Area = 1 m²

    R_total = 1/h_in + L_A/k_A + L_B/k_B + L_C/k_C + 1/h_out
            = 0.1 + 0.012 + 0.15 + 0.003 + 0.05 = 0.315 K/W
    """
    section("TEST 2: Composite Wall Series Resistance (Incropera §3.3)")

    # Build with CoolingStack
    stack = CoolingStack(h_ambient=20.0, T_ambient=300.0)
    stack.add_layer(ThermalLayer("Layer A", 0.3, 25.0))
    stack.add_layer(ThermalLayer("Layer B", 0.15, 1.0))
    stack.add_layer(ThermalLayer("Layer C", 0.15, 50.0))

    # CoolingStack doesn't include h_in, just the layers + convection out.
    # R_stack = R_A + R_B + R_C + R_conv_out
    R_stack = stack.total_resistance(1.0)
    R_expected = 0.3/25 + 0.15/1.0 + 0.15/50 + 1/20  # = 0.215 K/W
    check("R_stack (K/W)", R_expected, R_stack, tol_pct=0.01)

    # With inside convection added:
    R_total = 1.0/10.0 + R_expected  # 0.315 K/W
    check("R_total with h_in (K/W)", R_total, 1.0/10.0 + R_stack, tol_pct=0.01)


# ======================================================================
# TEST 3: PackageStack — silicon die 1D conduction
# ======================================================================
def test_silicon_die_resistance():
    """
    Bare silicon die thermal resistance.

    Reference: Direct calculation, k_Si = 148 W/(m·K)
    Die: 10 mm × 10 mm × 0.5 mm (100 mm², 500 µm)
    R = L/(k·A) = 0.5e-3 / (148 × 100e-6) = 0.0338 K/W
    """
    section("TEST 3: Bare Si Die Thermal Resistance")

    R_expected = 0.5e-3 / (148.0 * 100e-6)  # 0.03378 K/W

    pkg = PackageStack(
        die_thickness_m=0.5e-3,
        die_conductivity=148.0,
        h_ambient=1000.0,
    )
    # theta_jc with no TIM/IHS is just die conduction
    R_model = pkg.theta_jc(100e-6)
    check("R_die (K/W)", R_expected, R_model, tol_pct=0.01)


# ======================================================================
# TEST 4: Yovanovich spreading resistance — analytical solution
# ======================================================================
def test_yovanovich_spreading():
    """
    Yovanovich (1983) spreading resistance for concentric circles.

    Reference: Yovanovich, Cooper, Centurion (1983)
    Circular source a = 5 mm on plate b = 25 mm, k = 400 W/(m·K).
    ε = a/b = 0.2
    φ(ε) = 1 - 1.4092×0.2 + 0.3381×0.2³ + 0.0679×0.2⁵ + 0.0194×0.2⁷
         = 1 - 0.28184 + 0.002705 + 0.0000217 + 0.0000000249
         ≈ 0.72089
    R_sp = φ / (4·k·a) = 0.72089 / (4×400×0.005) = 0.09011 K/W
    """
    section("TEST 4: Yovanovich Spreading Resistance")

    a = 0.005  # 5 mm radius source
    b = 0.025  # 25 mm radius plate
    k = 400.0
    eps = a / b  # 0.2

    phi = (1.0 - 1.4092 * eps + 0.3381 * eps**3
           + 0.0679 * eps**5 + 0.0194 * eps**7)
    R_expected = phi / (4.0 * k * a)

    # Compute via PackageStack's internal method
    source_area = math.pi * a**2  # π × 25e-6 = 78.54e-6 m²
    sink_area = math.pi * b**2    # π × 625e-6 = 1963.5e-6 m²
    R_model = PackageStack._spreading_resistance(source_area, sink_area, k)
    check("R_spread (K/W)", R_expected, R_model, tol_pct=0.01)


# ======================================================================
# TEST 5: Convection resistance — Incropera fundamentals
# ======================================================================
def test_convection_resistance():
    """
    Convective thermal resistance R = 1/(h·A).

    Reference: Incropera & DeWitt, Eq. 1.12
    h = 500 W/(m²·K), A = 200e-6 m² (200 mm²)
    R = 1 / (500 × 200e-6) = 10.0 K/W
    """
    section("TEST 5: Convection Resistance")

    R_expected = 1.0 / (500.0 * 200e-6)  # 10.0 K/W

    stack = CoolingStack(h_ambient=500.0)
    R_model = stack.total_resistance(200e-6)  # no layers, just convection
    check("R_conv (K/W)", R_expected, R_model, tol_pct=0.01)


# ======================================================================
# TEST 6: PackageStack with known multi-layer R — hand-calculable
# ======================================================================
def test_hand_calculable_package():
    """
    Complete package path with known analytical R_total.

    Setup: 200 µm Si die, 25 µm paste (k=5), 2 mm Cu IHS (k=400),
           h = 1000 W/m²K, A_die = 100 mm², no contacts, no spreading.
    R = R_die + R_TIM + R_IHS + R_conv
      = 0.5e-3/(148×1e-4) + 25e-6/(5×1e-4) + 2e-3/(400×1e-4) + 1/(1000×1e-4)
      = 0.03378 + 0.05 + 0.05 + 10.0
      = 10.1338 K/W

    T_j at 10 W = 300 + 10 × 10.1338 = 401.34 K
    """
    section("TEST 6: Full Package Path (hand-calculable)")

    A = 100e-6
    R_die = 200e-6 / (148.0 * A)
    R_tim = 25e-6 / (5.0 * A)
    R_ihs = 2e-3 / (400.0 * A)
    R_conv = 1.0 / (1000.0 * A)
    R_total_expected = R_die + R_tim + R_ihs + R_conv

    pkg = PackageStack(
        die_thickness_m=200e-6,
        die_conductivity=148.0,
        tim=ThermalLayer("TIM", 25e-6, 5.0),
        ihs=ThermalLayer("IHS", 2e-3, 400.0),
        h_ambient=1000.0,
        T_ambient=300.0,
    )
    R_model = pkg.total_resistance(A)
    check("R_total (K/W)", R_total_expected, R_model, tol_pct=0.01)

    T_j_expected = 300.0 + 10.0 * R_total_expected
    T_j_model = pkg.junction_temperature(A, 10.0)
    check("T_j at 10 W (K)", T_j_expected, T_j_model, tol_abs=0.001)


# ======================================================================
# TEST 7: PackageStack with spreading — hand-calculable
# ======================================================================
def test_package_with_spreading():
    """
    Package with known spreading resistance — all values hand-calculable.

    Setup: 200 µm Si die, 50 µm paste (k=5), 3 mm Cu IHS (k=400),
           Die area = 100 mm², IHS area = 400 mm², h = 2000, T_amb = 300 K.
    A_die = 100e-6, A_IHS = 400e-6.
    Yovanovich: a_src = √(1e-4/π) = 0.005642, a_sink = √(4e-4/π) = 0.011284
    ε = 0.5, φ = 1 - 1.4092×0.5 + 0.3381×0.125 + 0.0679×0.03125 + 0.0194×0.0078125
             = 1 - 0.7046 + 0.04226 + 0.002122 + 0.0001516 = 0.33993
    R_sp = 0.33993 / (4×400×0.005642) = 0.03754 K/W

    R_die      = 200e-6 / (148 × 1e-4)     = 0.01351 K/W
    R_tim      = 50e-6 / (5 × 1e-4)        = 0.10000 K/W
    R_spread   = 0.03754 K/W
    R_ihs      = 3e-3 / (400 × 4e-4)       = 0.01875 K/W  (at IHS area)
    R_conv     = 1 / (2000 × 4e-4)         = 1.25000 K/W  (at IHS area)
    R_total    = 1.41980 K/W

    At 50 W: T_j = 300 + 50 × 1.41980 = 370.99 K
    """
    section("TEST 7: Package + Spreading (hand-calculable)")

    A_die = 100e-6
    A_ihs = 400e-6
    k_ihs = 400.0

    # Hand-compute spreading resistance
    a_src = math.sqrt(A_die / math.pi)
    a_sink = math.sqrt(A_ihs / math.pi)
    eps = a_src / a_sink
    phi = (1.0 - 1.4092 * eps + 0.3381 * eps**3
           + 0.0679 * eps**5 + 0.0194 * eps**7)
    R_sp_expected = phi / (4.0 * k_ihs * a_src)

    R_die = 200e-6 / (148.0 * A_die)
    R_tim = 50e-6 / (5.0 * A_die)
    R_ihs = 3e-3 / (k_ihs * A_ihs)
    R_conv = 1.0 / (2000.0 * A_ihs)
    R_total_expected = R_die + R_tim + R_sp_expected + R_ihs + R_conv

    pkg = PackageStack(
        die_thickness_m=200e-6,
        die_conductivity=148.0,
        tim=ThermalLayer("TIM", 50e-6, 5.0),
        ihs=ThermalLayer("IHS", 3e-3, k_ihs),
        h_ambient=2000.0,
        T_ambient=300.0,
        spreading_area_m2=A_ihs,
    )
    R_model = pkg.total_resistance(A_die)
    check("R_total with spreading (K/W)", R_total_expected, R_model, tol_pct=0.1)

    T_j_expected = 300.0 + 50.0 * R_total_expected
    T_j_model = pkg.junction_temperature(A_die, 50.0)
    check("T_j at 50 W (K)", T_j_expected, T_j_model, tol_abs=0.01)

    # Verify spreading resistance component
    R_sp_model = PackageStack._spreading_resistance(A_die, A_ihs, k_ihs)
    check("R_spread Yovanovich (K/W)", R_sp_expected, R_sp_model, tol_pct=0.01)


# ======================================================================
# TEST 8: Material property cross-check — Si conductivity
# ======================================================================
def test_silicon_conductivity():
    """
    Silicon thermal conductivity at 300 K.

    Reference: CRC Handbook of Chemistry and Physics, 97th ed.
    k_Si(300 K) = 148 W/(m·K) (single-crystal)
    """
    section("TEST 8: Silicon Conductivity (CRC Handbook)")

    si = get_material("silicon")
    check("k_Si (W/m·K)", 148.0, si.thermal_conductivity, tol_pct=1.0)


# ======================================================================
# TEST 9: Copper conductivity
# ======================================================================
def test_copper_conductivity():
    """
    Copper thermal conductivity at 300 K.

    Reference: CRC Handbook of Chemistry and Physics, 97th ed.
    k_Cu(300 K) = 401 W/(m·K)
    """
    section("TEST 9: Copper Conductivity (CRC Handbook)")

    cu = get_material("copper")
    check("k_Cu (W/m·K)", 401.0, cu.thermal_conductivity, tol_pct=1.0)


# ======================================================================
# TEST 10: Landauer limit at 300 K
# ======================================================================
def test_landauer_limit():
    """
    Landauer erasure energy at 300 K.

    Reference: Landauer (1961), E_min = k_B × T × ln(2)
    k_B = 1.380649e-23 J/K (CODATA 2018, exact)
    E = 1.380649e-23 × 300 × ln(2) = 2.8696e-21 J
    """
    section("TEST 10: Landauer Limit at 300 K (Landauer 1961)")

    from aethermor.physics.constants import landauer_limit, k_B
    E_expected = k_B * 300.0 * math.log(2)
    E_model = landauer_limit(300.0)
    check("E_Landauer (J)", E_expected, E_model, tol_pct=0.001)


# ======================================================================
# TEST 11: Effective h round-trip consistency
# ======================================================================
def test_effective_h_roundtrip():
    """
    effective_h should give identical T_j when used as a single h_conv.

    Build a complex stack, get h_eff, then build a bare-die model with
    that h_eff — T_j must match.
    """
    section("TEST 11: Effective h Round-Trip Consistency")

    A = 200e-6
    power = 100.0

    stack = CoolingStack.desktop_air()
    h_eff = stack.effective_h(A)
    R_stack = stack.total_resistance(A)
    T_j_stack = 300.0 + power * R_stack

    R_single = 1.0 / (h_eff * A)
    T_j_single = 300.0 + power * R_single
    check("h_eff round-trip T_j (K)", T_j_stack, T_j_single, tol_abs=0.001)


# ======================================================================

def main():
    print("\nAethermor Independent Textbook Validation")
    print("=" * 70)
    print("  Every expected value below is hand-calculable from the")
    print("  cited textbook or standard reference.  No trust in the")
    print("  developer is required — verify with a calculator.")
    print()

    test_plane_wall()
    test_composite_wall()
    test_silicon_die_resistance()
    test_yovanovich_spreading()
    test_convection_resistance()
    test_hand_calculable_package()
    test_package_with_spreading()
    test_silicon_conductivity()
    test_copper_conductivity()
    test_landauer_limit()
    test_effective_h_roundtrip()

    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {_pass} passed, {_fail} failed")
    print(f"{'=' * 70}")
    if _fail == 0:
        print("  All checks pass against independently verifiable references.")
    else:
        print(f"  {_fail} check(s) FAILED — see details above.")
    return _fail == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
