#!/usr/bin/env python3
"""Workflow 3: Substrate / Package Ranking

Ranks substrate materials by thermal performance for a fixed cooling
configuration, showing which material allows the highest power density.

Usage:
    python examples/workflow_substrate_ranking.py
    python examples/workflow_substrate_ranking.py --json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from aethermor.physics.cooling import CoolingStack, ThermalLayer
from aethermor.physics.materials import get_material


def run_ranking() -> list[dict]:
    """Rank substrates by max power under identical cooling."""
    die_area_m2 = 150e-6  # 150 mm²
    die_thickness_m = 0.5e-3
    T_max = 378.0

    materials = ["silicon", "silicon_carbide", "diamond", "gallium_nitride"]

    results = []
    for mat_key in materials:
        mat = get_material(mat_key)
        k = mat.thermal_conductivity

        # Build identical cooling stack, only die conductivity changes
        stack = CoolingStack(h_ambient=120.0)  # server forced air
        stack.add_layer(ThermalLayer(f"die ({mat.name})", die_thickness_m, k))
        stack.add_layer(ThermalLayer("solder TIM", 20e-6, 86.0))
        stack.add_layer(ThermalLayer("copper IHS", 2.0e-3, 401.0))
        stack.add_layer(ThermalLayer("copper heatsink", 6.0e-3, 401.0))

        R = stack.total_resistance(die_area_m2)
        P_max = stack.max_power_W(die_area_m2, T_junction_max=T_max)
        R_die = die_thickness_m / (k * die_area_m2)

        results.append({
            "material": mat.name,
            "k_Wm_K": round(k, 1),
            "R_die_KW": round(R_die, 4),
            "R_total_KW": round(R, 4),
            "P_max_W": round(P_max, 1),
            "max_temp_K": mat.max_operating_temp,
        })

    # Sort by P_max descending
    results.sort(key=lambda r: r["P_max_W"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Substrate ranking workflow")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = run_ranking()

    if args.json:
        report = {
            "workflow": "substrate_ranking",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "die_area_mm2": 150.0,
            "cooling": "server_forced_air_h120",
            "results": results,
        }
        print(json.dumps(report, indent=2))
    else:
        print("=" * 80)
        print("Substrate Ranking: Which material allows the highest power?")
        print("  Die: 150 mm², 0.5 mm thick | Cooling: server forced air (h=120)")
        print("=" * 80)
        print(
            f"{'Material':<25s}  {'k':>8s}  {'R_die':>8s}  {'R_total':>8s}  "
            f"{'P_max':>8s}  {'T_max,op':>8s}"
        )
        print(
            f"{'':25s}  {'W/m·K':>8s}  {'K/W':>8s}  {'K/W':>8s}  "
            f"{'W':>8s}  {'K':>8s}"
        )
        print("-" * 80)
        for r in results:
            print(
                f"{r['material']:<25s}  {r['k_Wm_K']:>8.1f}  {r['R_die_KW']:>8.4f}  "
                f"{r['R_total_KW']:>8.4f}  {r['P_max_W']:>8.1f}  "
                f"{r['max_temp_K']:>8.0f}"
            )
        print("-" * 80)

        # Insight
        best = results[0]
        worst = results[-1]
        ratio = best["P_max_W"] / worst["P_max_W"] if worst["P_max_W"] > 0 else float("inf")
        print(f"\n  Best: {best['material']} ({best['P_max_W']:.0f} W)")
        print(f"  Worst: {worst['material']} ({worst['P_max_W']:.0f} W)")
        print(f"  Ratio: {ratio:.2f}×")
        if ratio < 1.1:
            print("  → Substrate material is not the bottleneck; focus on cooling.")
        else:
            print(f"  → {best['material']} offers meaningful thermal advantage.")


if __name__ == "__main__":
    main()
