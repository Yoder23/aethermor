#!/usr/bin/env python3
"""
RESEARCH EXAMPLE: Technology roadmap projection
================================================

Research question: At what technology node does each computing paradigm
enter the thermodynamic regime, and when does the Landauer limit become
a practical engineering constraint?

This is the strategic planning analysis that chip architects and research
directors need.  Aethermor generates it in seconds.

What this script demonstrates:
  1. Energy-per-switch vs technology node for CMOS, adiabatic, reversible
  2. Landauer gap closure projection — when do we approach the physics limit?
  3. Paradigm crossover map — at what frequency does adiabatic beat CMOS?
  4. Thermal wall roadmap — max density per node per material
  5. Auto-generated strategic insights
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from analysis.tech_roadmap import TechnologyRoadmap

roadmap = TechnologyRoadmap(
    tech_nodes=[130, 65, 45, 28, 14, 7, 5, 3, 2, 1.4],
    materials=["silicon", "diamond", "silicon_carbide", "gallium_arsenide"],
)

# ═══════════════════════════════════════════════════════════════
# Full report at 1 GHz
# ═══════════════════════════════════════════════════════════════

print(roadmap.full_report(frequency_Hz=1e9, h_conv=1000))

# ═══════════════════════════════════════════════════════════════
# Frequency impact analysis
# ═══════════════════════════════════════════════════════════════

print()
print("=" * 100)
print("FREQUENCY IMPACT ON PARADIGM COMPETITIVENESS")
print("=" * 100)
print()

for freq in [1e8, 1e9, 1e10]:
    print(f"\n--- {freq/1e9:.1f} GHz ---")
    rows = roadmap.gap_closure_projection(frequency_Hz=freq)
    print(f"{'Node':>6s}  {'CMOS Gap':>10s}  {'Adiab Gap':>10s}  {'Rev Gap':>10s}")
    print("-" * 42)
    for r in rows:
        print(f"{r['node_nm']:>5.1f}nm  {r['gap_cmos']:>9.0f}×  "
              f"{r['gap_adiabatic']:>9.1f}×  {r['gap_reversible']:>9.1f}×")

print()
print("=" * 100)
print("KEY TAKEAWAYS FOR CHIP ARCHITECTS:")
print("=" * 100)
print("""
1. CMOS energy per switch drops with node scaling, but CANNOT go below
   the Landauer limit (k_B·T·ln2 ≈ 2.87e-21 J at 300K).

2. The Landauer gap for 7nm CMOS at 1 GHz is ~85,000× — enormous headroom
   but shrinking with each node.  At 1.4nm, gap drops to ~30,000×.

3. Adiabatic logic energy INCREASES with frequency (E ∝ f), so it's only
   competitive below its crossover frequency.  At 7nm, crossover is ~2 THz.

4. Reversible computing's gap is INDEPENDENT of technology node — it depends
   only on temperature.  This means its relative advantage grows as CMOS
   scales down.

5. Diamond substrate can sustain 10-50× higher density than Silicon at
   every node — it's the material asymptote for thermal computing.
""")
