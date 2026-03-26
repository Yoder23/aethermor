# Safe Use Policy

Aethermor is production-stable for architecture-stage thermal exploration and
inverse design. This document defines exactly which use cases are in scope,
which require caution, and which are out of scope.

---

## Safe

These are the intended, validated use cases. Results from these workflows
are backed by 680+ validated checks against published data.

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

---

## Use with Caution

These use cases are supported but require awareness of model boundaries.

| Use Case | Caution |
|----------|---------|
| Absolute junction temperature | Model captures conductive physics but omits package-specific interface resistances; use for relative comparisons, not sign-off Tj |
| Detailed package assumptions | CoolingStack uses constant-property 1D layers; use measured thermal interface data for your specific package |
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

## Decision Rule

> If your question is "which direction should we go?" → Aethermor is the right tool.
>
> If your question is "is this specific design ready to tape out?" → use COMSOL/ANSYS.

---

## Scope Statement

Production-stable for architecture-stage thermal exploration and inverse design;
not intended for sign-off, transient package verification, or transistor-level
thermal closure.
