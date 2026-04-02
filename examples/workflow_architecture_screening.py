#!/usr/bin/env python3
"""Workflow 1: Architecture Screening

Sweeps multiple cooling configurations and technology nodes to find the
maximum sustainable compute density for each combination.

Produces a ranked table showing which (node, cooling) pairs offer the
highest density before hitting the thermal wall.

Usage:
    python examples/workflow_architecture_screening.py
    python examples/workflow_architecture_screening.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from aethermor.physics.cooling import CoolingStack
from aethermor.analysis.thermal_optimizer import ThermalOptimizer


def run_screening() -> list[dict]:
    """Screen node × cooling combinations."""
    nodes_nm = [7, 5, 3]
    cooling_configs = {
        "desktop_air": CoolingStack.desktop_air(),
        "server_air": CoolingStack.server_air(),
        "liquid_cooled": CoolingStack.liquid_cooled(),
    }

    die_area_m2 = 200e-6  # 200 mm²

    results = []

    for node in nodes_nm:
        opt = ThermalOptimizer(tech_node_nm=node, frequency_Hz=3e9)
        for cooling_name, stack in cooling_configs.items():
            h_eff = stack.effective_h(die_area_m2)
            result = opt.find_max_density(
                material_key="silicon",
                h_conv=h_eff,
            )

            results.append({
                "node_nm": node,
                "cooling": cooling_name,
                "h_eff_Wm2K": round(h_eff, 1),
                "max_density_gates_per_element": round(result["max_density"], 0),
                "T_max_K": round(result["T_max_K"], 1),
                "power_W": round(result.get("power_W", 0), 1),
            })

    # Sort by density descending
    results.sort(key=lambda r: r["max_density_gates_per_element"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Architecture screening workflow")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = run_screening()

    if args.json:
        report = {
            "workflow": "architecture_screening",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }
        print(json.dumps(report, indent=2))
    else:
        print("=" * 80)
        print("Architecture Screening: Max Compute Density by Node × Cooling")
        print("=" * 80)
        print(f"{'Node':>6s}  {'Cooling':<20s}  {'h_eff':>10s}  {'Max Density':>14s}  {'T_max':>8s}  {'Power':>8s}")
        print("-" * 80)
        for r in results:
            print(
                f"{r['node_nm']:>4d}nm  {r['cooling']:<20s}  "
                f"{r['h_eff_Wm2K']:>10.1f}  "
                f"{r['max_density_gates_per_element']:>14,.0f}  "
                f"{r['T_max_K']:>8.1f}  {r['power_W']:>8.1f}"
            )
        print("-" * 80)


if __name__ == "__main__":
    main()
