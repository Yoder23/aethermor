# Safe Use Policy

**Version**: 1.0 — applies to Aethermor v1.0.x and v1.1.x  
**Last reviewed**: 2026-04-01  
**Status**: Active

Aethermor is validated for architecture-stage thermal exploration and
inverse design. This document defines exactly which use cases are in scope,
which require caution, and which are out of scope.

---

## Safe

These are the intended, validated use cases. Results from these workflows
are backed by 700+ validated checks against published data.

| Use Case | Description |
|----------|-------------|
| Architecture-stage thermal exploration | Sweep materials, cooling, densities to narrow the design space |
| Cooling tradeoff screening | Compare air → liquid → microchannel; find diminishing returns |
| Material comparison | Rank substrates by maximum sustainable compute density |
| Compute-density screening | Find thermal wall for a given node, frequency, material, cooling |
| Hotspot / headroom ranking | Identify which SoC blocks are thermally limited vs underutilized |
| Paradigm crossover analysis | Find when adiabatic logic becomes more efficient than CMOS |
| Technology roadmap projection | Track energy, Landauer gap, and thermal wall across nodes |
| Inverse thermal design | Find max density, min cooling, optimal power distribution |
| Design-space Pareto extraction | Multi-dimensional sweeps with automatic frontier detection |
| Package-level thermal path analysis | Use PackageStack for die → TIM → IHS → heatsink with contact resistances |

---

## Use with Caution

These use cases are supported but require awareness of model boundaries.

| Use Case | Caution |
|----------|---------|
| Absolute junction temperature | `CoolingStack` captures conductive physics but omits package-specific interface resistances; use `PackageStack` for contact resistance modeling, or use for relative comparisons, not sign-off Tj. See ACCURACY_ENVELOPE.md for expected residuals. |
| Detailed package assumptions | CoolingStack/PackageStack uses constant-property 1D layers; use measured thermal interface data for your specific package |
| Vendor-specific cooling edge cases | Factory cooling configurations are representative, not exact vendor specs |
| Public-spec-based chip approximation | Published TDP and die area are used; internal power maps and layout details are not modeled |
| Highly non-uniform power maps | Use ChipFloorplan model; base simulation assumes uniform density per element |

---

## Not For

These use cases are explicitly out of scope. Do not use Aethermor for:

| Use Case | Reason |
|----------|--------|
| Sign-off thermal closure | Requires die-level correlation with proprietary floorplan data and FEM |
| Layout closure | Aethermor operates at gate-level energy, not transistor or interconnect level |
| Transient package verification | Power gating, workload transients, and time-domain thermal response are not validated |
| Transistor-level reliability prediction | No NBTI, HCI, electromigration, or process-specific degradation models |
| Replacing COMSOL/ANSYS | Different abstraction level; Aethermor is for exploration, COMSOL is for detailed verification |

---

## Minimum Required Inputs

Before trusting any output, ensure you have provided:

1. **Die area** (mm²) — from datasheet or die photo measurement
2. **Total power** (W) — from TDP spec or measured workload
3. **Cooling configuration** — at minimum, h_ambient or a CoolingStack/PackageStack
4. **Ambient temperature** — actual operating environment, not room temperature assumption

---

## Required Validation Steps

Before using Aethermor results in any decision:

1. Run `aethermor validate` — confirm physics and material checks pass
2. Run `python -m benchmarks.external_benchmark_pack` — confirm analytical benchmarks pass
3. Check your operating point falls within the envelope defined in `ACCURACY_ENVELOPE.md`
4. Compare at least one result against a published datasheet value for your target platform

---

## Decision Rule

> If your question is "which direction should we go?" → Aethermor is the right tool.
>
> If your question is "is this specific design ready to tape out?" → use COMSOL/ANSYS.

---

## Release Checklist (for maintainers)

Before any release, verify:

- [ ] All `pytest` tests pass
- [ ] `aethermor validate` passes
- [ ] `benchmarks/external_benchmark_pack.py` passes (6/6)
- [ ] `benchmarks/hardware_correlation.py` runs without error
- [ ] `benchmarks/uncertainty_propagation.py` runs without error
- [ ] This document has been reviewed and version number updated
- [ ] ACCURACY_ENVELOPE.md reflects any new validation data
- [ ] CHANGELOG.md updated with scope of changes

---

## Scope Statement

Validated for architecture-stage thermal exploration and inverse design;
not intended for sign-off, transient package verification, or transistor-level
thermal closure.
