#!/usr/bin/env python3
"""
Uncertainty Propagation Analysis
================================

Demonstrates Monte Carlo uncertainty propagation for Aethermor's thermal
model, showing uncertainty bands on junction temperature predictions.

Instead of a single point estimate ("84°C"), produces "84°C ± X°C under
these assumption ranges."

Covers sensitivity to:
  - h_conv (convection coefficient)
  - die_thickness
  - thermal conductivity (k)
  - contact/interface resistance
  - die area (package tolerance)

Usage:
    python benchmarks/uncertainty_propagation.py
    python benchmarks/uncertainty_propagation.py --json results.json
    python benchmarks/uncertainty_propagation.py --samples 10000
"""
import sys
import os
import json
import argparse
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from aethermor.physics.materials import get_material
from aethermor.physics.cooling import PackageStack, ThermalLayer


def monte_carlo_Tj(base_params: dict, uncertainties: dict,
                   N: int = 5000, seed: int = 42) -> dict:
    """
    Run Monte Carlo uncertainty propagation on junction temperature.

    Parameters
    ----------
    base_params : dict
        Nominal values: die_area_m2, die_thickness_m, die_k, tim_thickness_m,
        tim_k, ihs_thickness_m, ihs_k, contact_die_tim, contact_tim_ihs,
        h_ambient, T_ambient, power_W.
    uncertainties : dict
        Relative uncertainties (fraction, e.g. 0.10 = ±10%) for each param.
    N : int
        Number of Monte Carlo samples.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict with nominal_Tj, mean_Tj, std_Tj, p5, p25, p50, p75, p95,
    samples array, sensitivity ranking.
    """
    rng = np.random.default_rng(seed)
    bp = base_params

    # Sample all parameters simultaneously
    samples = {}
    for key in uncertainties:
        base_val = bp[key]
        rel_unc = uncertainties[key]
        # Log-normal for strictly positive quantities
        sigma = rel_unc
        samples[key] = base_val * np.exp(rng.normal(0, sigma, N))

    # Fill in non-varied parameters
    for key in bp:
        if key not in samples:
            samples[key] = np.full(N, bp[key])

    # Compute T_j for each sample
    Tj_samples = np.zeros(N)
    for i in range(N):
        pkg = PackageStack(
            die_thickness_m=samples["die_thickness_m"][i],
            die_conductivity=samples["die_k"][i],
            tim=ThermalLayer("TIM", samples["tim_thickness_m"][i],
                             samples["tim_k"][i]),
            ihs=ThermalLayer("IHS", samples["ihs_thickness_m"][i],
                             samples["ihs_k"][i]) if bp.get("ihs_thickness_m", 0) > 0 else None,
            contact_die_tim=samples["contact_die_tim"][i],
            contact_tim_ihs=samples["contact_tim_ihs"][i],
            h_ambient=samples["h_ambient"][i],
            T_ambient=bp["T_ambient"],
        )
        Tj_samples[i] = pkg.junction_temperature(
            samples["die_area_m2"][i], samples["power_W"][i]
        )

    # Nominal (base case)
    pkg_nom = PackageStack(
        die_thickness_m=bp["die_thickness_m"],
        die_conductivity=bp["die_k"],
        tim=ThermalLayer("TIM", bp["tim_thickness_m"], bp["tim_k"]),
        ihs=ThermalLayer("IHS", bp["ihs_thickness_m"],
                         bp["ihs_k"]) if bp.get("ihs_thickness_m", 0) > 0 else None,
        contact_die_tim=bp["contact_die_tim"],
        contact_tim_ihs=bp["contact_tim_ihs"],
        h_ambient=bp["h_ambient"],
        T_ambient=bp["T_ambient"],
    )
    Tj_nominal = pkg_nom.junction_temperature(bp["die_area_m2"], bp["power_W"])

    # One-at-a-time sensitivity
    sensitivities = {}
    for key in uncertainties:
        perturbed_up = dict(bp)
        perturbed_up[key] = bp[key] * (1 + uncertainties[key])
        perturbed_dn = dict(bp)
        perturbed_dn[key] = bp[key] * (1 - uncertainties[key])

        # Compute T_j for each perturbation
        Tj_up = _compute_Tj(perturbed_up)
        Tj_dn = _compute_Tj(perturbed_dn)
        dTj = abs(Tj_up - Tj_dn) / 2
        sensitivities[key] = {
            "perturbation": f"±{uncertainties[key]*100:.0f}%",
            "Tj_minus": round(Tj_dn - 273.15, 1),
            "Tj_nominal": round(Tj_nominal - 273.15, 1),
            "Tj_plus": round(Tj_up - 273.15, 1),
            "delta_Tj_K": round(dTj, 1),
            "sensitivity": "High" if dTj > 5 else ("Medium" if dTj > 1 else "Low"),
        }

    return {
        "nominal_Tj_K": round(Tj_nominal, 1),
        "nominal_Tj_C": round(Tj_nominal - 273.15, 1),
        "mean_Tj_K": round(float(np.mean(Tj_samples)), 1),
        "std_Tj_K": round(float(np.std(Tj_samples)), 1),
        "p5_K": round(float(np.percentile(Tj_samples, 5)), 1),
        "p25_K": round(float(np.percentile(Tj_samples, 25)), 1),
        "p50_K": round(float(np.percentile(Tj_samples, 50)), 1),
        "p75_K": round(float(np.percentile(Tj_samples, 75)), 1),
        "p95_K": round(float(np.percentile(Tj_samples, 95)), 1),
        "N_samples": N,
        "seed": 42,
        "sensitivities": sensitivities,
    }


def _compute_Tj(params: dict) -> float:
    """Helper: compute T_j from a param dict."""
    pkg = PackageStack(
        die_thickness_m=params["die_thickness_m"],
        die_conductivity=params["die_k"],
        tim=ThermalLayer("TIM", params["tim_thickness_m"], params["tim_k"]),
        ihs=ThermalLayer("IHS", params["ihs_thickness_m"],
                         params["ihs_k"]) if params.get("ihs_thickness_m", 0) > 0 else None,
        contact_die_tim=params["contact_die_tim"],
        contact_tim_ihs=params["contact_tim_ihs"],
        h_ambient=params["h_ambient"],
        T_ambient=params["T_ambient"],
    )
    return pkg.junction_temperature(params["die_area_m2"], params["power_W"])


def main():
    parser = argparse.ArgumentParser(
        description="Aethermor uncertainty propagation analysis")
    parser.add_argument("--json", metavar="FILE", help="Write JSON output")
    parser.add_argument("--samples", type=int, default=5000,
                        help="Number of MC samples (default: 5000)")
    args = parser.parse_args()

    print("\nAethermor Uncertainty Propagation Analysis")
    print("=" * 60)

    # ── Case: Intel i9-13900K with PackageStack ──
    base_params = {
        "die_area_m2": 257e-6,
        "die_thickness_m": 775e-6,
        "die_k": 148.0,
        "tim_thickness_m": 50e-6,
        "tim_k": 38.0,
        "ihs_thickness_m": 2.0e-3,
        "ihs_k": 380.0,
        "contact_die_tim": 2.0e-6,
        "contact_tim_ihs": 5.0e-6,
        "h_ambient": 8000.0,     # effective at die-area ref for tower cooler
        "T_ambient": 300.0,
        "power_W": 253.0,
    }

    uncertainties = {
        "h_ambient":        0.25,   # ±25% — dominant source
        "die_thickness_m":  0.05,   # ±5%
        "die_k":            0.05,   # ±5%
        "tim_thickness_m":  0.20,   # ±20% (BLT variation)
        "tim_k":            0.15,   # ±15% (solder quality)
        "contact_die_tim":  0.30,   # ±30% (interface quality)
        "contact_tim_ihs":  0.30,   # ±30%
        "die_area_m2":      0.02,   # ±2% (lithography)
        "power_W":          0.10,   # ±10% (workload variation)
    }

    print(f"\n  Case: Intel i9-13900K (253 W MTP, tower cooler)")
    print(f"  Monte Carlo samples: {args.samples}")
    print(f"  Seed: 42 (deterministic)")

    result = monte_carlo_Tj(base_params, uncertainties, N=args.samples)

    print(f"\n  Junction Temperature:")
    print(f"    Nominal:    {result['nominal_Tj_C']:.1f}°C")
    print(f"    Mean:       {result['mean_Tj_K'] - 273.15:.1f}°C")
    print(f"    Std dev:    ±{result['std_Tj_K']:.1f} K")
    print(f"    90% CI:     [{result['p5_K'] - 273.15:.1f}, "
          f"{result['p95_K'] - 273.15:.1f}]°C")
    print(f"    IQR:        [{result['p25_K'] - 273.15:.1f}, "
          f"{result['p75_K'] - 273.15:.1f}]°C")

    print(f"\n  One-at-a-Time Sensitivity:")
    print(f"    {'Parameter':<25s} {'Perturb':>8s}  {'T_j−':>6s}  "
          f"{'Nominal':>7s}  {'T_j+':>6s}  {'ΔT_j':>5s}  Rank")
    print(f"    {'─'*25} {'─'*8}  {'─'*6}  {'─'*7}  {'─'*6}  {'─'*5}  ────")
    for key, s in sorted(result["sensitivities"].items(),
                         key=lambda x: -x[1]["delta_Tj_K"]):
        print(f"    {key:<25s} {s['perturbation']:>8s}  "
              f"{s['Tj_minus']:>5.1f}°  {s['Tj_nominal']:>6.1f}°  "
              f"{s['Tj_plus']:>5.1f}°  {s['delta_Tj_K']:>4.1f}K  "
              f"{s['sensitivity']}")

    print(f"\n  Result: T_j = {result['nominal_Tj_C']:.1f}°C "
          f"± {result['std_Tj_K']:.1f}°C (1σ) "
          f"[{result['p5_K'] - 273.15:.1f}–{result['p95_K'] - 273.15:.1f}°C, 90% CI]")

    if args.json:
        out = {
            "tool": "aethermor",
            "analysis": "uncertainty_propagation",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "case": "i9-13900K (253 W, tower cooler, PackageStack)",
            "base_params": {k: v for k, v in base_params.items()},
            "uncertainties": uncertainties,
            "result": result,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\n  Results written to {args.json}")


if __name__ == "__main__":
    main()
