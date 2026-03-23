# experiments/exp_fault_sweeps.py
"""
Fault regime sweeps for morphogenesis/material twin robustness.

Writes:
  artifacts/_report/fault_sweeps.csv
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
    severities = [0.1, 0.2, 0.4]      # multiplier applied during fault
    fault_counts = [1, 2, 4]          # how many fault steps occur

    rows = []
    for sev in severities:
        for fc in fault_counts:
            env = os.environ.copy()
            env["FAULT_SEVERITY"] = str(sev)
            env["FAULT_COUNT"] = str(fc)
            env["MORPHO_ENABLE"] = "1"
            env["BENCH_ARTIFACT_ROOT"] = ART_ROOT

            run("simulation.benchmark_morphogenesis", env)
            km = read_kpis(os.path.join(ART_ROOT, "morphogenesis", "kpis.json")) or {}

            env["TWIN_ENABLE"] = "1"
            run("simulation.benchmark_material_twin", env)
            kt = read_kpis(os.path.join(ART_ROOT, "material_twin", "kpis.json")) or {}

            rows.append({
                "fault_severity": sev,
                "fault_count": fc,
                "morph_uptime_gain_pct": km.get("uptime_gain_pct"),
                "twin_roi_recovery_gain_pct": kt.get("roi_recovery_gain_pct"),
            })

    out = os.path.join(REPORT_DIR, "fault_sweeps.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print("Fault sweeps complete:", out)

if __name__ == "__main__":
    main()
