$ErrorActionPreference = "Stop"

if (-not $env:BENCH_ARTIFACT_ROOT) { $env:BENCH_ARTIFACT_ROOT = "artifacts_pub_strict" }
if (-not $env:BENCH_STEPS) { $env:BENCH_STEPS = "80" }
if (-not $env:ABLATION_N) { $env:ABLATION_N = "20" }
if (-not $env:ABLATION_BASE_SEED) { $env:ABLATION_BASE_SEED = "9000" }
if (-not $env:PUB_MIN_PAIRS) { $env:PUB_MIN_PAIRS = "20" }
if (-not $env:RUN_PUBLICATION_ROBUSTNESS) { $env:RUN_PUBLICATION_ROBUSTNESS = "1" }
if (-not $env:PUB_REQUIRE_ROBUSTNESS) { $env:PUB_REQUIRE_ROBUSTNESS = "1" }
if (-not $env:PUB_MIN_ROBUST_SCENARIOS) { $env:PUB_MIN_ROBUST_SCENARIOS = "3" }
if (-not $env:PUB_SWEEP_N) { $env:PUB_SWEEP_N = "20" }
if (-not $env:PUB_SWEEP_STEPS) { $env:PUB_SWEEP_STEPS = "80" }
if (-not $env:PUB_SWEEP_BASE_SEED) { $env:PUB_SWEEP_BASE_SEED = "13000" }

python run_all_benchmarks.py
python experiments/exp_ablations.py
python publication_gate.py
python experiments/exp_publication_robustness.py
