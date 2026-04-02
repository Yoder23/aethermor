#!/usr/bin/env python3
"""CI smoke test — lightweight check that the installation is functional.

Runs a minimal subset of checks to confirm imports, key computations,
and CLI work.  Exits 0 on success, 1 on failure.

Usage:
    python scripts/ci_smoke_test.py
"""

import subprocess
import sys
import traceback


def _check(label, fn):
    try:
        fn()
        print(f"  [PASS] {label}")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        traceback.print_exc()
        return False


def test_imports():
    import aethermor
    from aethermor.physics.cooling import CoolingStack, PackageStack, ThermalLayer
    from aethermor.physics.materials import get_material
    from aethermor.physics.constants import landauer_limit
    from aethermor.analysis.thermal_optimizer import ThermalOptimizer


def test_material_lookup():
    from aethermor.physics.materials import get_material
    si = get_material("silicon")
    assert si.thermal_conductivity > 100, "Silicon k should be > 100"


def test_cooling_stack():
    from aethermor.physics.cooling import CoolingStack
    stack = CoolingStack.desktop_air()
    R = stack.total_resistance(150e-6)
    assert R > 0, "Resistance must be positive"
    P = stack.max_power_W(150e-6)
    assert P > 0, "Max power must be positive"


def test_package_stack():
    from aethermor.physics.cooling import PackageStack
    pkg = PackageStack.desktop_cpu()
    theta = pkg.theta_jc(257e-6)
    assert 0.01 < theta < 1.0, f"θ_jc = {theta} out of range"


def test_landauer():
    from aethermor.physics.constants import landauer_limit
    E = landauer_limit(300.0)
    assert 2.8e-21 < E < 3.0e-21, f"Landauer limit = {E}"


def test_cli_version():
    proc = subprocess.run(
        [sys.executable, "-m", "aethermor", "version"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, f"CLI version failed: {proc.stderr}"


def main():
    print("Aethermor CI Smoke Test")
    print("=" * 40)

    checks = [
        ("Package imports", test_imports),
        ("Material lookup", test_material_lookup),
        ("CoolingStack basics", test_cooling_stack),
        ("PackageStack basics", test_package_stack),
        ("Landauer limit", test_landauer),
        ("CLI version", test_cli_version),
    ]

    results = [_check(label, fn) for label, fn in checks]
    passed = sum(results)
    total = len(results)

    print("-" * 40)
    print(f"  {passed}/{total} passed")

    if passed < total:
        print("  SMOKE TEST FAILED")
        sys.exit(1)
    else:
        print("  Smoke test passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
