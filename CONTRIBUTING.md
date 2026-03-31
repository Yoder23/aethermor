# Contributing to Aethermor

Thanks for contributing.

## Ground Rules

- All physics must use SI units (Joules, Kelvin, Watts, metres).
- Every claim must be backed by tests or validation checks.
- Keep changes minimal, explicit, and test-backed.
- Do not introduce unverifiable benchmark claims.

## High-Value Contributions

The most valuable contributions extend the physics foundation:

- **New materials**: Register via `registry.register("my_mat", Material(...))`
  with published property values and source citations
- **New computing paradigms**: Implement the `EnergyModel` protocol
  (`energy_per_switch()` + `landauer_gap()`) and register via
  `paradigm_registry.register("my_paradigm", MyModelClass)`
- **New cooling layers**: Register via `cooling_registry.register("my_tim", ThermalLayer(...))`
- **Anisotropic thermal transport**: Extend `FourierThermalTransport` for
  direction-dependent thermal conductivity
- **Interconnect power models**: Wire dissipation as a function of technology node
- **Additional validation checks**: Add to `validation/validate_all.py` with
  reference source citations

All contributions must include tests in `tests/` and, for physics, a
corresponding validation check with a cited reference.

## Development Setup

```bash
git clone https://github.com/Yoder23/aethermor.git
cd aethermor
pip install -e ".[all]"    # core + dashboard + dev tools
```

Run tests:

```bash
python -m pytest tests/ -v              # 277 tests
python -m aethermor.validation.validate_all       # 133 physics cross-checks
```

Run examples:

```bash
python examples/custom_material.py      # extensibility walkthrough
aethermor dashboard                     # interactive explorer UI
```

## Pull Request Requirements

- Include a clear problem statement.
- Include test evidence (`pytest` output).
- If adding physics, include validation checks with reference citations.
- If touching existing models, verify the full validation suite passes.

## Style Expectations

- Python code should remain readable and explicit.
- Use type hints for public API functions.
- Prefer dataclasses for data containers.
- Follow PEP 8 naming conventions.

## Commit and PR Scope

- One concern per PR when possible.
- Separate refactors from behavioral changes.
- Do not include generated artifact directories.
