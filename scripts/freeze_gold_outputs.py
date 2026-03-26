#!/usr/bin/env python3
"""
Freeze gold outputs from the production benchmark suite.

Usage:
  python scripts/freeze_gold_outputs.py              # Generate gold outputs
  python scripts/freeze_gold_outputs.py --verify-only # Check against existing gold
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GOLD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "benchmarks", "gold_outputs")
GOLD_FILE = os.path.join(GOLD_DIR, "production_suite_v1.0.0.json")


def main():
    verify_only = "--verify-only" in sys.argv

    # Import and run the production suite
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "benchmarks", "production_suite"))
    from run_production_suite import main as run_suite

    success, output = run_suite()

    if not success:
        print("\nProduction suite FAILED. Cannot freeze gold outputs.")
        return False

    if verify_only:
        if not os.path.exists(GOLD_FILE):
            print(f"No gold file at {GOLD_FILE}. Run without --verify-only first.")
            return False

        with open(GOLD_FILE, "r") as f:
            gold = json.load(f)

        # Compare
        gold_by_chip = {r["chip"]: r for r in gold.get("case_results", [])}
        current_by_chip = {r["chip"]: r for r in output.get("case_results", [])}

        mismatches = 0
        for chip, current in current_by_chip.items():
            g = gold_by_chip.get(chip)
            if g is None:
                print(f"  NEW CASE: {chip}")
                continue
            for key in ["Tj_C", "R_cond_KW", "power_density_Wm2"]:
                if key in current and key in g:
                    if abs(current[key] - g[key]) > 1e-6:
                        print(f"  MISMATCH: {chip}.{key}: gold={g[key]}, current={current[key]}")
                        mismatches += 1

        if mismatches == 0:
            print("\nGold outputs verified: all match.")
            return True
        else:
            print(f"\n{mismatches} mismatches found.")
            return False

    else:
        os.makedirs(GOLD_DIR, exist_ok=True)
        with open(GOLD_FILE, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nGold outputs frozen to {GOLD_FILE}")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
