# External Validation

This document tracks external evaluation of Aethermor by engineers and
researchers who are not the original developers.

---

## Purpose

Production-grade tools need evidence that someone besides the developer
can use them reliably. This page documents external evaluations,
correlations, and feedback.

---

## External Correlations

| # | Source | Description | Status |
|---|--------|-------------|--------|
| 1 | — | Measured lab data from a collaborator | Open |
| 2 | — | Internal company test data from a trusted reviewer | Open |
| 3 | — | Comparison against trusted industrial/academic baseline | Open |

*To contribute a correlation: open an issue with the `external-validation`
label, or email the maintainers with your data and methodology.*

---

## External User Pilots

| # | Role / Organization | Use Case | Useful? | Issues Found | Status |
|---|---------------------|----------|---------|--------------|--------|
| 1 | — | — | — | — | Open |
| 2 | — | — | — | — | Open |
| 3 | — | — | — | — | Open |

### What Counts as a Valid Pilot

- The evaluator uses Aethermor independently on a real problem
- The evaluator provides written feedback
- At least one evaluator finds a real issue or limitation
- At least one evaluator says it was useful enough to influence analysis

### Pilot Feedback Template

```
Organization (can be anonymized): ___
Role: ___
Use case: ___
What worked: ___
What failed or was confusing: ___
Would you use it again? ___
What changed after using it (if anything): ___
```

---

## How to Participate

1. Clone the repo and install: `pip install -e .`
2. Run the validation suite: `python run_all_validations.py`
3. Try a case study: `python benchmarks/case_study_cooling_decision.py`
4. Apply Aethermor to your own problem
5. Send feedback via GitHub issue (`external-validation` label) or email

---

## Changes Made from External Feedback

| Date | Source | Feedback | Change Made |
|------|--------|----------|-------------|
| — | — | — | — |

*This table will be updated as external feedback is received and acted on.*
