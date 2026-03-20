"""
Research Example 2: When Does Adiabatic Computing Pay Off?

QUESTION: At what operating frequency and technology node does the overhead
of adiabatic (charge-recovery) logic become worthwhile compared to CMOS?

Adiabatic logic dissipates energy proportional to R·C²·V²·f — so it gets
more efficient at lower frequencies, while CMOS dynamic energy is constant.
However, CMOS leakage dominates at very low frequencies, creating a
complex crossover landscape.

This script maps the crossover frequency across technology nodes and
temperatures, identifying the operating regimes where each paradigm wins.

Run:
    python examples/adiabatic_crossover.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
from physics.constants import landauer_limit
from analysis.regime_map import paradigm_comparison, classify_regime


def crossover_vs_technology_node():
    """
    Find the adiabatic crossover frequency for each technology node.

    Below this frequency, adiabatic logic uses less energy per switch.
    This tells hardware teams at what clock speeds charge-recovery is viable.
    """
    print("=" * 80)
    print("RESEARCH QUESTION: When does adiabatic logic beat CMOS?")
    print("=" * 80)
    print()
    print(f"{'Tech Node':>10} {'Crossover Freq':>16} {'CMOS E_dyn':>14} "
          f"{'CMOS Gap':>12} {'Adiab Gap @100MHz':>18}")
    print("-" * 74)

    for node in [130, 65, 45, 28, 14, 7, 3]:
        cmos = CMOSGateEnergy(tech_node_nm=node)
        adiab = AdiabaticGateEnergy(tech_node_nm=node)

        f_cross = adiab.crossover_frequency(cmos)
        E_dyn = cmos.dynamic_energy()
        gap = cmos.landauer_gap(300.0, 1e9)
        adiab_gap_100mhz = adiab.landauer_gap(300.0, 1e8)

        print(f"{node:>7} nm {f_cross:>16.2e} Hz {E_dyn:>14.2e} J "
              f"{gap:>12.1f}× {adiab_gap_100mhz:>15.1f}×")

    print()
    print("INSIGHT: At smaller nodes, the crossover frequency INCREASES")
    print("because CMOS energy drops while adiabatic RC overhead persists.")
    print("This means adiabatic logic is most beneficial at OLDER nodes.")


def energy_vs_frequency_comparison():
    """
    Compare CMOS, adiabatic, and reversible energy across 6 decades of frequency.
    """
    print()
    print("=" * 80)
    print("ENERGY PER SWITCH vs FREQUENCY (7 nm, 300 K)")
    print("=" * 80)
    print()
    print(f"{'Frequency':>12} {'CMOS':>14} {'Adiabatic':>14} {'Reversible':>14} "
          f"{'Landauer':>14} {'Winner':>12}")
    print("-" * 84)

    cmos = CMOSGateEnergy(tech_node_nm=7)
    adiab = AdiabaticGateEnergy(tech_node_nm=7)
    from physics.energy_models import ReversibleGateEnergy, LandauerLimitEnergy
    rev = ReversibleGateEnergy()
    landauer = LandauerLimitEnergy()

    for freq in [1e6, 1e7, 1e8, 1e9, 1e10, 1e11]:
        E_c = cmos.energy_per_switch(freq)
        E_a = adiab.energy_per_switch(freq)
        E_r = rev.energy_per_switch(freq)
        E_l = landauer.energy_per_switch(freq)

        winner = min(
            [("CMOS", E_c), ("Adiabatic", E_a), ("Reversible", E_r)],
            key=lambda x: x[1]
        )[0]

        print(f"{freq:>12.0e} {E_c:>14.2e} {E_a:>14.2e} {E_r:>14.2e} "
              f"{E_l:>14.2e} {winner:>12}")

    print()
    print("INSIGHT: Reversible computing wins at all frequencies because its")
    print("energy is dominated by the clock overhead (~k_B·T), not by CV².")
    print("But this assumes perfect reversible gates — practical overhead")
    print("(3× gate count) reduces the advantage significantly.")


def temperature_sensitivity():
    """
    Show how the paradigm winner changes with operating temperature.

    At cryogenic temperatures, the Landauer limit drops dramatically,
    making near-limit operation more achievable.
    """
    print()
    print("=" * 80)
    print("PARADIGM COMPARISON vs TEMPERATURE (7 nm, 1 GHz)")
    print("=" * 80)
    print()

    cmos = CMOSGateEnergy(tech_node_nm=7)
    adiab = AdiabaticGateEnergy(tech_node_nm=7)
    from physics.energy_models import ReversibleGateEnergy
    rev = ReversibleGateEnergy()

    print(f"{'Temperature':>12} {'CMOS Gap':>12} {'Adiab Gap':>12} {'Rev Gap':>12} "
          f"{'Landauer':>14}")
    print("-" * 66)

    for T in [4, 10, 50, 77, 150, 300, 400, 500]:
        E_l = landauer_limit(T)
        gap_c = cmos.landauer_gap(T, 1e9)
        gap_a = adiab.landauer_gap(T, 1e9)
        gap_r = rev.landauer_gap(T, 1e9)

        print(f"{T:>9} K {gap_c:>12.0f}× {gap_a:>12.0f}× {gap_r:>12.1f}× "
              f"{E_l:>14.2e} J")

    print()
    print("INSIGHT: At 4 K (cryogenic), the Landauer limit is 75× lower,")
    print("but CMOS leakage drops even faster. The gap is LARGEST at low T.")
    print("Reversible computing's gap stays constant — its advantage grows")
    print("at higher temperatures where CMOS leakage explodes.")


if __name__ == "__main__":
    crossover_vs_technology_node()
    energy_vs_frequency_comparison()
    temperature_sensitivity()
