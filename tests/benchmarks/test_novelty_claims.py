import json
import os
import subprocess
import sys
from functools import lru_cache

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART_ROOT = f"artifacts_bench_{os.getpid()}"


def _run(script: str, env_updates=None):
    env = os.environ.copy()
    env.setdefault("BENCH_STEPS", "60")
    env.setdefault("BENCH_GRID", "32")
    env.setdefault("BENCH_ARTIFACT_ROOT", ART_ROOT)
    if env_updates:
        env.update(env_updates)

    p = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, (
        f"Benchmark failed: {script}\n"
        f"STDOUT:\n{(p.stdout or '').strip()}\n"
        f"STDERR:\n{(p.stderr or '').strip()}"
    )


def _load(relpath: str):
    path = os.path.join(ROOT, relpath)
    assert os.path.isfile(path), f"Missing KPI file: {relpath}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _thermo():
    _run("benchmark_thermodynamic_core.py")
    return _load(os.path.join(ART_ROOT, "thermo_core", "kpis.json"))


@lru_cache(maxsize=1)
def _material_pair():
    _run("benchmark_material_twin.py", {"TWIN_ENABLE": "1"})
    on = _load(os.path.join(ART_ROOT, "material_twin", "kpis.json"))
    _run("benchmark_material_twin.py", {"TWIN_ENABLE": "0"})
    off = _load(os.path.join(ART_ROOT, "material_twin", "kpis.json"))
    return on, off


@lru_cache(maxsize=1)
def _morph_pair():
    _run("benchmark_morphogenesis.py", {"MORPHO_ENABLE": "1"})
    on = _load(os.path.join(ART_ROOT, "morphogenesis", "kpis.json"))
    _run("benchmark_morphogenesis.py", {"MORPHO_ENABLE": "0"})
    off = _load(os.path.join(ART_ROOT, "morphogenesis", "kpis.json"))
    return on, off


@lru_cache(maxsize=1)
def _cluster_pair():
    _run("benchmark_metabolic_cluster.py", {"CLUSTER_ENABLE": "1"})
    on = _load(os.path.join(ART_ROOT, "metabolic_cluster", "kpis.json"))
    _run("benchmark_metabolic_cluster.py", {"CLUSTER_ENABLE": "0"})
    off = _load(os.path.join(ART_ROOT, "metabolic_cluster", "kpis.json"))
    return on, off


@pytest.mark.novelty
def test_thermo_core_efficiency_gain():
    k = _thermo()
    assert k["mean_eff_thermo_bits_per_unit"] > 0.0
    assert "bits_per_joule_gain_vs_naive_pct" in k
    assert k["landauer_monotonic_naive"] == 1
    assert k["landauer_monotonic_optimized"] == 1


@pytest.mark.novelty
def test_material_twin_roi_recovery():
    on, off = _material_pair()
    assert on["roi_recovery_gain_pct"] >= off["roi_recovery_gain_pct"]
    assert on["roi_recovery_gain_pct"] > 0.0


@pytest.mark.novelty
def test_morphogenesis_resilience_and_specialization():
    on, off = _morph_pair()
    assert on["uptime_gain_pct"] >= off["uptime_gain_pct"]
    assert on["specialization_gain"] >= 0.0
    assert on["modules_mean_with_morph"] >= 2.0


@pytest.mark.novelty
def test_metabolic_cluster_benefit():
    on, off = _cluster_pair()
    assert on["peak_temp_reduction_C"] >= off["peak_temp_reduction_C"]
    assert on["peak_temp_reduction_C"] > 0.0
    assert on["local_energy_gain_pct"] >= off["local_energy_gain_pct"]
