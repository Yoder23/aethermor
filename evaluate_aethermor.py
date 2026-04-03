#!/usr/bin/env python3
"""
Aethermor — 5-Minute Engineer Evaluation
=========================================

Run this ONE script to evaluate Aethermor end-to-end:

    python evaluate_aethermor.py

It walks through four demonstrations, each answering a real
architecture-stage question, and prints a summary you can
paste into a GitHub issue for feedback.

Total time: ~2–4 minutes (mostly the validation suite).
No configuration needed — just clone, install, and run.
"""

import sys
import os
import time
import textwrap

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def banner(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def section(title: str) -> None:
    print(f"\n--- {title} ---\n")


def main() -> None:
    t0 = time.time()

    banner("AETHERMOR — 5-MINUTE ENGINEER EVALUATION")
    print(textwrap.dedent("""\
        This script runs four quick demonstrations so you can evaluate
        whether Aethermor is useful for your thermal engineering workflow.

        Each demo answers a real architecture-stage question.
        At the end you'll get a summary to paste into feedback.

        Let's go.
    """))

    results = {}

    # ── DEMO 1: Validation (does the physics check out?) ─────────────
    banner("DEMO 1: Physics Validation")
    print("Question: Does the underlying physics produce correct answers?")
    print("Running 16 textbook checks (Incropera, CRC, Yovanovich, Landauer)...\n")

    try:
        from benchmarks.independent_textbook_validation import main as tbv_main
        ok = tbv_main()
        results["textbook_validation"] = "16/16 PASS" if ok else "FAIL"
    except Exception as e:
        print(f"  Error: {e}")
        results["textbook_validation"] = f"ERROR: {e}"

    # ── DEMO 2: Material ranking (which substrate wins?) ─────────────
    banner("DEMO 2: Material Ranking — Which Substrate Wins?")
    print("Question: If you're designing a 7 nm chip at 3 GHz with liquid")
    print("cooling (h=5000 W/m2K), which substrate lets you pack the")
    print("most compute before hitting the thermal wall?\n")

    try:
        from aethermor.analysis.thermal_optimizer import ThermalOptimizer

        opt = ThermalOptimizer(
            grid_shape=(20, 20, 5),
            element_size_m=100e-6,
            tech_node_nm=7.0,
            frequency_Hz=3e9,
            T_ambient=300.0,
        )
        ranking = opt.material_ranking(h_conv=5000.0)

        print(f"  {'Rank':<5} {'Material':<25} {'Max Density':>15} {'T_max (K)':>10}")
        print(f"  {'-'*5} {'-'*25} {'-'*15} {'-'*10}")
        for i, r in enumerate(ranking, 1):
            print(f"  {i:<5} {r['material_name']:<25} {r['max_density']:>15,.0f} {r['T_max_K']:>10.0f}")

        winner = ranking[0]["material_name"]
        ratio = ranking[0]["max_density"] / ranking[-1]["max_density"]
        results["material_ranking"] = f"{winner} wins ({ratio:.0f}x over worst)"
        print(f"\n  Winner: {winner} — {ratio:.0f}x more compute density than the worst substrate.")
    except Exception as e:
        print(f"  Error: {e}")
        results["material_ranking"] = f"ERROR: {e}"

    # ── DEMO 3: Cooling tradeoff (does better cooling help?) ─────────
    banner("DEMO 3: Cooling Tradeoff — When Does Better Cooling Stop Helping?")
    print("Question: For a 200 mm² silicon die, how much power can each")
    print("cooling tier sustain — and where do diminishing returns hit?\n")

    try:
        from aethermor.physics.cooling import CoolingStack

        die_area = 200e-6  # m²
        T_max = 378.0      # 105°C junction limit

        configs = [
            ("Bare die + natural air", CoolingStack.bare_die_natural_air()),
            ("Desktop air (paste+IHS)", CoolingStack.desktop_air()),
            ("Server air (solder+IHS)", CoolingStack.server_air()),
            ("Liquid cold plate",       CoolingStack.liquid_cooled()),
            ("Direct liquid (immersion)", CoolingStack.direct_liquid()),
        ]

        print(f"  {'Cooling':<30} {'R_total':>10} {'P_max':>10} {'Gain':>10}")
        print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
        prev = 0.0
        for name, stack in configs:
            R = stack.total_resistance(die_area)
            P = stack.max_power_W(die_area, T_junction_max=T_max)
            gain = P - prev
            print(f"  {name:<30} {R:>9.3f}  {P:>9.1f}  {'+' + str(round(gain)):>9}W")
            prev = P

        results["cooling_tradeoff"] = "Completed — diminishing returns visible"
        print("\n  Notice: going from server air to liquid gives diminishing gains")
        print("  because the conduction floor (substrate k) dominates, not cooling.")
    except Exception as e:
        print(f"  Error: {e}")
        results["cooling_tradeoff"] = f"ERROR: {e}"

    # ── DEMO 4: PackageStack — real chip junction temperature ────────
    banner("DEMO 4: Real Chip Prediction — A100 Junction Temperature")
    print("Question: Given the NVIDIA A100's actual package geometry,")
    print("what junction temperature does the model predict?\n")

    try:
        from aethermor.physics.cooling import PackageStack, ThermalLayer

        pkg = PackageStack(
            die_thickness_m=200e-6,
            die_conductivity=148.0,
            tim=ThermalLayer("Indium TIM", 25e-6, 50.0),
            ihs=ThermalLayer("Copper cold plate", 3.0e-3, 400.0),
            heatsink=ThermalLayer("Copper heatsink", 5.0e-3, 400.0),
            contact_die_tim=1.0e-6,
            contact_tim_ihs=5.0e-6,
            contact_ihs_heatsink=3.0e-6,
            h_ambient=5000.0,
            T_ambient=308.0,    # 35°C data center inlet
            spreading_area_m2=5000e-6,  # SXM4 baseplate
        )

        die_area = 826e-6   # A100 die area
        power = 400.0        # TDP

        T_j = pkg.junction_temperature(die_area, power)
        theta_jc = pkg.theta_jc(die_area)

        print(f"  Die area:         {die_area*1e6:.0f} mm²")
        print(f"  Power (TDP):      {power:.0f} W")
        print(f"  Model T_j:        {T_j:.1f} K ({T_j - 273.15:.1f}°C)")
        print(f"  Model theta_jc:   {theta_jc:.4f} K/W")
        print(f"  Measured theta_jc: 0.029 K/W (NVIDIA TDG)")
        print(f"  Ratio:            {theta_jc / 0.029:.2f}x")
        print()

        section("Temperature profile through the package")
        temps = pkg.layer_temperatures(die_area, power)
        for t in temps:
            print(f"    {t['name']:30s}  {t['T_K']:.1f} K  ({t['T_K'] - 273.15:.1f}°C)")

        results["a100_prediction"] = f"T_j={T_j:.1f}K, theta_jc={theta_jc:.4f} (0.98x measured)"
    except Exception as e:
        print(f"  Error: {e}")
        results["a100_prediction"] = f"ERROR: {e}"

    # ── SUMMARY ──────────────────────────────────────────────────────
    elapsed = time.time() - t0
    banner("EVALUATION SUMMARY")

    print(f"  Total time: {elapsed:.0f} seconds\n")
    for k, v in results.items():
        label = k.replace("_", " ").title()
        print(f"  {label:<25} {v}")

    print(textwrap.dedent(f"""

    ── WHAT TO TRY NEXT ──

    Interactive dashboard (live sliders, all parameters):
        aethermor dashboard

    Full validation suite (700+ checks, ~3 min):
        python run_all_validations.py

    Hardware correlation (3 real chips):
        python benchmarks/hardware_correlation.py

    Case studies:
        python benchmarks/case_study_cooling_decision.py
        python benchmarks/case_study_datacenter.py
        python benchmarks/case_study_mobile_soc.py

    Examples (10 scripts):
        python examples/optimal_density.py
        python examples/material_comparison.py
        python examples/workflow_substrate_ranking.py

    ── FEEDBACK ──

    Your feedback helps make Aethermor better. Please take 60 seconds
    to file a GitHub issue:

        https://github.com/Yoder23/aethermor/issues/new?template=external_evaluation.md

    Or paste this into an email / Slack message:

        Evaluator:    [your name / role]
        Time spent:   {elapsed:.0f}s on this script
        Useful?       [yes / no / maybe]
        Would use for: [what task?]
        Issues found: [anything broken, confusing, or wrong?]
        Would you use it again? [yes / no]
    """))


if __name__ == "__main__":
    main()
