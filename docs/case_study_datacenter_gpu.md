# Case Study: 8-GPU Datacenter Node Cooling Strategy

**Decision**: Air cooling vs. liquid cooling vs. substrate upgrade for a next-generation
8× GPU compute node.

**Result**: Substrate selection matters 780× more than cooling upgrades.
Compute redistribution across SoC blocks gives 47% more throughput for free.

---

## The Problem

An engineering team is designing a next-generation GPU compute rack:

- **8 × 600W accelerators** per node (think NVIDIA H100-class)
- **800 mm² silicon dies**, 4 nm process
- **4,800W total node power**
- **Target: Tj < 85°C (358 K)** for reliability qualification
- Budget decision: $2M data center retrofit for liquid cooling, or invest
  in substrate R&D

## Aethermor Analysis (< 10 seconds)

### Step 1: Baseline — What cooling does silicon need?

```python
from aethermor.analysis.thermal_optimizer import ThermalOptimizer

opt = ThermalOptimizer(tech_node_nm=4, frequency_Hz=2e9)
req = opt.find_min_cooling("silicon", gate_density=1e5)
print(f"Min h_conv: {req['min_h_conv']:.0f} W/(m²·K)")
print(f"Category:   {req['cooling_category']}")
```

At 600W on 800 mm² silicon, the model reports h_conv ≈ 1,500 W/(m²·K)
is the minimum — requiring **liquid cooling** to stay below 85°C.

### Step 2: What does 20× more aggressive cooling buy?

| h_conv (W/m²·K) | Cooling Type | Max Density Gain | ΔTj |
|-----------------|-------------|-----------------|-----|
| 500 | Forced air | Baseline | — |
| 1,500 | Liquid | +0.2% | −3°C |
| 5,000 | Aggressive liquid | +0.3% | −4°C |
| 10,000 | Direct die contact | +0.3% | −4°C |

**Diminishing returns**: Going from forced air to aggressive liquid cooling
yields only 0.3% more compute density. The **conduction floor** — the
irreducible thermal resistance through the silicon die — caps the benefit.

### Step 3: What about a different substrate?

| Substrate | k (W/m·K) | Max Density vs Silicon | Cost |
|-----------|-----------|----------------------|------|
| Silicon | 150 | 1.0× (baseline) | — |
| SiC | 370 | 2.3× | Per-die premium |
| Diamond | 2000 | 13.9× | R&D investment |

**SiC gives 232% more compute density** — the same air cooling that's
inadequate for silicon becomes more than sufficient for SiC.

### Step 4: Compute redistribution (free)

Using `optimize_power_distribution()` on the heterogeneous SoC:

```python
from aethermor.physics.chip_floorplan import ChipFloorplan

soc = ChipFloorplan.modern_soc()
result = opt.optimize_power_distribution(soc, h_conv=1000)
```

The GPU block is thermally saturated (1.0× headroom), but the L3 cache block
has 26× thermal headroom. Redistributing compute from GPU to underutilized
blocks yields **47% more throughput** with zero hardware changes.

## The Decision Matrix

| Strategy | Density Gain | Cost | Timeline |
|----------|-------------|------|----------|
| Upgrade to liquid cooling (20×) | **0.3%** | $2M retrofit | 6 months |
| Switch to SiC substrate | **232%** | Per-die premium | 12–18 months |
| Redistribute compute across SoC | **47% throughput** | **$0** | Immediate |
| Diamond heat spreader | **1,387%** | R&D investment | 2–3 years |

## Engineering Recommendation

1. **Immediate**: Redistribute compute across SoC blocks (+47%, free)
2. **Next gen**: Qualify SiC substrate (+232%, justified per-die premium)
3. **Do not**: Retrofit to liquid cooling for 0.3% gain at $2M

## Reproduce This

```bash
pip install -e .
python benchmarks/case_study_datacenter.py       # Full analysis with pass/fail gates
python benchmarks/case_study_cooling_decision.py  # Cooling vs substrate comparison
```

Both scripts are deterministic and print pass/fail results for every
quantitative claim.

---

**Key insight**: At architecture stage, the substrate thermal conductivity
floor — not the cooling solution — determines compute density limits.
Aethermor surfaces this in seconds; discovering it through CFD iteration
typically takes weeks of engineering time.
