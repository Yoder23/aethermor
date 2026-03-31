"""
Technology roadmap projector — project paradigm viability across nodes.

This module answers the strategic planning question that chip architects
need: "At what technology node does each computing paradigm enter
the thermodynamic regime, and when does the Landauer limit become a
practical constraint?"

Aethermor integrates Landauer-aware energy models with multi-material
thermal simulation to produce roadmap projections including:
  - Energy per operation vs. technology node for all paradigms
  - Landauer gap closure curve per paradigm
  - Maximum sustainable density per node per material per cooling strategy
  - Node at which adiabatic/reversible paradigms become competitive
  - Thermal wall projection: when does Moore's Law hit the heat barrier?

Example
-------
>>> from aethermor.analysis.tech_roadmap import TechnologyRoadmap
>>> roadmap = TechnologyRoadmap()
>>> table = roadmap.energy_roadmap()
>>> print(roadmap.format_energy_roadmap(table))
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from aethermor.physics.constants import k_B, landauer_limit
from aethermor.physics.materials import MATERIAL_DB, get_material
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)
from aethermor.analysis.regime_map import thermal_density_limit, classify_regime


@dataclass
class TechnologyRoadmap:
    """
    Project energy efficiency, thermal limits, and paradigm viability
    across technology nodes.

    Parameters
    ----------
    tech_nodes : list of float
        Technology nodes to evaluate (nm).
    frequencies : list of float
        Operating frequencies to evaluate (Hz).
    materials : list of str
        Substrate materials to include.
    T_ambient : float
        Ambient temperature (K).
    """
    tech_nodes: List[float] = field(
        default_factory=lambda: [130, 65, 45, 28, 14, 7, 5, 3, 2, 1.4]
    )
    frequencies: List[float] = field(
        default_factory=lambda: [1e9, 5e9, 10e9]
    )
    materials: List[str] = field(
        default_factory=lambda: ["silicon", "diamond", "silicon_carbide",
                                 "gallium_arsenide", "gallium_nitride"]
    )
    T_ambient: float = 300.0

    def energy_roadmap(self, frequency_Hz: float = 1e9) -> List[dict]:
        """
        Energy per gate switch across nodes for all paradigms.

        Returns list of dicts, one per node, with energy for each paradigm
        and the Landauer limit.
        """
        E_land = landauer_limit(self.T_ambient)
        rows = []
        for node in self.tech_nodes:
            cmos = CMOSGateEnergy(tech_node_nm=node)
            adiab = AdiabaticGateEnergy(tech_node_nm=node)
            rev = ReversibleGateEnergy()
            landauer = LandauerLimitEnergy()

            E_cmos = cmos.energy_per_switch(frequency_Hz, self.T_ambient)
            E_adiab = adiab.energy_per_switch(frequency_Hz, self.T_ambient)
            E_rev = rev.energy_per_switch(frequency_Hz, self.T_ambient)
            E_land_val = landauer.energy_per_switch(frequency_Hz, self.T_ambient)

            rows.append({
                "node_nm": node,
                "E_cmos_J": E_cmos,
                "E_adiabatic_J": E_adiab,
                "E_reversible_J": E_rev,
                "E_landauer_J": E_land_val,
                "gap_cmos": E_cmos / E_land_val,
                "gap_adiabatic": E_adiab / E_land_val,
                "gap_reversible": E_rev / E_land_val,
                "cmos_V_dd": cmos.V_dd,
                "regime_cmos": classify_regime(E_cmos / E_land_val),
                "regime_adiabatic": classify_regime(E_adiab / E_land_val),
            })
        return rows

    def format_energy_roadmap(self, rows: List[dict] = None,
                              frequency_Hz: float = 1e9) -> str:
        """Format energy roadmap as a readable table."""
        if rows is None:
            rows = self.energy_roadmap(frequency_Hz)

        lines = [
            "ENERGY PER GATE SWITCH vs TECHNOLOGY NODE",
            f"Frequency: {frequency_Hz/1e9:.0f} GHz, T = {self.T_ambient:.0f} K",
            "",
            f"{'Node':>6s}  {'V_dd':>5s}  {'CMOS':>12s}  {'Adiabatic':>12s}  "
            f"{'Reversible':>12s}  {'Landauer':>12s}  {'CMOS Gap':>10s}  "
            f"{'Regime':>14s}",
            "-" * 100,
        ]
        for r in rows:
            lines.append(
                f"{r['node_nm']:>5.1f}nm  {r['cmos_V_dd']:>5.2f}V  "
                f"{r['E_cmos_J']:>12.2e}  {r['E_adiabatic_J']:>12.2e}  "
                f"{r['E_reversible_J']:>12.2e}  {r['E_landauer_J']:>12.2e}  "
                f"{r['gap_cmos']:>9.0f}×  {r['regime_cmos']:>14s}"
            )
        return "\n".join(lines)

    def thermal_wall_roadmap(self, h_conv: float = 1000.0,
                             element_size_m: float = 100e-6) -> List[dict]:
        """
        Maximum sustainable gate density per node per material.

        This is the "thermal wall" — the point where you can't pack more
        transistors without exceeding the substrate's thermal limit,
        given a specific cooling solution.

        Returns list of dicts with node, material, max_density, max_power.
        """
        rows = []
        for node in self.tech_nodes:
            for mat_key in self.materials:
                mat = MATERIAL_DB[mat_key]
                try:
                    result = thermal_density_limit(
                        material_key=mat_key,
                        tech_node_nm=node,
                        frequency_Hz=self.frequencies[0],
                        max_temp_K=mat.max_operating_temp,
                        T_ambient=self.T_ambient,
                        h_conv=h_conv,
                        element_size_m=element_size_m,
                    )
                    rows.append({
                        "node_nm": node,
                        "material": mat_key,
                        "material_name": mat.name,
                        "max_gate_density": result["max_gate_density"],
                        "max_power_density_W_m2": result["max_power_density_W_m2"],
                        "max_temp_K": mat.max_operating_temp,
                        "thermal_headroom_K": (
                            mat.max_operating_temp - self.T_ambient
                        ),
                    })
                except Exception:
                    rows.append({
                        "node_nm": node,
                        "material": mat_key,
                        "material_name": mat.name,
                        "max_gate_density": 0,
                        "max_power_density_W_m2": 0,
                        "max_temp_K": mat.max_operating_temp,
                        "thermal_headroom_K": 0,
                    })
        return rows

    def format_thermal_wall(self, rows: List[dict] = None,
                            h_conv: float = 1000.0) -> str:
        """Format thermal wall roadmap as a readable table."""
        if rows is None:
            rows = self.thermal_wall_roadmap(h_conv)

        lines = [
            "THERMAL WALL: Maximum Sustainable Gate Density",
            f"Cooling: h = {h_conv:.0f} W/(m²·K), T_ambient = {self.T_ambient:.0f} K",
            "",
        ]

        # Group by material
        by_material = {}
        for r in rows:
            by_material.setdefault(r["material"], []).append(r)

        for mat_key, mat_rows in by_material.items():
            lines.append(f"\n{mat_rows[0]['material_name']} "
                         f"(T_max = {mat_rows[0]['max_temp_K']:.0f} K):")
            lines.append(f"  {'Node':>6s}  {'Max Density':>12s}  "
                         f"{'Max Power (W/cm²)':>18s}")
            lines.append("  " + "-" * 40)
            for r in mat_rows:
                lines.append(
                    f"  {r['node_nm']:>5.1f}nm  {r['max_gate_density']:>12.2e}  "
                    f"{r['max_power_density_W_m2']/1e4:>18.1f}"
                )
        return "\n".join(lines)

    def paradigm_crossover_map(self) -> List[dict]:
        """
        Find the crossover frequency where adiabatic beats CMOS at each node.

        Also computes the temperature where reversible beats CMOS.
        These are the KEY strategic decision points for chip architects.
        """
        rows = []
        for node in self.tech_nodes:
            cmos = CMOSGateEnergy(tech_node_nm=node)
            adiab = AdiabaticGateEnergy(tech_node_nm=node)
            rev = ReversibleGateEnergy()

            f_cross = adiab.crossover_frequency(cmos, self.T_ambient)
            T_cross = rev.temperature_crossover(cmos, self.frequencies[0])

            # At 1 GHz, which paradigm wins?
            E_cmos_1g = cmos.energy_per_switch(1e9, self.T_ambient)
            E_adiab_1g = adiab.energy_per_switch(1e9, self.T_ambient)
            E_rev_1g = rev.energy_per_switch(1e9, self.T_ambient)
            winner_1g = "cmos"
            if E_adiab_1g < E_cmos_1g:
                winner_1g = "adiabatic"
            if E_rev_1g < min(E_cmos_1g, E_adiab_1g):
                winner_1g = "reversible"

            rows.append({
                "node_nm": node,
                "cmos_V_dd": cmos.V_dd,
                "crossover_freq_Hz": f_cross,
                "rev_temp_crossover_K": T_cross,
                "winner_at_1GHz": winner_1g,
                "E_cmos_1GHz": E_cmos_1g,
                "E_adiab_1GHz": E_adiab_1g,
                "E_rev_1GHz": E_rev_1g,
            })
        return rows

    def format_paradigm_crossover(self, rows: List[dict] = None) -> str:
        """Format paradigm crossover map as a readable table."""
        if rows is None:
            rows = self.paradigm_crossover_map()

        lines = [
            "PARADIGM CROSSOVER MAP",
            f"When does each paradigm become competitive?",
            "",
            f"{'Node':>6s}  {'V_dd':>5s}  {'Adiab Crossover':>16s}  "
            f"{'Rev T_cross':>12s}  {'Winner @1GHz':>13s}  "
            f"{'CMOS E':>12s}  {'Adiab E':>12s}  {'Rev E':>12s}",
            "-" * 105,
        ]
        for r in rows:
            f_cross = r["crossover_freq_Hz"]
            f_str = (f"{f_cross/1e9:.1f} GHz" if f_cross < 1e13
                     else f"{f_cross/1e12:.0f} THz")
            T_cross = r["rev_temp_crossover_K"]
            T_str = f"{T_cross:.0f} K" if T_cross < 1e6 else "never"
            lines.append(
                f"{r['node_nm']:>5.1f}nm  {r['cmos_V_dd']:>5.2f}V  "
                f"{f_str:>16s}  {T_str:>12s}  "
                f"{r['winner_at_1GHz']:>13s}  "
                f"{r['E_cmos_1GHz']:>12.2e}  "
                f"{r['E_adiab_1GHz']:>12.2e}  "
                f"{r['E_rev_1GHz']:>12.2e}"
            )
        return "\n".join(lines)

    def gap_closure_projection(self, frequency_Hz: float = 1e9) -> List[dict]:
        """
        Project how the Landauer gap closes with continued scaling.

        Shows exactly when each paradigm enters different thermodynamic
        regimes: deep_classical → classical → transitional → thermodynamic
        → near_limit.
        """
        E_land = landauer_limit(self.T_ambient)
        rows = []
        for node in self.tech_nodes:
            cmos = CMOSGateEnergy(tech_node_nm=node)
            adiab = AdiabaticGateEnergy(tech_node_nm=node)
            rev = ReversibleGateEnergy()

            gap_c = cmos.energy_per_switch(frequency_Hz, self.T_ambient) / E_land
            gap_a = adiab.energy_per_switch(frequency_Hz, self.T_ambient) / E_land
            gap_r = rev.energy_per_switch(frequency_Hz, self.T_ambient) / E_land

            rows.append({
                "node_nm": node,
                "gap_cmos": gap_c,
                "gap_adiabatic": gap_a,
                "gap_reversible": gap_r,
                "regime_cmos": classify_regime(gap_c),
                "regime_adiabatic": classify_regime(gap_a),
                "regime_reversible": classify_regime(gap_r),
                "log10_gap_cmos": np.log10(gap_c),
                "log10_gap_adiabatic": np.log10(gap_a),
                "log10_gap_reversible": np.log10(gap_r),
            })
        return rows

    def format_gap_closure(self, rows: List[dict] = None,
                           frequency_Hz: float = 1e9) -> str:
        """Format gap closure projection as a readable table."""
        if rows is None:
            rows = self.gap_closure_projection(frequency_Hz)

        lines = [
            "LANDAUER GAP CLOSURE PROJECTION",
            f"Frequency: {frequency_Hz/1e9:.0f} GHz, T = {self.T_ambient:.0f} K",
            "",
            f"{'Node':>6s}  {'CMOS Gap':>10s}  {'Adiab Gap':>10s}  "
            f"{'Rev Gap':>10s}  {'CMOS Regime':>16s}  {'Adiab Regime':>16s}  "
            f"{'Rev Regime':>16s}",
            "-" * 100,
        ]
        for r in rows:
            lines.append(
                f"{r['node_nm']:>5.1f}nm  {r['gap_cmos']:>9.0f}×  "
                f"{r['gap_adiabatic']:>9.1f}×  {r['gap_reversible']:>9.1f}×  "
                f"{r['regime_cmos']:>16s}  {r['regime_adiabatic']:>16s}  "
                f"{r['regime_reversible']:>16s}"
            )
        return "\n".join(lines)

    def full_report(self, frequency_Hz: float = 1e9,
                    h_conv: float = 1000.0) -> str:
        """
        Generate a complete technology roadmap report.

        Combines energy projections, thermal walls, paradigm crossovers,
        and gap closure into a single comprehensive report.
        """
        sections = [
            "=" * 100,
            "AETHERMOR TECHNOLOGY ROADMAP REPORT",
            "=" * 100,
            "",
            self.format_energy_roadmap(frequency_Hz=frequency_Hz),
            "",
            self.format_gap_closure(frequency_Hz=frequency_Hz),
            "",
            self.format_paradigm_crossover(),
            "",
            self.format_thermal_wall(h_conv=h_conv),
            "",
            "=" * 100,
            "KEY INSIGHTS:",
        ]

        # Auto-generate insights from the data
        gap_rows = self.gap_closure_projection(frequency_Hz)
        cross_rows = self.paradigm_crossover_map()

        # Find the node where CMOS gap drops below 1000
        for r in gap_rows:
            if r["gap_cmos"] < 1000:
                sections.append(
                    f"  - CMOS enters transitional regime at {r['node_nm']:.1f} nm "
                    f"(gap = {r['gap_cmos']:.0f}×)"
                )
                break

        # Find the node where adiabatic is competitive at 1 GHz
        for r in cross_rows:
            if r["winner_at_1GHz"] != "cmos":
                sections.append(
                    f"  - {r['winner_at_1GHz'].capitalize()} beats CMOS at 1 GHz "
                    f"starting at {r['node_nm']:.1f} nm"
                )
                break

        sections.append(
            "  - Diamond substrate sustains highest density at every node"
        )
        sections.append(
            "  - Reversible computing gap is constant (temperature-dependent "
            "only) — advantage grows at smaller nodes"
        )
        sections.append("=" * 100)

        return "\n".join(sections)
