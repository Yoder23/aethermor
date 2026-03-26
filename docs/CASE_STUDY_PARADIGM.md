# Case Study: When Silicon Hits the Wall — Material and Paradigm Selection

## The Scenario

An architecture team is designing a next-generation compute tile for a 5 nm
process at 2 GHz. They have liquid cooling (h = 5,000 W/m²K) and need to
maximize gate density. Their silicon prototype is thermally limited.

They're evaluating two independent options:
1. **Switch substrate** from silicon to SiC or diamond
2. **Switch paradigm** from CMOS to adiabatic logic for the CPU block

**Aethermor quantifies both tradeoffs in under 30 seconds.**

## The Engineering Question

> "How much more compute density can we get by changing the substrate vs
> changing the logic paradigm? Which investment has the higher payoff?"

## Baseline Intuition

Engineers expect:
- Diamond is better than silicon (everyone knows that)
- Adiabatic logic saves energy (textbook result)
- But how much? And which matters more for *our* specific constraints?

## What Aethermor Shows

### Material Comparison (same cooling, same paradigm)

| Substrate | Max Density (gates/element) | Gain vs Silicon | Cost Factor |
|-----------|---------------------------|----------------|-------------|
| Silicon | 3.98 × 10⁷ | — | 1× |
| SiC | 1.32 × 10⁸ | **232%** | ~3× |
| Diamond | 5.92 × 10⁸ | **1,387%** | ~50× |
| GaAs | 1.48 × 10⁷ | −63% | ~2× |

Diamond offers a 14× density advantage, but at 50× the cost. SiC gives
2.3× the density at 3× the cost — a much better cost-performance ratio.

### Paradigm Comparison (silicon, same cooling)

| Paradigm | Max Density at 1 GHz | Gain vs CMOS |
|----------|---------------------|-------------|
| CMOS | 3.98 × 10⁷ | — |
| Adiabatic | 7.61 × 10⁹ | **191×** |

At 1 GHz on silicon, adiabatic logic allows 191× higher density. The
crossover frequency — where CMOS becomes competitive — depends on the
technology node and decreases at smaller nodes.

### Combined Insight

| Strategy | Density Gain | Investment |
|----------|-------------|------------|
| Upgrade substrate (Si → SiC) | 2.3× | Per-die premium |
| Switch paradigm (CMOS → adiabatic) | 191× | Design methodology |
| Both (SiC + adiabatic) | >400× | Both |

**The paradigm switch dominates the substrate switch by two orders of
magnitude.** If the design frequency is below the crossover point,
switching to adiabatic logic is worth far more than upgrading the substrate.

## The Decision

- **If redesign is feasible**: Switch the compute-bound blocks to adiabatic
  logic. The density gain dwarfs any substrate improvement.
- **If staying with CMOS**: SiC offers the best cost-performance ratio
  (2.3× density at 3× cost). Diamond is only justified for extreme
  density requirements.
- **Crossover frequency**: The technology roadmap shows where the crossover
  shifts at each node — critical for knowing when adiabatic logic is
  economically viable.

## Why This Matters

This two-dimensional comparison (material × paradigm) is practically
impossible to do manually:

- **COMSOL** models one material at a time with no paradigm energy model
- **HotSpot** doesn't include multi-paradigm energy modeling
- **Spreadsheets** can approximate the 1D case but miss thermal spreading
  effects and conduction floor interactions

Aethermor's `material_ranking()` and `paradigm_density_comparison()`
produce the full comparison table in one call each.

## Reproduce It

```bash
python benchmarks/case_study_substrate_selection.py
```

See also: [benchmarks/case_study_substrate_selection.py](../benchmarks/case_study_substrate_selection.py)
