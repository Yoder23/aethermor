"""
Regime mapping — identify where thermodynamic effects dominate.

In computing systems, there are two fundamentally different operating regimes:

1. CLASSICAL regime: Energy dissipation is dominated by circuit-level losses
   (V²·C switching, interconnect resistance, leakage). The Landauer limit is
   irrelevant — you're so far above it that thermodynamic considerations
   don't affect design decisions.

2. THERMODYNAMIC regime: Energy dissipation approaches the Landauer limit.
   Thermal noise becomes a design constraint. Reversible computing, adiabatic
   logic, and thermodynamic optimization strategies become relevant.

The boundary between these regimes depends on:
  - Technology node (smaller → closer to thermodynamic regime)
  - Temperature (higher → higher Landauer limit → regime boundary shifts)
  - Operating frequency (lower → adiabatic logic becomes viable)
  - Compute density (higher → thermal management dominates)

This module maps these regime boundaries, answering the question:
"Under what conditions does thermodynamic computing become necessary?"

This is arguably the most important question for hardware research teams,
because it tells them WHEN to invest in thermodynamic computing approaches
vs. when classical optimization is sufficient.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from aethermor.physics.constants import k_B, landauer_limit, thermal_energy
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)


@dataclass
class RegimeBoundary:
    """
    A point on the boundary between classical and thermodynamic regimes.

    Attributes
    ----------
    parameter_name : str
        The parameter being varied (e.g. "tech_node_nm", "temperature_K").
    parameter_value : float
        The value at which the regime transition occurs.
    gap_at_boundary : float
        The Landauer gap at the boundary (typically ~10-100).
    classical_side : str
        Description of the classical side.
    thermodynamic_side : str
        Description of the thermodynamic side.
    """
    parameter_name: str
    parameter_value: float
    gap_at_boundary: float
    classical_side: str = ""
    thermodynamic_side: str = ""


def classify_regime(landauer_gap: float) -> str:
    """
    Classify the operating regime based on Landauer gap.

    Categories:
      - "deep_classical": gap > 10⁶ — Landauer limit completely irrelevant
      - "classical": 10³ < gap ≤ 10⁶ — noticeable but not limiting
      - "transitional": 10 < gap ≤ 10³ — thermodynamic effects relevant
      - "thermodynamic": 1 < gap ≤ 10 — near the limit, TC strategies matter
      - "near_limit": gap ≤ 1 — at or below theoretical minimum (error or reversible)
    """
    if landauer_gap > 1e6:
        return "deep_classical"
    elif landauer_gap > 1e3:
        return "classical"
    elif landauer_gap > 10:
        return "transitional"
    elif landauer_gap > 1:
        return "thermodynamic"
    else:
        return "near_limit"


def regime_map_vs_node_and_frequency(
    tech_nodes: List[float] = None,
    frequencies: List[float] = None,
    T: float = 300.0,
) -> Dict[str, np.ndarray]:
    """
    Map the computing regime across (tech_node, frequency) space.

    Returns matrices showing the Landauer gap and regime classification
    for every (node, frequency) combination.

    This is a fundamental research tool: it shows exactly where in the
    design space thermodynamic computing approaches become relevant.

    Parameters
    ----------
    tech_nodes : list of float
        Technology nodes in nm. Default: 3 to 130 nm.
    frequencies : list of float
        Operating frequencies in Hz. Default: 10 MHz to 1 THz.
    T : float
        Temperature (K).

    Returns
    -------
    dict with keys:
      - "tech_nodes": 1D array of node values
      - "frequencies": 1D array of frequency values
      - "cmos_gap": 2D array [node × freq] of Landauer gaps for CMOS
      - "adiabatic_gap": 2D array [node × freq] of gaps for adiabatic
      - "cmos_regime": 2D array [node × freq] of regime strings
      - "adiabatic_regime": 2D array [node × freq] of regime strings
    """
    if tech_nodes is None:
        tech_nodes = [3, 5, 7, 10, 14, 22, 28, 45, 65, 90, 130]
    if frequencies is None:
        frequencies = [1e7, 1e8, 5e8, 1e9, 5e9, 1e10, 5e10, 1e11, 5e11, 1e12]

    nodes = np.array(tech_nodes, dtype=float)
    freqs = np.array(frequencies, dtype=float)

    cmos_gap = np.zeros((len(nodes), len(freqs)))
    adiab_gap = np.zeros((len(nodes), len(freqs)))
    cmos_regime = np.empty((len(nodes), len(freqs)), dtype=object)
    adiab_regime = np.empty((len(nodes), len(freqs)), dtype=object)

    for i, node in enumerate(nodes):
        cmos = CMOSGateEnergy(tech_node_nm=node)
        adiab = AdiabaticGateEnergy(tech_node_nm=node)
        for j, freq in enumerate(freqs):
            cg = cmos.landauer_gap(T, freq)
            ag = adiab.landauer_gap(T, freq)
            cmos_gap[i, j] = cg
            adiab_gap[i, j] = ag
            cmos_regime[i, j] = classify_regime(cg)
            adiab_regime[i, j] = classify_regime(ag)

    return {
        "tech_nodes": nodes,
        "frequencies": freqs,
        "cmos_gap": cmos_gap,
        "adiabatic_gap": adiab_gap,
        "cmos_regime": cmos_regime,
        "adiabatic_regime": adiab_regime,
    }


def find_crossover_node(
    frequency_Hz: float = 1e9,
    T: float = 300.0,
    gap_threshold: float = 100.0,
) -> Optional[float]:
    """
    Find the technology node (nm) where the Landauer gap drops below a threshold.

    Below this node, thermodynamic computing strategies start to matter.

    Parameters
    ----------
    frequency_Hz : float
        Operating frequency (Hz).
    T : float
        Temperature (K).
    gap_threshold : float
        Gap threshold for "thermodynamic regime". Default: 100.

    Returns
    -------
    float or None
        Technology node in nm where gap ≈ threshold, or None if not found.
    """
    # Search from large to small nodes
    nodes = np.linspace(1, 200, 1000)
    for node in reversed(nodes):
        cmos = CMOSGateEnergy(tech_node_nm=node)
        gap = cmos.landauer_gap(T, frequency_Hz)
        if gap <= gap_threshold:
            return float(node)
    return None


def thermal_density_limit(
    material_key: str = "silicon",
    tech_node_nm: float = 7.0,
    frequency_Hz: float = 1e9,
    max_temp_K: float = 400.0,
    T_ambient: float = 300.0,
    h_conv: float = 1000.0,
    element_size_m: float = 100e-6,
) -> dict:
    """
    Find the maximum sustainable gate density before thermal runaway.

    This answers: "How many gates per element can I pack before the chip
    overheats?" — one of the most practical questions in chip design.

    Uses a 1D steady-state thermal model:
      T_max = T_ambient + Q / (h_conv · A)
    where Q = n_gates · frequency · E_gate and A = element surface area.

    Parameters
    ----------
    material_key : str
        Substrate material.
    tech_node_nm : float
        Technology node.
    frequency_Hz : float
        Operating frequency (Hz).
    max_temp_K : float
        Maximum allowable temperature (K).
    T_ambient : float
        Ambient temperature (K).
    h_conv : float
        Convective cooling coefficient (W/(m²·K)).
    element_size_m : float
        Element size (m).

    Returns
    -------
    dict with keys:
      - max_gate_density: maximum gates per element
      - max_power_density_W_m2: maximum power per unit area
      - energy_per_gate_J: energy per gate at this operating point
      - temp_headroom_K: temperature headroom (max_temp - T_ambient)
    """
    energy_model = CMOSGateEnergy(tech_node_nm=tech_node_nm)
    E_gate = energy_model.energy_per_switch(frequency_Hz, T_ambient)

    temp_headroom = max_temp_K - T_ambient
    if temp_headroom <= 0:
        return {"max_gate_density": 0, "max_power_density_W_m2": 0,
                "energy_per_gate_J": E_gate, "temp_headroom_K": 0}

    # Max heat flux that cooling can handle: q = h · ΔT (W/m²)
    max_heat_flux = h_conv * temp_headroom

    # Max power per element: P = q · A where A = element_size² (one face)
    element_area = element_size_m ** 2
    max_power_per_element = max_heat_flux * element_area

    # Max gate density: n = P / (f · E_gate)
    power_per_gate = frequency_Hz * E_gate
    if power_per_gate <= 0:
        max_gates = float('inf')
    else:
        max_gates = max_power_per_element / power_per_gate

    return {
        "max_gate_density": max_gates,
        "max_power_density_W_m2": max_heat_flux,
        "energy_per_gate_J": E_gate,
        "temp_headroom_K": temp_headroom,
    }


def paradigm_comparison(
    T: float = 300.0,
    frequencies: List[float] = None,
) -> Dict[str, List[dict]]:
    """
    Compare CMOS, adiabatic, and reversible paradigms across frequencies.

    Shows the crossover points where each paradigm becomes optimal.
    This is the central research question for thermodynamic computing.

    Returns
    -------
    dict keyed by paradigm name → list of {freq, energy_J, gap, regime}.
    """
    if frequencies is None:
        frequencies = [1e6, 1e7, 1e8, 1e9, 5e9, 1e10, 1e11, 1e12]

    cmos = CMOSGateEnergy(tech_node_nm=7)
    adiab = AdiabaticGateEnergy(tech_node_nm=7)
    rev = ReversibleGateEnergy()
    landauer = LandauerLimitEnergy()

    results = {"cmos": [], "adiabatic": [], "reversible": [], "landauer": []}

    for freq in frequencies:
        for name, model in [("cmos", cmos), ("adiabatic", adiab),
                            ("reversible", rev), ("landauer", landauer)]:
            E = model.energy_per_switch(freq, T)
            gap = model.landauer_gap(T, freq)
            results[name].append({
                "frequency_Hz": freq,
                "energy_J": E,
                "gap": gap,
                "regime": classify_regime(gap),
            })

    return results
