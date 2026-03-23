# experiments/exp_scaling.py
"""
Scaling: run novelty benches at multiple grid sizes and record KPIs.

Writes:
  artifacts/_report/scaling.csv
"""

import os
import json
import subprocess
import sys
import pandas as pd

ART_ROOT = os.getenv("BENCH_ARTIFACT_ROOT", "artifacts")
REPORT_DIR = os.path.join(ART_ROOT, "_report")
os.makedirs(REPORT_DIR, exist_ok=True)

def run(module, env):
    p = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(
            f"{module} failed (exit={p.returncode})\n"
            f"STDOUT:\n{(p.stdout or '').strip()}\n"
            f"STDERR:\n{(p.stderr or '').strip()}"
        )
    return p.returncode

def read_kpis(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        return json.load(f)

def main():
    sizes = [24, 32, 40, 48]  # bump to [24..80] for a paper
    rows = []

    for s in sizes:
        env = os.environ.copy()
        env["BENCH_GRID"] = str(s)      # your benchmark scripts should read this
        env["BENCH_STEPS"] = "80"
        env["BENCH_ARTIFACT_ROOT"] = ART_ROOT

        run("simulation.benchmark_morphogenesis", env)
        km = read_kpis(os.path.join(ART_ROOT, "morphogenesis", "kpis.json")) or {}

        run("simulation.benchmark_material_twin", env)
        kt = read_kpis(os.path.join(ART_ROOT, "material_twin", "kpis.json")) or {}

        run("simulation.benchmark_metabolic_cluster", env)
        kc = read_kpis(os.path.join(ART_ROOT, "metabolic_cluster", "kpis.json")) or {}

        rows.append({
            "grid": s,
            "morph_uptime_gain_pct": km.get("uptime_gain_pct"),
            "twin_roi_recovery_gain_pct": kt.get("roi_recovery_gain_pct"),
            "cluster_peak_temp_reduction_C": kc.get("peak_temp_reduction_C"),
            "cluster_local_energy_gain_pct": kc.get("local_energy_gain_pct"),
        })

    out = os.path.join(REPORT_DIR, "scaling.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print("Scaling complete:", out)

if __name__ == "__main__":
    main()
