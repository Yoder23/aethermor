# run_all_benchmarks.py

import subprocess
import sys
import os

SCRIPTS = [
    "benchmark_morphogenesis.py",
    "benchmark_thermodynamic_core.py",
    "benchmark_material_twin.py",
    "benchmark_metabolic_cluster.py",
]

def main():
    env = os.environ.copy()
    env.setdefault("BENCH_ARTIFACT_ROOT", os.getenv("BENCH_ARTIFACT_ROOT", "artifacts"))
    art_root = env["BENCH_ARTIFACT_ROOT"]
    for s in SCRIPTS:
        print(f"\n=== Running {s} ===")
        subprocess.run([sys.executable, s], check=True, env=env)
    print(f"\nAll novelty benchmarks completed. KPI JSON files are in ./{art_root}/")

if __name__ == "__main__":
    main()
