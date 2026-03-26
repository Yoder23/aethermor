# Aethermor v1.0.0 Release Notes

## What's New in 1.0.0

Aethermor v1.0.0 upgrades the project from Beta to **Production/Stable**.

> **Scope: Production-stable for architecture-stage thermal exploration and inverse design; not intended for sign-off, transient package verification, or transistor-level thermal closure.**

The key addition is experimental measurement validation — closing the gap between
"matches published specs" and "matches real hardware measurements."

## Experimental Measurement Validation (18 checks)

`benchmarks/experimental_validation.py` validates the thermal model against
**published hardware measurements**, not just published specifications:

### Tier 1: JEDEC-Measured Thermal Resistance (θ_jc)
- NVIDIA A100: published θ_jc = 0.029 K/W
- Intel i9-13900K: published θ_jc = 0.43 K/W
- AMD Ryzen 7950X: published θ_jc = 0.11 K/W

### Tier 2: Published Experimental Data
- Kandlikar (2003) — microchannel ΔT at h = 10,000 W/(m²·K)
- Bar-Cohen & Wang (2009) — IR thermal imaging, 100 W on 1 cm² Si
- Yovanovich (1998) — spreading resistance analytical
- Full-path junction temperature for 100 W desktop package

### Tier 3: Cross-Validation
- HotSpot ev6 (Alpha 21264) benchmark — R_convec = 0.1 K/W
- Incropera & DeWitt analytical plane wall
- Biot number lumped capacitance
- Thermal time constant (L²/α)
- COMSOL-verified fin geometry
- 3D Fourier energy conservation (< 5%)

## Other Changes

- **Version**: 0.1.0 → 1.0.0
- **Classifier**: Development Status :: 4 - Beta → 5 - Production/Stable
- **CI matrix**: Python 3.10, 3.11, 3.12 (was 3.10 only)
- **CI pipeline**: experimental validation runs on every push
- **LIMITATIONS.md**: Rewritten to acknowledge published hardware measurement
  validation while maintaining honesty about remaining scope (no custom test
  chip IR imaging)
- **HONEST_REVIEW.md**: OSS readiness upgraded to "Production-ready for
  architecture-stage engineering"
- **VALIDATION.md**: New Section 4 documenting experimental measurement
  validation methodology

## Full Verification Suite

```bash
python -m pytest tests/ -v                    # 278 tests
python -m validation.validate_all             # 133 physics cross-checks
python benchmarks/chip_thermal_database.py    # 82 chip thermal database checks (12 chips)
python benchmarks/material_cross_validation.py # 93 material cross-validation checks (9 materials)
python benchmarks/literature_validation.py    # 20 literature cross-checks
python benchmarks/real_world_validation.py    # 33 real-world chip validations
python benchmarks/experimental_validation.py  # 18 experimental measurement checks
python benchmarks/case_study_datacenter.py    # 13 datacenter cooling strategy checks
python benchmarks/case_study_mobile_soc.py    # 10 mobile SoC thermal envelope checks
python run_all_validations.py                 # Master runner: 12 suites, all checks
```

**Total: 680+ checks, all passing.**

## Install

```bash
pip install https://github.com/Yoder23/aethermor/releases/download/v1.0.0/aethermor-1.0.0-py3-none-any.whl
```

Or from source:
```bash
git clone https://github.com/Yoder23/aethermor.git
cd aethermor
pip install -e .
```
