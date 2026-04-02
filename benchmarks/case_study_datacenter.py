#!/usr/bin/env python3
"""
Case Study: Data-Center Cooling Strategy
==========================================

An engineering team is designing a next-generation GPU compute rack:
  - 8 × accelerators per node, each 600 W TDP, 800 mm² die (4 nm Si)
  - Total node power: 4800 W
  - Target T_j < 85 °C (358 K) for reliability

Questions this case study answers:
  1. What cooling is needed for silicon at 600 W on 800 mm²?
  2. Does switching to SiC substrate reduce cooling requirements enough
     to justify the cost?
  3. What is the maximum die power before thermal runaway at each
     cooling level?
  4. If we add a diamond heat spreader, how much power headroom do we gain?

This case study demonstrates Aethermor's ability to make concrete,
concrete engineering recommendations from thermal physics.
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from aethermor.physics.materials import get_material
from aethermor.physics.thermal import FourierThermalTransport, ThermalBoundaryCondition
from aethermor.physics.cooling import CoolingStack
from aethermor.analysis.thermal_optimizer import ThermalOptimizer

_pass = 0
_fail = 0


def sep(title):
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}\n")


def check(desc, value, lo, hi, unit=""):
    global _pass, _fail
    ok = lo <= value <= hi
    tag = "PASS" if ok else "FAIL"
    if ok:
        _pass += 1
    else:
        _fail += 1
    u = f" {unit}" if unit else ""
    print(f"  [{tag}]  {desc}")
    print(f"         Got: {value:.4g}{u}")
    print(f"         Expected: [{lo:.4g}, {hi:.4g}]{u}")
    return ok


def part1_cooling_requirements():
    """What cooling does silicon need at 600 W / 800 mm²?"""
    sep("PART 1: Cooling Requirements for 600W Silicon Accelerator")

    si = get_material("silicon")
    die_area = 800e-6    # 800 mm²
    ihs_area = 5000e-6   # OAM contact ~50×100 mm
    T_amb = 300.0
    T_j_max = 358.0      # 85 °C target
    TDP = 600.0
    k_cu = 400.0

    # Thermal resistance budget: T_j_max = T_amb + TDP × θ_ja
    theta_ja_budget = (T_j_max - T_amb) / TDP
    print(f"  Thermal resistance budget: θ_ja ≤ {theta_ja_budget:.4f} K/W")
    print(f"  (for T_j < {T_j_max:.0f} K at {TDP:.0f} W)")

    # Conductive path (die + TIM + IHS)
    t_die = 200e-6
    t_tim = 25e-6
    k_tim = 50.0  # indium TIM
    t_ihs = 3e-3
    R_die = t_die / (si.thermal_conductivity * die_area)
    R_tim = t_tim / (k_tim * die_area)
    R_ihs = t_ihs / (k_cu * ihs_area)
    a_die = np.sqrt(die_area / np.pi)
    R_sp = 1.0 / (4.0 * k_cu * a_die)
    theta_jc = R_die + R_tim + R_ihs + R_sp

    # Required convective resistance
    theta_conv_needed = theta_ja_budget - theta_jc
    h_needed = 1.0 / (theta_conv_needed * ihs_area)

    print(f"  θ_jc (conductive): {theta_jc:.4f} K/W")
    print(f"  θ_conv budget:     {theta_conv_needed:.4f} K/W")
    print(f"  Required h_conv:   {h_needed:.0f} W/(m²·K)")
    print()

    check(
        "θ_ja budget is tight (< 0.15 K/W)",
        theta_ja_budget, 0.05, 0.15, "K/W",
    )

    check(
        "Required h_conv is in liquid-cooling range (> 3000)",
        h_needed, 3000, 50000, "W/(m²·K)",
    )

    # At standard server air (h=3000):
    R_conv_air = 1.0 / (3000 * ihs_area)
    T_j_air = T_amb + TDP * (theta_jc + R_conv_air)
    print(f"  At server air (h=3000): T_j = {T_j_air:.1f} K ({T_j_air - 273.15:.1f} °C)")

    # At direct liquid (h=20000):
    R_conv_dlc = 1.0 / (20000 * ihs_area)
    T_j_dlc = T_amb + TDP * (theta_jc + R_conv_dlc)
    print(f"  At direct liquid (h=20000): T_j = {T_j_dlc:.1f} K ({T_j_dlc - 273.15:.1f} °C)")

    verdict_air = "EXCEEDS SPEC" if T_j_air > T_j_max else "WITHIN SPEC"
    verdict_dlc = "EXCEEDS SPEC" if T_j_dlc > T_j_max else "WITHIN SPEC"
    print(f"\n  ➜ Server air: {verdict_air}")
    print(f"  ➜ Direct liquid: {verdict_dlc}")

    check(
        "Server air cooling insufficient for 600W Si",
        T_j_air, T_j_max, 500, "K",
    )
    check(
        "Direct liquid cooling keeps T_j within spec",
        T_j_dlc, T_amb, T_j_max, "K",
    )

    return theta_jc, h_needed


def part2_sic_substrate():
    """Does SiC substrate reduce cooling requirements?"""
    sep("PART 2: SiC Substrate — Worth the Cost?")

    sic = get_material("silicon_carbide")
    die_area = 800e-6
    ihs_area = 5000e-6
    T_amb = 300.0
    T_j_max = 358.0
    TDP = 600.0
    k_cu = 400.0

    t_die = 200e-6
    t_tim = 25e-6
    k_tim = 50.0
    t_ihs = 3e-3

    # SiC die conduction
    R_die_sic = t_die / (sic.thermal_conductivity * die_area)
    R_tim = t_tim / (k_tim * die_area)
    R_ihs = t_ihs / (k_cu * ihs_area)
    a_die = np.sqrt(die_area / np.pi)
    R_sp = 1.0 / (4.0 * k_cu * a_die)
    theta_jc_sic = R_die_sic + R_tim + R_ihs + R_sp

    # Si for comparison
    si = get_material("silicon")
    R_die_si = t_die / (si.thermal_conductivity * die_area)
    theta_jc_si = R_die_si + R_tim + R_ihs + R_sp

    reduction_pct = (1 - theta_jc_sic / theta_jc_si) * 100
    print(f"  θ_jc Silicon:  {theta_jc_si:.4f} K/W")
    print(f"  θ_jc SiC:      {theta_jc_sic:.4f} K/W")
    print(f"  Reduction:     {reduction_pct:.1f}%")

    # Required h for SiC
    theta_ja_budget = (T_j_max - T_amb) / TDP
    theta_conv_sic = theta_ja_budget - theta_jc_sic
    h_sic = 1.0 / (theta_conv_sic * ihs_area)

    theta_conv_si = theta_ja_budget - theta_jc_si
    h_si = 1.0 / (theta_conv_si * ihs_area)

    print(f"\n  Required h_conv for T_j < 85°C:")
    print(f"    Silicon: {h_si:.0f} W/(m²·K)")
    print(f"    SiC:     {h_sic:.0f} W/(m²·K)")
    print(f"    Saving:  {(1 - h_sic / h_si) * 100:.1f}% less aggressive cooling")

    check(
        "SiC reduces θ_jc vs silicon",
        theta_jc_sic, 0.001, theta_jc_si * 0.99, "K/W",
    )
    check(
        "SiC requires less cooling (lower h_conv)",
        h_sic, 100, h_si * 0.99, "W/(m²·K)",
    )

    # At server air (h=3000) with SiC
    R_conv_air = 1.0 / (3000 * ihs_area)
    T_j_sic_air = T_amb + TDP * (theta_jc_sic + R_conv_air)
    T_j_si_air = T_amb + TDP * (theta_jc_si + R_conv_air)
    delta = T_j_si_air - T_j_sic_air
    print(f"\n  At server air (h=3000):")
    print(f"    T_j Silicon: {T_j_si_air:.1f} K")
    print(f"    T_j SiC:     {T_j_sic_air:.1f} K")
    print(f"    SiC saves:   {delta:.1f} K")

    print(f"\n  ➜ DECISION: SiC saves {delta:.0f} K at same cooling.")
    print(f"     At 600W with server air, SiC alone does NOT eliminate")
    print(f"     the need for liquid cooling but reduces thermal stress.")

    check(
        "SiC lowers T_j at same cooling",
        delta, 0.1, 50.0, "K",
    )


def part3_max_power_budget():
    """What is the power ceiling at each cooling level?"""
    sep("PART 3: Maximum Power per Accelerator at Each Cooling Level")

    si = get_material("silicon")
    die_area = 800e-6
    ihs_area = 5000e-6
    T_amb = 300.0
    T_j_max = 358.0
    k_cu = 400.0

    t_die = 200e-6
    t_tim = 25e-6
    k_tim = 50.0
    t_ihs = 3e-3

    R_die = t_die / (si.thermal_conductivity * die_area)
    R_tim = t_tim / (k_tim * die_area)
    R_ihs = t_ihs / (k_cu * ihs_area)
    a_die = np.sqrt(die_area / np.pi)
    R_sp = 1.0 / (4.0 * k_cu * a_die)
    theta_jc = R_die + R_tim + R_ihs + R_sp

    cooling_scenarios = [
        ("Server air (h=3000)", 3000),
        ("Enhanced air (h=5000)", 5000),
        ("AIO liquid (h=10000)", 10000),
        ("Direct liquid (h=20000)", 20000),
        ("Immersion (h=50000)", 50000),
    ]

    print(f"  Die: 800 mm² Silicon, θ_jc = {theta_jc:.4f} K/W")
    print(f"  Target: T_j < {T_j_max:.0f} K ({T_j_max - 273.15:.0f} °C)")
    print(f"  Contact area: 5000 mm²")
    print()

    max_powers = []
    for label, h in cooling_scenarios:
        R_conv = 1.0 / (h * ihs_area)
        theta_total = theta_jc + R_conv
        P_max = (T_j_max - T_amb) / theta_total
        max_powers.append(P_max)
        marker = " ← current target" if abs(P_max - 600) < 200 else ""
        print(f"  {label:30s}  P_max = {P_max:.0f} W{marker}")

    print()

    check(
        "Server air max power < 600W (confirms liquid needed)",
        max_powers[0], 50, 599, "W",
    )
    check(
        "Direct liquid max power > 600W (confirms it works)",
        max_powers[3], 601, 5000, "W",
    )
    check(
        "Immersion yields highest power budget",
        max_powers[4], max_powers[3], 10000, "W",
    )

    # Power headroom at direct liquid
    headroom = max_powers[3] - 600
    headroom_pct = headroom / 600 * 100
    print(f"\n  ➜ At direct liquid cooling: {headroom:.0f} W headroom ({headroom_pct:.0f}% above 600W target)")

    check(
        "Direct liquid gives > 10% headroom above 600W",
        headroom_pct, 10, 500, "%",
    )


def part4_diamond_spreader():
    """Does adding a diamond spreader change the picture?"""
    sep("PART 4: Diamond Heat Spreader — How Much Headroom?")

    si = get_material("silicon")
    diamond = get_material("diamond")
    die_area = 800e-6
    ihs_area = 5000e-6
    T_amb = 300.0
    T_j_max = 358.0
    k_cu = 400.0

    t_die = 200e-6
    t_tim = 25e-6
    k_tim = 50.0
    t_ihs = 3e-3
    t_diamond = 0.5e-3  # 0.5 mm diamond spreader

    # Without diamond
    R_die = t_die / (si.thermal_conductivity * die_area)
    R_tim = t_tim / (k_tim * die_area)
    R_ihs = t_ihs / (k_cu * ihs_area)
    a_die = np.sqrt(die_area / np.pi)
    R_sp = 1.0 / (4.0 * k_cu * a_die)
    theta_jc_std = R_die + R_tim + R_ihs + R_sp

    # With diamond spreader (replace Cu IHS with diamond then Cu)
    R_diamond = t_diamond / (diamond.thermal_conductivity * die_area)
    # Diamond spreader is larger than die, reduces spreading R
    a_diamond = np.sqrt(2 * die_area / np.pi)  # spreader ~2× die area
    R_sp_diamond = 1.0 / (4.0 * diamond.thermal_conductivity * a_diamond)
    theta_jc_diamond = R_die + R_tim + R_diamond + R_sp_diamond + R_ihs

    print(f"  θ_jc standard (Cu IHS):     {theta_jc_std:.4f} K/W")
    print(f"  θ_jc with diamond spreader: {theta_jc_diamond:.4f} K/W")
    reduction = (1 - theta_jc_diamond / theta_jc_std) * 100
    print(f"  θ_jc reduction: {reduction:.1f}%")

    # Max power comparison at direct liquid (h=20000)
    h = 20000
    R_conv = 1.0 / (h * ihs_area)
    P_max_std = (T_j_max - T_amb) / (theta_jc_std + R_conv)
    P_max_dia = (T_j_max - T_amb) / (theta_jc_diamond + R_conv)
    extra_W = P_max_dia - P_max_std
    extra_pct = extra_W / P_max_std * 100

    print(f"\n  At direct liquid (h=20000):")
    print(f"    P_max standard:     {P_max_std:.0f} W")
    print(f"    P_max with diamond: {P_max_dia:.0f} W")
    print(f"    Extra power:        +{extra_W:.0f} W (+{extra_pct:.0f}%)")

    check(
        "Diamond spreader reduces θ_jc",
        theta_jc_diamond, 0.001, theta_jc_std * 0.99, "K/W",
    )
    check(
        "Diamond spreader increases max power",
        P_max_dia, P_max_std * 1.01, 10000, "W",
    )

    # Cost-benefit analysis
    print(f"\n  ➜ DECISION SUMMARY:")
    print(f"     Diamond spreader adds {extra_W:.0f} W headroom per GPU.")
    print(f"     For 8 GPUs per node: {8 * extra_W:.0f} W extra across the node.")
    if extra_pct > 5:
        print(f"     The {extra_pct:.0f}% power increase is meaningful for HPC workloads.")
    else:
        print(f"     The {extra_pct:.0f}% gain is marginal — may not justify diamond cost.")


def main():
    global _pass, _fail

    print("Aethermor Case Study: Data-Center Cooling Strategy")
    print("=" * 72)
    print()
    print("Scenario: 8× GPU compute node, 600W per accelerator, 800 mm² die")
    print("Target: T_j < 85 °C (358 K) for 5-year reliability")
    print()

    part1_cooling_requirements()
    part2_sic_substrate()
    part3_max_power_budget()
    part4_diamond_spreader()

    sep(f"RESULTS: {_pass} passed, {_fail} failed")

    if _fail == 0:
        print("  All checks passed.")
        print()
        print("  KEY ENGINEERING CONCLUSIONS:")
        print("  1. Silicon at 600W/800mm² REQUIRES liquid cooling (server air insufficient)")
        print("  2. SiC substrate reduces θ_jc but does not eliminate liquid cooling need")
        print("  3. Direct liquid cooling provides adequate headroom for 600W operation")
        print("  4. Diamond heat spreader adds meaningful power headroom for future upgrades")
        print()
        print("  These conclusions are quantitative: an engineer")
        print("  using Aethermor can determine cooling requirements, evaluate substrate")
        print("  alternatives, and size thermal solutions before committing to hardware.")

    return _fail == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
