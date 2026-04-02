# Technical Governance

**Version**: 1.0 — effective with Aethermor v1.1.0

This document defines the review processes, ownership, and trust
infrastructure for Aethermor.

---

## Model Review Checklist

Before merging any change that modifies physics, materials, or validation:

- [ ] **Unit tests pass**: `pytest tests/ -q` — zero failures
- [ ] **Validation suite passes**: `python -m aethermor.validation.validate_all` — exit 0
- [ ] **Benchmark pack passes**: `python -m benchmarks.external_benchmark_pack` — 6/6
- [ ] **Hardware correlation runs**: `python -m benchmarks.hardware_correlation` — no regression
- [ ] **Robustness tests pass**: `pytest tests/unit/test_robustness.py -q`
- [ ] **No new overconfident claims**: grep for "proves", "guarantees", "production-ready"
- [ ] **CHANGELOG.md updated**: with scope of change
- [ ] **ACCURACY_ENVELOPE.md reviewed**: if accuracy claims affected

---

## Validation Signoff

| Layer | Runner | Owner | Frequency |
|-------|--------|-------|-----------|
| Unit tests | `pytest tests/` | Any contributor | Every commit |
| Physics validation | `aethermor validate` | Maintainer | Every release |
| External benchmarks | `benchmarks/external_benchmark_pack.py` | Maintainer | Every release |
| Hardware correlation | `benchmarks/hardware_correlation.py` | Maintainer | Major releases |
| Uncertainty analysis | `benchmarks/uncertainty_propagation.py` | Maintainer | When model changes |
| CI smoke test | `scripts/ci_smoke_test.py` | CI system | Every commit |

---

## Source-of-Truth References

All physics models reference published data. Here are the authoritative
sources:

| Domain | Source | Used For |
|--------|--------|----------|
| Fundamental constants | CODATA 2018 (NIST) | k_B, h, e, c, σ |
| Material properties | CRC Handbook of Chemistry & Physics | k, c_p, ρ |
| Semiconductor data | IRDS/ITRS roadmap tables | Gate energy scaling |
| Thermal interface | Published vendor datasheets | TIM conductivity, contact resistance |
| Chip specs | Public datasheets (Intel ARK, NVIDIA specs) | Die area, TDP, θ_jc |
| Analytical solutions | Fourier's law, Newton's law of cooling | Cross-checks |

---

## Benchmark Update Ownership

| Benchmark | Update Trigger | Responsible |
|-----------|---------------|-------------|
| `external_benchmark_pack.py` | New analytical case available | Maintainer |
| `hardware_correlation.py` | New published chip data | Maintainer |
| `uncertainty_propagation.py` | Model parameter changes | Contributor + maintainer review |
| Material database | New material data published | Contributor + maintainer review |
| Cooling layer library | New TIM/cooling data | Contributor + maintainer review |

---

## Decision Authority

| Decision | Authority | Escalation |
|----------|-----------|-----------|
| Add new material to database | Any contributor (with source) | PR review |
| Modify physics model | Maintainer only | Must pass all validation layers |
| Change accuracy claims | Maintainer only | Must update ACCURACY_ENVELOPE.md |
| Upgrade classifier beyond Beta | Maintainer consensus | Requires external validation data |
| Remove or rename public API | Major release only | Must follow API_STABILITY.md deprecation policy |

---

## Incident Response

If a user reports incorrect results:

1. **Reproduce**: Create a minimal test case
2. **Root-cause**: Identify the failing model or assumption
3. **Scope**: Determine if the issue affects other cases
4. **Fix**: Patch the model and add a regression test
5. **Communicate**: Update ACCURACY_ENVELOPE.md and CHANGELOG.md
6. **Release**: Patch release (x.x.+1) if the fix changes outputs
