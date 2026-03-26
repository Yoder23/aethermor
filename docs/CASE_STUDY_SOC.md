# Case Study: The SoC Block That Was Wasting Thermal Budget

## The Scenario

A chip architect is designing a heterogeneous 5 nm SoC with four functional
blocks: CPU, GPU, L3 cache, and I/O. The GPU block is thermally limited —
hitting 95°C at target density — so the team is considering a $3M cooling
upgrade from server air to direct liquid cooling.

**Aethermor shows a better answer exists inside the chip itself.**

## The Engineering Question

> "We have a 50 W power budget and our GPU block is at the thermal limit.
> Should we upgrade cooling, or is there a way to get more throughput
> without changing hardware?"

## Baseline Intuition

Most architects would expect:
- More aggressive cooling → more thermal headroom → more compute density
- All blocks are similarly utilized
- The only way to add throughput is to add cooling capacity

## What Aethermor Shows

Running the SoC bottleneck case study reveals:

| Block | Density | Temperature | Headroom |
|-------|---------|-------------|----------|
| CPU (CMOS) | High | At limit | ~0% |
| GPU (CMOS) | High | At limit | ~0% |
| L3 Cache | Low | Well below limit | **26× headroom** |
| I/O | Low | Well below limit | **15× headroom** |

**The cache and I/O blocks are using less than 5% of their thermal budget.**

By redistributing compute density from the over-utilized GPU block to the
under-utilized cache and I/O blocks, Aethermor finds:

| Strategy | Throughput Gain | Cost |
|----------|----------------|------|
| Upgrade to liquid cooling | Marginal | $3M retrofit |
| Redistribute density across blocks | **~47%** | **Free** |
| Switch CPU to adiabatic logic | Additional density gain | Design effort |

## The Decision

**Don't upgrade cooling. Redistribute compute.**

The 47% throughput gain from reallocation is free — it requires no hardware
changes, no cooling upgrades, and no additional power. It works because heat
transfer is a local phenomenon: a thermally underutilized block has capacity
that cannot help a distant overheated block, but compute workload *can* be
moved there.

## Why This Matters

This insight is difficult to get from forward-only thermal tools:

- **HotSpot** shows per-block temperatures but doesn't compute headroom maps
  or optimal reallocation in a single call
- **COMSOL** requires manual post-processing to extract headroom percentages
- **Manual analysis** requires setting up separate runs for each redistribution
  scenario

Aethermor's `thermal_headroom_map()` and `optimize_power_distribution()`
answer this question in one function call.

## Reproduce It

```bash
python benchmarks/case_study_soc_bottleneck.py
```

See also: [benchmarks/case_study_soc_bottleneck.py](../benchmarks/case_study_soc_bottleneck.py)
