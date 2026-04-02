# Case Study: The Cooling Upgrade That Wouldn't Help

## The Scenario

A data center architecture team is designing their next-generation AI
accelerator — a 5 nm chip running at 1.5 GHz on standard silicon. Their
current server air cooling (h = 1,000 W/m²K) has them at the thermal limit.
They can't pack more gates without overheating.

They're evaluating a $2M data center retrofit to upgrade from air cooling
to direct liquid cooling (h = 20,000 W/m²K) for their 10,000-unit fleet.
The assumption: 20× more aggressive cooling should unlock significantly more
compute density.

**Aethermor's model suggests this assumption is wrong.**

## The Three Conclusions

### 1. Liquid Cooling Buys Almost Nothing on Silicon

| Cooling Solution               | h (W/m²K) | Max Density   | Gain    |
|-------------------------------|-----------|---------------|---------|
| Server air (current)          | 1,000     | 3.984 × 10⁷   | —       |
| Direct liquid ($2M retrofit)  | 20,000    | 3.996 × 10⁷   | **0.3%** |
| Exotic direct-die (theoretical) | 50,000  | 4.015 × 10⁷   | 0.8%    |

20× more aggressive cooling buys **0.3% more compute density**.

**Why?** Silicon's thermal conductivity (148 W/m·K) creates an irreducible
*conduction floor*. Heat cannot leave the die interior fast enough,
regardless of how aggressively you cool the surface. The convective
resistance (surface → coolant) is already tiny relative to the conductive
resistance (die interior → surface). Making it tinier changes almost nothing.

### 2. Changing the Substrate Is 780× More Effective

| Substrate + Cooling        | k (W/m·K) | Max Density    | vs Si+Air | vs Si+Liquid |
|---------------------------|-----------|----------------|-----------|-------------|
| Diamond + air             | 2,200     | 6.840 × 10⁸    | 17.2×     | 17.1×       |
| SiC + air                 | 490       | 1.324 × 10⁸    | 3.3×      | 3.3×        |
| GaN + air                 | 130       | 7.792 × 10⁷    | 2.0×      | 2.0×        |
| Silicon + air             | 148       | 3.984 × 10⁷    | 1.0×      | 1.0×        |

SiC with the **same cheap air cooling** gives 232% more density — and
**3.3× more** than silicon with the expensive liquid cooling upgrade.

The decision is unambiguous: don't retrofit the data center. Change the
substrate. SiC + air >> Si + liquid.

### 3. Compute Redistribution Gives 47% for Free

Even without changing substrate or cooling, the team can gain 47% more
throughput by redistributing compute density across their SoC blocks:

| Block        | Current Density | Optimized Density | Headroom |
|-------------|----------------|-------------------|----------|
| GPU cluster | 10,000          | 6,994 (↓ 0.7×)    | 1.0× (bottleneck) |
| L3 cache    | 8,000           | 139,876 (↑ 17.5×)  | 26.2×    |
| I/O complex | 2,000           | 19,206 (↑ 9.6×)    | 14.4×    |

The GPU is at the thermal wall. The L3 cache has **26× thermal headroom**.
The optimizer shifts compute density from the GPU to the cache and I/O
blocks, yielding **47% more total throughput** with zero hardware changes.

**Critical insight**: The 200 W power budget is not the constraint. Only
10.2 W is used. The binding constraint is *thermal*, not electrical. Adding
more power capacity does nothing.

## What Makes This Non-Obvious

An experienced thermal engineer knows qualitatively that "more cooling has
diminishing returns" and "some blocks run hotter than others." What they
typically **don't** have without significant manual work is:

1. **Quantified futility** — knowing that 20× cooling gains exactly 0.3%
   density, not "a little" or "not much"
2. **Cross-material comparison** — knowing that SiC + air beats Si + liquid
   by 3.3×, not just "substrate matters"
3. **Optimal redistribution** — knowing the L3 cache can absorb 17.5×
   more density and that the throughput gain is exactly 47%, not just
   "move compute away from the hot block"

Getting these numbers from COMSOL or HotSpot requires setting up separate
models for each material and cooling configuration (typically 1-2 days of
engineering time per configuration). Aethermor produces all three conclusions
from a single API in **10 seconds**.

## Run It Yourself

```bash
python benchmarks/case_study_cooling_decision.py
```

The script prints every number shown above, computed live from Aethermor's
physics models. No hardcoded results — change the parameters (tech node,
frequency, cooling, materials) and see how the conclusions shift.

## What This Proves and What It Does Not

**Proves**: Aethermor surfaces quantitative engineering conclusions from first
principles that are non-trivial to obtain from existing tools. The physics
(Fourier conduction, conduction floor, combined conduction+convection models)
is well-established and validated against published data (see
[VALIDATION.md](../VALIDATION.md)).

**Does not prove**: That the specific dollar amounts or density numbers apply
to any particular chip design. Real chips have layout-dependent effects,
non-uniform heat spreading, and manufacturing variation that this model does
not capture. Aethermor is for architecture-stage exploration — the stage
where you decide *whether* to invest in liquid cooling or substrate changes,
before committing to the detailed CAD and fabrication work that would confirm
the exact numbers.
