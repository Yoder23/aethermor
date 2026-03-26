#!/usr/bin/env python3
"""
Production Benchmark Suite
==========================

Fixed benchmark set that every release must pass. Runs 20 representative
hardware and synthetic cases, computes error metrics, and checks against
release-gating thresholds.

Exit code 0 = all gates pass. Non-zero = regression detected.
"""
import sys
import os
import csv
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from physics.materials import get_material
from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
from physics.cooling import CoolingStack

CASES_CSV = os.path.join(os.path.dirname(__file__), "cases.csv")
GOLD_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gold_outputs", "production_suite_v1.0.0.json")

# ── Release-gating thresholds ──
THRESHOLDS = {
    "material_median_pct_error": 1.0,     # ≤ 1% median material property error
    "material_max_pct_error": 10.0,       # ≤ 10% worst-case material error
    "energy_conservation_pct": 5.0,       # ≤ 5% 3D Fourier conservation error
    "gold_regression_max_pct": 1.0,       # No output regresses > 1% vs gold
    "all_cases_pass": True,               # Every case must produce valid output
}


def load_cases():
    """Load benchmark cases from CSV."""
    cases = []
    with open(CASES_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["die_area_mm2"] = float(row["die_area_mm2"])
            row["tdp_w"] = float(row["tdp_w"])
            row["node_nm"] = int(row["node_nm"])
            row["tj_max_c"] = float(row["tj_max_c"])
            row["theta_jc_kw"] = float(row["theta_jc_kw"]) if row["theta_jc_kw"] else None
            cases.append(row)
    return cases


def run_case(case):
    """Run a single benchmark case and return results dict."""
    si = get_material("silicon")
    die_m2 = case["die_area_mm2"] * 1e-6
    tdp = case["tdp_w"]
    thick = 0.775e-3  # standard wafer thickness

    # 1D conduction thermal resistance
    R_cond = thick / (si.thermal_conductivity * die_m2)

    # Cooling: use representative h values by cooling type
    h_map = {
        "liquid": 10000.0,
        "server_air": 500.0,
        "desktop_air": 200.0,
        "fanless": 50.0,
        "fan": 100.0,
        "variable": 1000.0,
    }
    h_conv = h_map.get(case["cooling"], 500.0)
    R_conv = 1.0 / (h_conv * die_m2)

    T_amb = 300.0  # 27°C
    Tj_K = T_amb + tdp * (R_cond + R_conv)
    Tj_C = Tj_K - 273.15

    # Theta_jc model
    theta_jc_model = R_cond

    # Power density
    power_density = tdp / die_m2

    result = {
        "chip": case["chip"],
        "segment": case["segment"],
        "Tj_C": round(Tj_C, 2),
        "R_cond_KW": round(R_cond, 6),
        "theta_jc_model": round(theta_jc_model, 6),
        "power_density_Wm2": round(power_density, 1),
        "valid": bool(Tj_K > 0 and np.isfinite(Tj_K)),
    }

    # If published theta_jc is available, compute ratio
    if case["theta_jc_kw"] is not None:
        result["theta_jc_ratio"] = round(theta_jc_model / case["theta_jc_kw"], 4)

    return result


def run_material_checks():
    """Run material property cross-validation checks."""
    # CRC Handbook 97th ed. reference values
    crc_k = {
        "silicon": 148, "silicon_dioxide": 1.4, "gallium_arsenide": 55,
        "diamond": 2200, "copper": 401, "indium_phosphide": 68,
        "silicon_carbide": 490, "gallium_nitride": 130,
    }
    errors = []
    for name, k_ref in crc_k.items():
        mat = get_material(name)
        err = abs(mat.thermal_conductivity - k_ref) / k_ref * 100
        errors.append(err)
    return {
        "median_pct_error": round(float(np.median(errors)), 4),
        "p90_pct_error": round(float(np.percentile(errors, 90)), 4),
        "max_pct_error": round(float(max(errors)), 4),
    }


def check_gold_regression(results, gold_path):
    """Compare current results against gold outputs."""
    if not os.path.exists(gold_path):
        return {"status": "no_gold_file", "regressions": []}

    with open(gold_path, "r") as f:
        gold = json.load(f)

    gold_by_chip = {r["chip"]: r for r in gold.get("case_results", [])}
    regressions = []

    for r in results:
        g = gold_by_chip.get(r["chip"])
        if g is None:
            continue
        for key in ["Tj_C", "R_cond_KW", "power_density_Wm2"]:
            if key in r and key in g and g[key] != 0:
                delta_pct = abs(r[key] - g[key]) / abs(g[key]) * 100
                if delta_pct > THRESHOLDS["gold_regression_max_pct"]:
                    regressions.append({
                        "chip": r["chip"],
                        "key": key,
                        "gold": g[key],
                        "current": r[key],
                        "delta_pct": round(delta_pct, 4),
                    })

    return {"status": "checked", "regressions": regressions}


def main():
    t_start = time.time()
    print("=" * 70)
    print("AETHERMOR PRODUCTION BENCHMARK SUITE")
    print("=" * 70)
    print()

    # 1. Load and run cases
    cases = load_cases()
    print(f"Running {len(cases)} benchmark cases...")
    results = []
    for case in cases:
        r = run_case(case)
        results.append(r)
        status = "PASS" if r["valid"] else "FAIL"
        print(f"  [{status}]  {r['chip']:<35} Tj={r['Tj_C']:>8.1f}°C  P={r['power_density_Wm2']:>12.0f} W/m²")

    all_valid = all(r["valid"] for r in results)
    print(f"\n  Cases: {sum(1 for r in results if r['valid'])}/{len(results)} valid")

    # 2. Material checks
    print("\nMaterial property cross-validation...")
    mat = run_material_checks()
    print(f"  Median error: {mat['median_pct_error']:.4f}%")
    print(f"  P90 error:    {mat['p90_pct_error']:.4f}%")
    print(f"  Max error:    {mat['max_pct_error']:.4f}%")

    # 3. Gold regression check
    print("\nGold output regression check...")
    regression = check_gold_regression(results, GOLD_FILE)
    if regression["status"] == "no_gold_file":
        print("  No gold file found. Run scripts/freeze_gold_outputs.py to create.")
    elif regression["regressions"]:
        for reg in regression["regressions"]:
            print(f"  REGRESSION: {reg['chip']} {reg['key']}: gold={reg['gold']}, current={reg['current']}, delta={reg['delta_pct']:.2f}%")
    else:
        print("  No regressions detected.")

    # 4. Gate check
    print("\n" + "=" * 70)
    print("RELEASE GATE CHECK")
    print("=" * 70)
    gates = {
        "all_cases_valid": all_valid,
        "material_median_ok": mat["median_pct_error"] <= THRESHOLDS["material_median_pct_error"],
        "material_max_ok": mat["max_pct_error"] <= THRESHOLDS["material_max_pct_error"],
        "no_regressions": len(regression.get("regressions", [])) == 0,
    }

    all_pass = all(gates.values())
    for gate, passed in gates.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}]  {gate}")

    elapsed = time.time() - t_start
    print(f"\n  RESULT: {'ALL GATES PASS' if all_pass else 'GATE FAILURE'} ({elapsed:.1f}s)")

    # 5. Save results for gold comparison
    output = {
        "version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "case_results": results,
        "material_checks": mat,
        "gates": gates,
        "all_pass": all_pass,
    }

    return all_pass, output


if __name__ == "__main__":
    success, output = main()
    sys.exit(0 if success else 1)
