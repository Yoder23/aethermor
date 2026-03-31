"""
Thermal map analysis — spatial thermal profiling of compute lattices.

Provides tools for analyzing the thermal behavior of chip architectures
simulated on the Aethermor lattice:

  - Hotspot detection and characterization
  - Thermal gradient analysis (stress risk)
  - Cooling efficiency mapping
  - Thermal resistance network extraction

Hardware teams use these to:
  1. Identify thermal bottlenecks in proposed architectures
  2. Evaluate the effectiveness of cooling strategies
  3. Predict where thermal failures will occur first
  4. Guide placement of temperature sensors on physical chips
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from aethermor.physics.thermal import FourierThermalTransport


@dataclass
class HotspotInfo:
    """
    Description of a thermal hotspot in the lattice.

    Attributes
    ----------
    center : tuple
        (x, y, z) coordinates of the hotspot peak.
    peak_temp_K : float
        Peak temperature at the hotspot center.
    extent : int
        Number of elements in the hotspot (above threshold).
    mean_temp_K : float
        Mean temperature within the hotspot.
    gradient_K_per_m : float
        Maximum thermal gradient at the hotspot boundary.
    thermal_risk : str
        "low", "medium", "high", "critical" based on proximity to max_operating_temp.
    """
    center: tuple
    peak_temp_K: float
    extent: int
    mean_temp_K: float
    gradient_K_per_m: float
    thermal_risk: str = "low"


def detect_hotspots(
    temperature_field: np.ndarray,
    T_ambient: float = 300.0,
    threshold_above_ambient: float = 20.0,
    element_size_m: float = 100e-6,
    max_operating_temp: float = 400.0,
) -> List[HotspotInfo]:
    """
    Detect and characterize thermal hotspots in the temperature field.

    A hotspot is a connected region where T > T_ambient + threshold.

    Parameters
    ----------
    temperature_field : ndarray
        3D temperature field (K).
    T_ambient : float
        Ambient temperature (K).
    threshold_above_ambient : float
        Temperature elevation threshold for hotspot detection (K).
    element_size_m : float
        Physical size of each element (m).
    max_operating_temp : float
        Maximum safe operating temperature (K).

    Returns
    -------
    list of HotspotInfo
        Detected hotspots, sorted by peak temperature (descending).
    """
    from scipy.ndimage import label as nd_label

    elevation = temperature_field - T_ambient
    mask = elevation > threshold_above_ambient

    if not mask.any():
        return []

    # Label connected components
    labeled, n_features = nd_label(mask)

    # Compute gradients for thermal stress analysis
    gradients = np.sqrt(sum(
        np.gradient(temperature_field, element_size_m, axis=ax) ** 2
        for ax in range(3)
    ))

    hotspots = []
    for i in range(1, n_features + 1):
        component = labeled == i
        temps = temperature_field[component]
        grads = gradients[component]

        peak_idx = np.argmax(temperature_field * component)
        center = np.unravel_index(peak_idx, temperature_field.shape)
        peak_temp = float(temps.max())

        # Risk classification
        headroom = max_operating_temp - peak_temp
        if headroom < 0:
            risk = "critical"
        elif headroom < 20:
            risk = "high"
        elif headroom < 50:
            risk = "medium"
        else:
            risk = "low"

        hotspots.append(HotspotInfo(
            center=tuple(int(c) for c in center),
            peak_temp_K=peak_temp,
            extent=int(component.sum()),
            mean_temp_K=float(temps.mean()),
            gradient_K_per_m=float(grads.max()),
            thermal_risk=risk,
        ))

    hotspots.sort(key=lambda h: h.peak_temp_K, reverse=True)
    return hotspots


def cooling_efficiency_map(
    thermal: FourierThermalTransport,
    heat_generation_W: np.ndarray,
) -> np.ndarray:
    """
    Compute cooling efficiency at each element.

    Efficiency = (T_element - T_ambient) / (heat_generated_at_element / h_conv)

    Values < 1 mean heat is being conducted away efficiently (good).
    Values > 1 mean heat is accumulating (bad — potential hotspot).

    Parameters
    ----------
    thermal : FourierThermalTransport
        Thermal simulation (should be at or near steady state).
    heat_generation_W : ndarray
        Heat generation per element (W).

    Returns
    -------
    ndarray
        Cooling efficiency at each element. Shape = grid_shape.
    """
    bc = thermal.boundary
    elevation = thermal.T - bc.T_ambient

    # Expected steady-state elevation for isolated elements
    element_area = thermal.dx ** 2
    if bc.mode == "convective" and bc.h_conv > 0:
        expected_elevation = heat_generation_W / (bc.h_conv * element_area)
    else:
        expected_elevation = np.ones_like(elevation)

    # Efficiency ratio: actual / expected
    with np.errstate(divide='ignore', invalid='ignore'):
        efficiency = np.where(
            expected_elevation > 0,
            elevation / np.maximum(expected_elevation, 1e-30),
            0.0,
        )
    return efficiency


def thermal_summary(
    temperature_field: np.ndarray,
    T_ambient: float = 300.0,
    max_operating_temp: float = 400.0,
) -> dict:
    """
    Compute summary thermal statistics for a temperature field.

    Parameters
    ----------
    temperature_field : ndarray
        3D temperature field (K).
    T_ambient : float
        Ambient temperature (K).
    max_operating_temp : float
        Maximum safe operating temperature (K).

    Returns
    -------
    dict with thermal statistics.
    """
    T = temperature_field
    elevation = T - T_ambient

    return {
        "T_min_K": float(T.min()),
        "T_max_K": float(T.max()),
        "T_mean_K": float(T.mean()),
        "T_std_K": float(T.std()),
        "elevation_max_K": float(elevation.max()),
        "elevation_mean_K": float(elevation.mean()),
        "fraction_above_max": float(np.sum(T > max_operating_temp)) / T.size,
        "fraction_within_10pct_max": float(np.sum(T > 0.9 * max_operating_temp)) / T.size,
        "thermal_uniformity": 1.0 - float(T.std()) / max(float(T.mean() - T_ambient), 1e-10),
    }
