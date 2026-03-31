"""
Landauer gap analysis — distance from the thermodynamic limit.

The Landauer gap is the ratio of actual energy dissipated per operation to the
theoretical minimum (k_B · T · ln 2). This is the single most important metric
for thermodynamic computing research: it tells you how much room for improvement
exists at every point in the system.

Key research questions this module answers:
  1. Where in the chip is energy being wasted most? (spatial gap map)
  2. How does the gap scale with technology node? (scaling analysis)
  3. At what temperature does the gap start mattering? (thermal sensitivity)
  4. Which computing paradigm (CMOS/adiabatic/reversible) closes the gap fastest?
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from aethermor.physics.constants import k_B, landauer_limit
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)


@dataclass
class LandauerGapResult:
    """
    Result of a Landauer gap analysis.

    Attributes
    ----------
    gap_ratio : float
        E_actual / E_landauer. 1.0 = at the limit. >1 = room to improve.
    E_actual_J : float
        Actual energy per operation (Joules).
    E_landauer_J : float
        Landauer limit at this temperature (Joules).
    T_kelvin : float
        Temperature used for the calculation.
    wasted_fraction : float
        Fraction of energy above the Landauer minimum: (E_actual - E_min) / E_actual.
    bits_per_joule_actual : float
        How many bit erasures per Joule at this operating point.
    bits_per_joule_limit : float
        Theoretical maximum bit erasures per Joule.
    """
    gap_ratio: float
    E_actual_J: float
    E_landauer_J: float
    T_kelvin: float
    wasted_fraction: float
    bits_per_joule_actual: float
    bits_per_joule_limit: float


def compute_gap(E_actual_J: float, T: float = 300.0) -> LandauerGapResult:
    """
    Compute the Landauer gap for a single operating point.

    Parameters
    ----------
    E_actual_J : float
        Actual energy per irreversible bit operation (Joules).
    T : float
        Operating temperature (Kelvin).

    Returns
    -------
    LandauerGapResult
    """
    E_min = landauer_limit(T)
    gap = E_actual_J / E_min if E_min > 0 else float('inf')
    wasted = max(0.0, (E_actual_J - E_min) / E_actual_J) if E_actual_J > 0 else 0.0

    return LandauerGapResult(
        gap_ratio=gap,
        E_actual_J=E_actual_J,
        E_landauer_J=E_min,
        T_kelvin=T,
        wasted_fraction=wasted,
        bits_per_joule_actual=1.0 / max(E_actual_J, 1e-100),
        bits_per_joule_limit=1.0 / E_min,
    )


def spatial_gap_map(
    energy_per_element_J: np.ndarray,
    temperature_field_K: np.ndarray,
    operations_per_element: np.ndarray,
) -> np.ndarray:
    """
    Compute the Landauer gap at every lattice element.

    This produces a 3D map showing where energy is being wasted most.
    Hardware teams can use this to identify which regions of their chip
    are furthest from the thermodynamic limit and why.

    Parameters
    ----------
    energy_per_element_J : ndarray
        Total energy dissipated at each element (Joules). Shape: grid_shape.
    temperature_field_K : ndarray
        Temperature at each element (Kelvin). Shape: grid_shape.
    operations_per_element : ndarray
        Number of irreversible operations at each element. Shape: grid_shape.

    Returns
    -------
    ndarray
        Landauer gap ratio at each element. Shape: grid_shape.
        Values > 1 mean room for improvement. Higher = more waste.
    """
    # Landauer minimum energy at each element
    E_min_per_op = k_B * temperature_field_K * np.log(2.0)
    E_min_total = E_min_per_op * np.maximum(operations_per_element, 1e-30)

    # Gap ratio
    gap = np.where(
        E_min_total > 0,
        np.maximum(energy_per_element_J, 0.0) / E_min_total,
        0.0,
    )
    return gap


def gap_vs_technology_node(
    tech_nodes_nm: List[float] = None,
    frequency_Hz: float = 1e9,
    T: float = 300.0,
) -> Dict[str, List[dict]]:
    """
    Compare Landauer gap across technology nodes for different paradigms.

    This answers: "How does the gap change as we shrink transistors?"

    CMOS gap generally decreases with smaller nodes (lower C, lower V),
    but leakage increases, creating a complex trade-off.

    Parameters
    ----------
    tech_nodes_nm : list of float
        Technology nodes to evaluate. Default: [130, 65, 45, 28, 14, 7, 3].
    frequency_Hz : float
        Operating frequency (Hz).
    T : float
        Temperature (K).

    Returns
    -------
    dict
        Keyed by paradigm name, values are lists of dicts with
        {node_nm, gap, energy_J, landauer_J}.
    """
    if tech_nodes_nm is None:
        tech_nodes_nm = [130, 65, 45, 28, 14, 7, 3]

    results = {"cmos": [], "adiabatic": []}
    E_min = landauer_limit(T)

    for node in tech_nodes_nm:
        cmos = CMOSGateEnergy(tech_node_nm=node)
        adiabatic = AdiabaticGateEnergy(tech_node_nm=node)

        E_cmos = cmos.energy_per_switch(frequency_Hz, T)
        E_adiab = adiabatic.energy_per_switch(frequency_Hz, T)

        results["cmos"].append({
            "node_nm": node,
            "gap": E_cmos / E_min,
            "energy_J": E_cmos,
            "landauer_J": E_min,
        })
        results["adiabatic"].append({
            "node_nm": node,
            "gap": E_adiab / E_min,
            "energy_J": E_adiab,
            "landauer_J": E_min,
        })

    return results


def gap_vs_temperature(
    energy_model,
    temperatures_K: List[float] = None,
    frequency_Hz: float = 1e9,
) -> List[dict]:
    """
    How does the Landauer gap change with temperature?

    Key insight: the Landauer limit INCREASES with temperature (more thermal
    noise to fight), but CMOS energy is roughly constant. So the gap DECREASES
    at higher T — but that's not good, it means noise is catching up to signal.

    For reversible computing, energy scales WITH temperature, so the gap
    stays roughly constant.

    Parameters
    ----------
    energy_model : object
        Any energy model with .energy_per_switch(frequency, T) method.
    temperatures_K : list of float
        Temperatures to evaluate. Default: 4 K to 600 K.
    frequency_Hz : float
        Operating frequency (Hz).

    Returns
    -------
    list of dict
        Each dict: {T_K, gap, energy_J, landauer_J}.
    """
    if temperatures_K is None:
        temperatures_K = [4, 10, 50, 77, 150, 200, 250, 300, 350, 400, 500, 600]

    results = []
    for T in temperatures_K:
        E_actual = energy_model.energy_per_switch(frequency_Hz, T)
        E_min = landauer_limit(T)
        results.append({
            "T_K": T,
            "gap": E_actual / E_min,
            "energy_J": E_actual,
            "landauer_J": E_min,
        })
    return results


def identify_efficiency_bottlenecks(
    gap_map: np.ndarray,
    threshold: float = 2.0,
) -> dict:
    """
    Identify regions where the Landauer gap exceeds a threshold.

    Returns statistics about the bottleneck regions that hardware teams
    can use to focus optimization efforts.

    Parameters
    ----------
    gap_map : ndarray
        Landauer gap ratio at each element (from spatial_gap_map).
    threshold : float
        Gap ratio above which an element is considered a bottleneck.

    Returns
    -------
    dict
        - fraction_bottleneck: fraction of elements above threshold
        - mean_gap_bottleneck: mean gap in bottleneck regions
        - max_gap: maximum gap anywhere
        - hotspot_coords: coordinates of the worst element
    """
    mask = gap_map > threshold
    indices = np.argwhere(mask)

    result = {
        "fraction_bottleneck": float(mask.sum()) / max(gap_map.size, 1),
        "mean_gap_overall": float(np.mean(gap_map[gap_map > 0])) if np.any(gap_map > 0) else 0.0,
        "mean_gap_bottleneck": float(np.mean(gap_map[mask])) if mask.any() else 0.0,
        "max_gap": float(np.max(gap_map)) if gap_map.size > 0 else 0.0,
        "hotspot_coords": tuple(np.unravel_index(np.argmax(gap_map), gap_map.shape)) if gap_map.size > 0 else None,
    }
    return result
