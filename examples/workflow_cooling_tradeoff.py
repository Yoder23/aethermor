#!/usr/bin/env python3
"""Workflow 2: Cooling Tradeoff Review

Compares cooling solutions for a fixed chip design, showing the cost of
each additional thermal headroom step.

Produces a table of cooling configs ranked by max power, with
diminishing-returns analysis.

Usage:
    python examples/workflow_cooling_tradeoff.py
    python examples/workflow_cooling_tradeoff.py --json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from aethermor.physics.cooling import CoolingStack


def run_tradeoff() -> list[dict]:
    """Compare cooling solutions for a 200 mm² die."""
    die_area_m2 = 200e-6
    T_max = 378.0
    T_amb = 300.0

    configs = [
        ("Bare die, natural air", CoolingStack.bare_die_natural_air()),
        ("Desktop air (paste + IHS + tower)", CoolingStack.desktop_air()),
        ("Server air (solder + IHS + high-CFM)", CoolingStack.server_air()),
        ("Liquid cold plate", CoolingStack.liquid_cooled()),
    ]

    results = []
    prev_pmax = 0.0

    for name, stack in configs:
        R = stack.total_resistance(die_area_m2)
        h_eff = stack.effective_h(die_area_m2)
        P_max = stack.max_power_W(die_area_m2, T_junction_max=T_max)
        gain = P_max - prev_pmax

        results.append({
            "cooling": name,
            "R_total_KW": round(R, 4),
            "h_eff_Wm2K": round(h_eff, 1),
            "P_max_W": round(P_max, 1),
            "marginal_gain_W": round(gain, 1),
        })
        prev_pmax = P_max

    return results


def main():
    parser = argparse.ArgumentParser(description="Cooling tradeoff workflow")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = run_tradeoff()

    if args.json:
        report = {
            "workflow": "cooling_tradeoff",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "die_area_mm2": 200.0,
            "T_max_K": 378.0,
            "results": results,
        }
        print(json.dumps(report, indent=2))
    else:
        print("=" * 85)
        print("Cooling Tradeoff Review: 200 mm² die, T_max = 378 K")
        print("=" * 85)
        print(f"{'Cooling':<40s}  {'R_ja':>8s}  {'h_eff':>8s}  {'P_max':>8s}  {'Gain':>8s}")
        print(f"{'':40s}  {'K/W':>8s}  {'W/m²K':>8s}  {'W':>8s}  {'W':>8s}")
        print("-" * 85)
        for r in results:
            print(
                f"{r['cooling']:<40s}  {r['R_total_KW']:>8.4f}  "
                f"{r['h_eff_Wm2K']:>8.1f}  {r['P_max_W']:>8.1f}  "
                f"{r['marginal_gain_W']:>+8.1f}"
            )
        print("-" * 85)

        # Diminishing returns check
        gains = [r["marginal_gain_W"] for r in results[1:]]
        if len(gains) >= 2 and gains[-1] < gains[0] * 0.1:
            print("\n  NOTE: Diminishing returns detected beyond server air cooling.")
            print("  → Evaluate whether the extra cost of liquid cooling is justified.")
        print()


if __name__ == "__main__":
    main()
