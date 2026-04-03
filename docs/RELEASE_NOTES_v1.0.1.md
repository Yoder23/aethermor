# Aethermor v1.0.1 Release Notes

**Date:** 2026-04-03
**Status:** Development Status :: 4 - Beta (architecture-stage thermal engineering)

> **Scope: Architecture-stage thermal exploration and inverse design.
> Hardware-correlated against 3 published chip designs (A100, i9-13900K, M1).
> Not intended for sign-off, transient package verification, or transistor-level
> thermal closure.**

## What's New in 1.0.1

v1.0.1 is a documentation, validation, and packaging overhaul following six
rounds of peer review. No physics model changes — all improvements are in
packaging, documentation, validation coverage, and onboarding.

### Package Restructure

- All modules moved under `aethermor/` namespace (`aethermor.physics`,
  `aethermor.analysis`, `aethermor.validation`, `aethermor.simulation`).
- Proper installable package with `pip install -e .`.
- CLI entry point: `aethermor dashboard`, `aethermor validate`, `aethermor version`.
- Monolithic `app.py` (730 lines) replaced with modular `aethermor/app/` package.

### Physics & Validation

- **Yovanovich (1983) spreading resistance** in `PackageStack` — A100 θ_jc
  accuracy improved from 1.97× to 0.98× of measured value.
- **Material database expanded** from 9 to 21 materials (aluminum, tungsten,
  molybdenum, AlN, alumina, BeO, sapphire, germanium, SAC305 solder, FR-4,
  thermal grease, AlSiC). 192 cross-validation checks (was 93).
- **Independent textbook validation** — 16 hand-calculable checks (Incropera,
  CRC Handbook, Landauer 1961, Yovanovich 1983), all at 0.00% error.

### Documentation

- **Engineer review checklist** — 5-step, 5-minute walkthrough in README.
- **Escalation rule** — clear guidance on when to escalate to FEA/CFD.
- **Hardware correlation numbers** surfaced in README (A100 0.028 vs 0.029 K/W,
  i9-13900K 382 vs 373 K, M1 72.7°C in 60–75°C range).
- **Production-ready scope** — blockquote at top of README.
- Root directory cleaned: `HONEST_REVIEW.md`, `VALIDATION.md`,
  `RELEASE_NOTES_v1.0.0.md` moved to `docs/`.
- External validation template (Pilot 3) added for future engineering feedback.
- Calibration case study, datacenter GPU case study, and 5 new case studies.

### Automation

- **`verification_summary.json`** — `run_all_validations.py` emits a
  machine-readable artifact to `reports/` with version, git hash, timestamp,
  per-suite pass/fail, and environment info.
- `release_check.py` updated for relocated docs and case-insensitive matching.

## Full Verification Suite

```bash
python -m pytest tests/ -v                    # 308 tests (1 skipped)
python run_all_validations.py                 # 12+ suites, 800+ checks
python evaluate_aethermor.py                  # 5-minute onboarding demo
```

### Verification Counts

| Suite | Checks |
|-------|--------|
| Unit / integration / robustness tests | 308 |
| Physics cross-checks | 133 |
| Material cross-validation (21 materials × 3 sources) | 192 |
| Chip thermal database (12 chips × 4 segments) | 82 |
| Real-world chip validation | 33 |
| Case studies (datacenter, mobile, cooling, substrate, bottleneck) | 23+ |
| Literature cross-checks | 20 |
| Experimental measurement validation | 18 |
| Independent textbook validation | 16 |
| **Total** | **800+** |

## Install

```bash
pip install https://github.com/Yoder23/aethermor/releases/download/v1.0.1/aethermor-1.0.1-py3-none-any.whl
```

## Upgrade from v1.0.0

```bash
pip install --upgrade https://github.com/Yoder23/aethermor/releases/download/v1.0.1/aethermor-1.0.1-py3-none-any.whl
```

See [CHANGELOG.md](../CHANGELOG.md) for the complete change log.
