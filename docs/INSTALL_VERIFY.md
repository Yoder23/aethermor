# Installation and Verification

## Install

### From Release Wheel (Recommended)

```bash
pip install https://github.com/Yoder23/aethermor/releases/download/v1.0.0/aethermor-1.0.0-py3-none-any.whl
```

### From Source

```bash
git clone https://github.com/Yoder23/aethermor.git
cd aethermor
pip install -e .
```

### With Dashboard

```bash
pip install -e ".[dashboard]"
```

### With Everything (dev + dashboard)

```bash
pip install -e ".[all]"
```

## Verify Installation

### Quick Smoke Test

```bash
python -c "import analysis, physics; print('ok')"
```

Expected output: `ok`

### Full Smoke Test

```bash
python run_all_validations.py --smoke
```

This runs a fast subset of all 12 validation suites to confirm everything
is working. Expected output: all suites report PASS.

### Full Validation (680+ checks)

```bash
python run_all_validations.py
```

Expected: 12/12 suites pass, 680+ checks, ~3 minutes.

## Run a Case Study

After installation, run a case study to see Aethermor in action:

```bash
python benchmarks/case_study_cooling_decision.py
```

This demonstrates the cooling-vs-substrate tradeoff analysis described
in [docs/CASE_STUDY.md](CASE_STUDY.md).

## Upgrade

```bash
pip install --upgrade https://github.com/Yoder23/aethermor/releases/download/v1.0.0/aethermor-1.0.0-py3-none-any.whl
```

Replace `v1.0.0` with the target version.

After upgrading, re-run the smoke test:

```bash
python -c "import analysis, physics; print('ok')"
python run_all_validations.py --smoke
```

## Environment Lock

For reproducible environments, pin the exact version:

```bash
pip install aethermor==1.0.0
pip freeze > requirements.lock
```

## Requirements

- **Python**: 3.10, 3.11, or 3.12
- **Core dependencies**: numpy, pandas, scipy, matplotlib
- **Optional (dashboard)**: dash, plotly
- **Optional (dev)**: pytest, coverage, flake8

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: physics` | Run from the aethermor directory, or install with `pip install -e .` |
| Dashboard won't start | Install with `pip install -e ".[dashboard]"` |
| Tests fail on import | Ensure Python 3.10+ and all core dependencies are installed |
| Validation suite slow | Normal: ~3 minutes for 680+ checks. Use `--smoke` for fast check. |
