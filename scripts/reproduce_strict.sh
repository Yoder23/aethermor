#!/usr/bin/env bash
set -euo pipefail

export BENCH_ARTIFACT_ROOT="${BENCH_ARTIFACT_ROOT:-artifacts_pub_strict}"
export BENCH_STEPS="${BENCH_STEPS:-80}"
export ABLATION_N="${ABLATION_N:-20}"
export ABLATION_BASE_SEED="${ABLATION_BASE_SEED:-9000}"
export PUB_MIN_PAIRS="${PUB_MIN_PAIRS:-20}"
export RUN_PUBLICATION_ROBUSTNESS="${RUN_PUBLICATION_ROBUSTNESS:-1}"
export PUB_REQUIRE_ROBUSTNESS="${PUB_REQUIRE_ROBUSTNESS:-1}"
export PUB_MIN_ROBUST_SCENARIOS="${PUB_MIN_ROBUST_SCENARIOS:-3}"
export PUB_SWEEP_N="${PUB_SWEEP_N:-20}"
export PUB_SWEEP_STEPS="${PUB_SWEEP_STEPS:-80}"
export PUB_SWEEP_BASE_SEED="${PUB_SWEEP_BASE_SEED:-13000}"

python run_all_benchmarks.py
python experiments/exp_ablations.py
python publication_gate.py
python experiments/exp_publication_robustness.py
