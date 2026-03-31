"""
Design space exploration — parameter sweeps and Pareto frontier extraction.

This module systematically explores the design space that hardware teams
care about: given a chip architecture (material, density, cooling, paradigm),
what trade-offs exist between energy, throughput, reliability, and temperature?

The key output is a Pareto frontier: the set of configurations where you
cannot improve one metric without worsening another. This tells hardware
teams exactly where the interesting design decisions lie.

Research questions this module answers:
  1. What is the Pareto frontier of energy vs. throughput for a given material?
  2. At what compute density do thermal failures spike?
  3. How does the optimal configuration change with substrate material?
  4. What cooling coefficient is needed to sustain a target compute density?
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
import itertools
import json

from aethermor.physics.constants import k_B, landauer_limit
from aethermor.physics.materials import Material, MATERIAL_DB
from aethermor.physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
from aethermor.physics.thermal import FourierThermalTransport, ThermalBoundaryCondition


@dataclass
class DesignPoint:
    """
    A single point in the design space with its evaluated metrics.

    Attributes
    ----------
    params : dict
        Input parameters (tech_node_nm, grid_size, frequency, etc.)
    metrics : dict
        Evaluated output metrics (energy_per_op, max_temp, throughput, etc.)
    pareto_rank : int
        Pareto dominance rank (0 = non-dominated = on the frontier).
    """
    params: dict
    metrics: dict
    pareto_rank: int = -1  # -1 = not yet ranked

    def dominates(self, other: 'DesignPoint', minimize: List[str] = None) -> bool:
        """
        Does this point Pareto-dominate the other?

        A point dominates if it is ≤ in all objectives and < in at least one.
        """
        if minimize is None:
            minimize = list(self.metrics.keys())

        at_least_one_better = False
        for key in minimize:
            if key not in self.metrics or key not in other.metrics:
                continue
            if self.metrics[key] > other.metrics[key]:
                return False
            if self.metrics[key] < other.metrics[key]:
                at_least_one_better = True
        return at_least_one_better


def extract_pareto_frontier(
    points: List[DesignPoint],
    minimize: List[str],
) -> List[DesignPoint]:
    """
    Extract the Pareto-non-dominated set from a list of design points.

    Parameters
    ----------
    points : list of DesignPoint
        All evaluated design points.
    minimize : list of str
        Names of metrics to minimize (e.g. ["energy_per_op", "max_temp"]).

    Returns
    -------
    list of DesignPoint
        The Pareto frontier (non-dominated points), with pareto_rank = 0.
    """
    frontier = []
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if i != j and q.dominates(p, minimize):
                dominated = True
                break
        if not dominated:
            p.pareto_rank = 0
            frontier.append(p)
    return frontier


@dataclass
class DesignSpaceSweep:
    """
    Systematic parameter sweep over the design space.

    Sweeps over combinations of:
      - Technology node (nm)
      - Operating frequency (Hz)
      - Compute density (gates per element)
      - Substrate material
      - Cooling coefficient

    For each combination, runs a thermal steady-state simulation and
    evaluates: energy per operation, max temperature, throughput (ops/s),
    Landauer gap, and reliability estimate.

    Parameters
    ----------
    grid_shape : tuple
        Lattice dimensions (Nx, Ny, Nz).
    element_size_m : float
        Physical size per element (m).
    tech_nodes : list of float
        Technology nodes to sweep (nm).
    frequencies : list of float
        Operating frequencies to sweep (Hz).
    gate_densities : list of float
        Gates per element to sweep.
    materials : list of str
        Material keys from MATERIAL_DB to sweep.
    h_conv_values : list of float
        Convective cooling coefficients to sweep (W/(m²·K)).
    T_ambient : float
        Ambient temperature (K).
    thermal_steps : int
        Number of thermal simulation steps per design point.
    """
    grid_shape: Tuple[int, int, int] = (20, 20, 5)
    element_size_m: float = 100e-6
    tech_nodes: List[float] = field(default_factory=lambda: [7, 14, 28])
    frequencies: List[float] = field(default_factory=lambda: [1e9, 5e9, 10e9])
    gate_densities: List[float] = field(default_factory=lambda: [1e4, 1e5, 1e6])
    materials: List[str] = field(default_factory=lambda: ["silicon", "diamond", "silicon_carbide"])
    h_conv_values: List[float] = field(default_factory=lambda: [500, 1000, 5000])
    T_ambient: float = 300.0
    thermal_steps: int = 500

    def _evaluate_point(
        self,
        tech_node: float,
        frequency: float,
        gate_density: float,
        material_key: str,
        h_conv: float,
    ) -> DesignPoint:
        """
        Evaluate a single design point by running thermal simulation.
        """
        mat = MATERIAL_DB[material_key]
        energy_model = CMOSGateEnergy(tech_node_nm=tech_node)

        # Energy per gate switch
        E_gate = energy_model.energy_per_switch(frequency, self.T_ambient)

        # Heat generation per element: gates × frequency × energy_per_switch
        heat_per_element_W = gate_density * frequency * E_gate

        # Run thermal simulation
        bc = ThermalBoundaryCondition(h_conv=h_conv, T_ambient=self.T_ambient)
        thermal = FourierThermalTransport(
            grid_shape=self.grid_shape,
            element_size_m=self.element_size_m,
            material=mat,
            boundary=bc,
        )

        heat_field = np.full(self.grid_shape, heat_per_element_W)
        # Run to approximate steady state
        for _ in range(self.thermal_steps):
            thermal.step(heat_field)

        max_temp = thermal.max_temperature()
        mean_temp = thermal.mean_temperature()

        # Throughput: total operations per second
        n_elements = np.prod(self.grid_shape)
        throughput_ops_per_s = gate_density * frequency * n_elements

        # Total power (W)
        total_power_W = heat_per_element_W * n_elements

        # Energy per operation
        energy_per_op = E_gate

        # Landauer gap at mean operating temperature
        gap = energy_model.landauer_gap(mean_temp, frequency)

        # Reliability estimate: fraction of elements below max operating temp
        reliable_fraction = float(np.sum(thermal.T < mat.max_operating_temp)) / n_elements

        params = {
            "tech_node_nm": tech_node,
            "frequency_Hz": frequency,
            "gate_density": gate_density,
            "material": material_key,
            "h_conv": h_conv,
        }
        metrics = {
            "energy_per_op_J": energy_per_op,
            "max_temp_K": max_temp,
            "mean_temp_K": mean_temp,
            "throughput_ops_per_s": throughput_ops_per_s,
            "total_power_W": total_power_W,
            "landauer_gap": gap,
            "reliable_fraction": reliable_fraction,
        }

        return DesignPoint(params=params, metrics=metrics)

    def run(self, progress_callback: Optional[Callable] = None) -> List[DesignPoint]:
        """
        Run the full design space sweep.

        Parameters
        ----------
        progress_callback : callable, optional
            Called with (current_index, total_count) for progress tracking.

        Returns
        -------
        list of DesignPoint
            All evaluated design points.
        """
        combos = list(itertools.product(
            self.tech_nodes,
            self.frequencies,
            self.gate_densities,
            self.materials,
            self.h_conv_values,
        ))
        total = len(combos)
        results = []

        for i, (node, freq, density, mat, h) in enumerate(combos):
            point = self._evaluate_point(node, freq, density, mat, h)
            results.append(point)
            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def run_and_extract_pareto(
        self,
        minimize: List[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Tuple[List[DesignPoint], List[DesignPoint]]:
        """
        Run sweep and extract Pareto frontier.

        Parameters
        ----------
        minimize : list of str
            Metrics to minimize. Default: ["energy_per_op_J", "max_temp_K"].
        progress_callback : callable, optional
            Progress callback.

        Returns
        -------
        tuple of (all_points, pareto_frontier)
        """
        if minimize is None:
            minimize = ["energy_per_op_J", "max_temp_K"]

        all_points = self.run(progress_callback)
        frontier = extract_pareto_frontier(all_points, minimize)
        return all_points, frontier


def export_results_csv(points: List[DesignPoint], filepath: str):
    """Export design points to CSV for analysis in external tools."""
    import csv
    if not points:
        return

    param_keys = sorted(points[0].params.keys())
    metric_keys = sorted(points[0].metrics.keys())
    headers = param_keys + metric_keys + ["pareto_rank"]

    with open(filepath, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for p in points:
            row = {**p.params, **p.metrics, "pareto_rank": p.pareto_rank}
            writer.writerow(row)


def export_results_json(points: List[DesignPoint], filepath: str):
    """Export design points to JSON."""
    data = []
    for p in points:
        data.append({
            "params": p.params,
            "metrics": {k: float(v) for k, v in p.metrics.items()},
            "pareto_rank": p.pareto_rank,
        })
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
