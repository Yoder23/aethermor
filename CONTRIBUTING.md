# Contributing to Aethermor

Thanks for contributing.

## Ground Rules

- Keep claims scoped to software/simulation evidence.
- Prefer reproducibility over novelty in PRs.
- Do not introduce unverifiable benchmark claims.
- Keep changes minimal, explicit, and test-backed.

## High-Value Contributions

The most valuable contributions extend the physics foundation:

- **New materials**: Add entries to `physics/materials.py` with published properties
- **New energy models**: Subclass gate energy models in `physics/energy_models.py`
  (e.g., superconducting logic, spintronic gates, photonic switching)
- **Anisotropic thermal transport**: Extend `FourierThermalTransport` for
  direction-dependent thermal conductivity
- **Interconnect power models**: Wire dissipation as a function of technology node
- **Thermal interface resistance**: Die → TIM → heatsink stack modeling

All physics contributions must include tests in `tests/unit/` and use SI units.

## Development Setup

```powershell
python -m pip install -r requirements.txt
```

Run tests:

```powershell
pytest -q
```

Run strict publication pipeline:

```powershell
$env:BENCH_ARTIFACT_ROOT="artifacts_pub_strict"
$env:BENCH_STEPS="80"
$env:ABLATION_N="20"
$env:PUB_MIN_PAIRS="20"
$env:RUN_PUBLICATION_ROBUSTNESS="1"
$env:PUB_REQUIRE_ROBUSTNESS="1"
$env:PUB_SWEEP_N="20"
$env:PUB_SWEEP_STEPS="80"
python run_all_benchmarks.py
python experiments/exp_ablations.py
python publication_gate.py
python experiments/exp_publication_robustness.py
```

## Pull Request Requirements

- Include a clear problem statement.
- Include expected behavior and actual behavior.
- Include test evidence (`pytest` output and, if relevant, report artifacts).
- If touching experimental claims, include updated report paths.

## Style Expectations

- Python code should remain readable and explicit.
- Keep environment variables documented in changed scripts.
- Avoid hidden data dependencies.

## Commit and PR Scope

- One concern per PR when possible.
- Separate refactors from behavioral changes.
- Do not include generated artifact directories unless explicitly requested for review.

## Reproducibility Expectations

If you change benchmark logic, include:
- Updated seeds/controls used
- Updated report files under `<BENCH_ARTIFACT_ROOT>/_report`
- Any changes to publication gate behavior (`publication_gate.py`)
