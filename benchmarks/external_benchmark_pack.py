#!/usr/bin/env python3
"""Reproducible external benchmark pack.

Runs Aethermor models against fixed reference cases drawn from published
data and analytical solutions.  Every case has a pinned expected output so
the pack doubles as a regression guard.

Usage:
    python -m benchmarks.external_benchmark_pack          # human-readable
    python -m benchmarks.external_benchmark_pack --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
import platform
from datetime import datetime, timezone

import numpy as np

# ── Aethermor imports ────────────────────────────────────────────────
from aethermor.physics.cooling import CoolingStack, ThermalLayer, PackageStack
from aethermor.physics.materials import get_material


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


# =====================================================================
# Reference cases
# =====================================================================

def _analytical_1d_slab() -> dict:
    """1-D steady conduction through a uniform silicon slab.

    Analytical solution: ΔT = q·L / (k·A)
    q = 100 W, A = 1e-4 m², L = 0.5 mm, k_Si = 148 W/m·K
    """
    si = get_material("silicon")
    k_si = si.thermal_conductivity
    A = 1e-4
    stack = CoolingStack(
        h_ambient=1e6,          # huge h → negligible convection ΔT
        layers=[ThermalLayer("die", 0.5e-3, k_si)],
    )
    R = stack.total_resistance(A)
    delta_model = 100.0 * R
    delta_exact = (100.0 * 0.5e-3) / (k_si * A) + 100.0 / (1e6 * A)
    return {
        "case": "1-D silicon slab (analytical)",
        "reference_source": "Fourier law: ΔT = q·L/(k·A)",
        "reference_value_K": round(delta_exact, 4),
        "model_value_K": round(delta_model, 4),
        "residual_K": round(delta_model - delta_exact, 4),
        "tolerance_K": 0.01,
        "pass": abs(delta_model - delta_exact) < 0.01,
    }


def _analytical_convection() -> dict:
    """Pure convection resistance check.

    R_conv = 1/(h·A).  h = 50 W/m²K, A = 400 mm² = 4e-4 m².
    R = 1/(50 × 4e-4) = 50.0 K/W.  At 10 W → ΔT = 500 K.
    """
    A = 4e-4
    stack = CoolingStack(h_ambient=50.0, layers=[])
    R = stack.total_resistance(A)
    delta_model = 10.0 * R
    delta_exact = 10.0 / (50.0 * A)
    return {
        "case": "Pure convection (analytical)",
        "reference_source": "R = 1/(h·A)",
        "reference_value_K": round(delta_exact, 4),
        "model_value_K": round(delta_model, 4),
        "residual_K": round(delta_model - delta_exact, 4),
        "tolerance_K": 0.01,
        "pass": abs(delta_model - delta_exact) < 0.01,
    }


def _multi_layer_series() -> dict:
    """Three-layer series conduction + convection.

    Layers (referenced to 1e-4 m² area):
      Si  0.5 mm, k=148  → R = 0.5e-3/(148·1e-4) = 0.0338 K/W
      Cu  1.0 mm, k=400  → R = 1.0e-3/(400·1e-4) = 0.025  K/W
      Al  2.0 mm, k=237  → R = 2.0e-3/(237·1e-4) = 0.0844 K/W
      Conv h=100          → R = 1/(100·1e-4)       = 100    K/W
    R_total = 100.1432 K/W.  At 50 W → ΔT = 5007.16 K.
    """
    si = get_material("silicon")
    cu = get_material("copper")
    k_si = si.thermal_conductivity
    k_cu = cu.thermal_conductivity
    k_al = 237.0  # aluminum, W/m·K
    A = 1e-4
    stack = CoolingStack(
        h_ambient=100.0,
        layers=[
            ThermalLayer("die", 0.5e-3, k_si),
            ThermalLayer("copper_spreader", 1.0e-3, k_cu),
            ThermalLayer("aluminum_base", 2.0e-3, k_al),
        ],
    )
    R_total_model = stack.total_resistance(A)
    delta_model = 50.0 * R_total_model

    R_si = 0.5e-3 / (k_si * A)
    R_cu = 1.0e-3 / (k_cu * A)
    R_al = 2.0e-3 / (k_al * A)
    R_conv = 1.0 / (100.0 * A)
    R_total = R_si + R_cu + R_al + R_conv
    delta_exact = 50.0 * R_total

    return {
        "case": "Multi-layer series (analytical)",
        "reference_source": "R_total = ΣL/(k·A) + 1/(h·A)",
        "reference_value_K": round(delta_exact, 4),
        "model_value_K": round(delta_model, 4),
        "residual_K": round(delta_model - delta_exact, 4),
        "tolerance_K": 0.05,
        "pass": abs(delta_model - delta_exact) < 0.05,
    }


def _package_stack_theta_jc() -> dict:
    """PackageStack θ_jc for a desktop CPU config against expected range.

    Published desktop-class θ_jc: 0.02–0.30 K/W (literature survey).
    Model: desktop_cpu() factory → θ_jc should fall in this range.
    Die area for i9-13900K ≈ 257 mm².
    """
    pkg = PackageStack.desktop_cpu()
    die_area = 257e-6  # m²
    theta_jc = pkg.theta_jc(die_area)
    in_range = 0.02 <= theta_jc <= 0.30
    return {
        "case": "PackageStack θ_jc desktop (literature range)",
        "reference_source": "Published θ_jc range for desktop CPUs",
        "reference_range_KW": [0.02, 0.30],
        "model_value_KW": round(theta_jc, 4),
        "pass": in_range,
    }


def _max_power_sanity() -> dict:
    """Max power from CoolingStack should respect T_max correctly.

    At exactly max_power, T_j should equal T_max.
    """
    A = 1e-4
    stack = CoolingStack(
        h_ambient=500.0,
        layers=[ThermalLayer("die", 0.5e-3, 148.0)],
    )
    P_max = stack.max_power_W(die_area_m2=A, T_junction_max=380.0)
    R = stack.total_resistance(A)
    T_j_at_pmax = stack.T_ambient + P_max * R
    residual = abs(T_j_at_pmax - 380.0)
    return {
        "case": "max_power_W consistency check",
        "reference_source": "T_j(P_max) must equal T_max",
        "reference_value_K": 380.0,
        "model_value_K": round(T_j_at_pmax, 4),
        "residual_K": round(residual, 6),
        "tolerance_K": 1e-6,
        "pass": residual < 1e-6,
    }


def _landauer_limit_check() -> dict:
    """Landauer limit at 300 K = k_B T ln 2 ≈ 2.87e-21 J."""
    from aethermor.physics.constants import landauer_limit
    E = landauer_limit(300.0)
    expected = 1.380649e-23 * 300.0 * np.log(2)
    residual = abs(E - expected)
    return {
        "case": "Landauer limit at 300 K",
        "reference_source": "k_B T ln 2 (NIST 2018 SI)",
        "reference_value_J": float(f"{expected:.6e}"),
        "model_value_J": float(f"{E:.6e}"),
        "residual_J": float(f"{residual:.2e}"),
        "tolerance_J": 1e-30,
        "pass": residual < 1e-30,
    }


# =====================================================================
# Runner
# =====================================================================

ALL_CASES = [
    _analytical_1d_slab,
    _analytical_convection,
    _multi_layer_series,
    _package_stack_theta_jc,
    _max_power_sanity,
    _landauer_limit_check,
]


def run_all() -> dict:
    results = [fn() for fn in ALL_CASES]
    passed = sum(1 for r in results if r["pass"])
    return {
        "tool": "aethermor",
        "benchmark_pack": "external_benchmark_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "total_cases": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Aethermor external benchmark pack")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = run_all()

    if args.json:
        print(json.dumps(report, indent=2, cls=_NumpyEncoder))
    else:
        print("=" * 60)
        print("Aethermor External Benchmark Pack")
        print("=" * 60)
        for c in report["cases"]:
            status = "PASS" if c["pass"] else "FAIL"
            print(f"  [{status}] {c['case']}")
        print("-" * 60)
        print(f"  {report['passed']}/{report['total_cases']} passed")
        if report["failed"] > 0:
            print(f"  {report['failed']} FAILED")
            sys.exit(1)
        print("  All benchmarks passed.")


if __name__ == "__main__":
    main()
