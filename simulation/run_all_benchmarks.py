# run_all_benchmarks.py

import subprocess
import sys
import os

MODULES = [
    "simulation.benchmark_morphogenesis",
    "simulation.benchmark_thermodynamic_core",
    "simulation.benchmark_material_twin",
    "simulation.benchmark_metabolic_cluster",
]

def main():
    env = os.environ.copy()
    env.setdefault("BENCH_ARTIFACT_ROOT", os.getenv("BENCH_ARTIFACT_ROOT", "artifacts"))
    art_root = env["BENCH_ARTIFACT_ROOT"]
    for m in MODULES:
        print(f"\n=== Running {m} ===")
        subprocess.run([sys.executable, "-m", m], check=True, env=env)
    print(f"\nAll novelty benchmarks completed. KPI JSON files are in ./{art_root}/")

if __name__ == "__main__":
    main()
