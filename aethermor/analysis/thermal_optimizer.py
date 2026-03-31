"""
Thermal budget optimiser — find optimal compute density distributions.

This module solves the *inverse problem* that chip architects face:

    Given a power budget, thermal limit, cooling solution, and substrate,
    what is the optimal distribution of compute density across the chip?

Most thermal tools only solve the *forward* problem (given a design →
compute temperature). Aethermor's optimiser works backwards:

    Given constraints → find the best design.

This workflow compression — from manual sweep campaigns to single function
calls — is the core value of Aethermor for architecture-stage exploration.

Capabilities:
  1.  **Max-density finder**: Binary search for the highest uniform density
      a given material + cooling can sustain (3D simulation).
  2.  **Thermal headroom map**: For a heterogeneous floorplan, identify which
      blocks have thermal headroom and which are bottlenecked, with per-block
      recommendations.
  3.  **Power redistribution**: Given a total power budget, optimise gate
      density across functional blocks to maximise throughput under thermal
      and power constraints.
  4.  **Cooling requirement finder**: Given a target density, find the minimum
      cooling coefficient needed (combined conduction + convection model).
  5.  **Material selection advisor**: Rank materials by achievable density
      for a given cooling and power budget.
  6.  **Paradigm comparison**: Compare CMOS vs adiabatic max density.
  7.  **Cooling sweep**: Sweep h_conv to show temperature vs cooling trade-off
      with conduction floor visibility.
  8.  **Full design exploration**: One-call comprehensive analysis combining
      material ranking, max density, cooling, paradigm comparison, and sweep.

Example
-------
>>> from aethermor.analysis.thermal_optimizer import ThermalOptimizer
>>> opt = ThermalOptimizer()
>>> result = opt.find_max_density("silicon", h_conv=1000)
>>> print(f"Max density: {result['max_density']:.2e} gates/element")
>>> print(f"At T_max = {result['T_max_K']:.1f} K")
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from aethermor.physics.constants import landauer_limit
from aethermor.physics.materials import MATERIAL_DB, get_material
from aethermor.physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy
from aethermor.physics.thermal import FourierThermalTransport, ThermalBoundaryCondition
from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock


@dataclass
class ThermalOptimizer:
    """
    Optimiser for thermodynamic computing design decisions.

    Parameters
    ----------
    grid_shape : tuple
        Lattice dimensions for 3D thermal simulations.
    element_size_m : float
        Physical element size (m).
    tech_node_nm : float
        Technology node (nm).
    frequency_Hz : float
        Operating frequency (Hz).
    T_ambient : float
        Ambient temperature (K).
    activity : float
        Gate switching activity factor (0-1).
    thermal_steps : int
        Steps per thermal simulation.
    """
    grid_shape: Tuple[int, int, int] = (20, 20, 5)
    element_size_m: float = 100e-6
    tech_node_nm: float = 7.0
    frequency_Hz: float = 1e9
    T_ambient: float = 300.0
    activity: float = 0.2
    thermal_steps: int = 500

    def _analytical_T_max(self, gate_density: float, material_key: str,
                          h_conv: float, paradigm: str = "cmos") -> float:
        """
        Combined conduction + convection 1D steady-state model.

        Physics: uniform volumetric heating in a slab of thickness dx,
        cooled from one face by convection at h_conv.

            T_max = T_ambient + Q · (1/(h·A) + dx/(2·k·A))

        where Q = power_per_element, A = dx², dx = element_size.

        The 1/(h·A) term captures convective resistance to ambient.
        The dx/(2k·A) term captures conductive resistance through the die.
        Material conductivity k creates a conduction floor: even with
        perfect cooling (h→∞), T_max > T_ambient + Q·dx/(2k·A).

        This gives physically meaningful results for cooling analyses:
        - At low h: convection-limited (T_max ~ 1/h)
        - At high h: conduction-limited (floor set by k)
        - Diminishing returns as h increases
        - Material-dependent behaviour
        """
        mat = get_material(material_key)
        if paradigm == "cmos":
            model = CMOSGateEnergy(tech_node_nm=self.tech_node_nm)
        else:
            model = AdiabaticGateEnergy(tech_node_nm=self.tech_node_nm)

        E_switch = model.energy_per_switch(self.frequency_Hz, self.T_ambient)
        power = gate_density * self.activity * self.frequency_Hz * E_switch
        dx = self.element_size_m
        A = dx ** 2
        k = mat.thermal_conductivity

        R_conv = 1.0 / (h_conv * A)    # convective resistance [K/W]
        R_cond = dx / (2.0 * k * A)    # conductive resistance [K/W]
        return self.T_ambient + power * (R_conv + R_cond)

    def _run_thermal(self, gate_density: float, material_key: str,
                     h_conv: float, density_field: np.ndarray = None,
                     paradigm: str = "cmos") -> FourierThermalTransport:
        """Run a thermal simulation and return the solver."""
        mat = get_material(material_key)

        if paradigm == "cmos":
            model = CMOSGateEnergy(tech_node_nm=self.tech_node_nm)
        else:
            model = AdiabaticGateEnergy(tech_node_nm=self.tech_node_nm)

        E_switch = model.energy_per_switch(self.frequency_Hz, self.T_ambient)

        bc = ThermalBoundaryCondition(
            mode="convective", h_conv=h_conv, T_ambient=self.T_ambient
        )
        thermal = FourierThermalTransport(
            grid_shape=self.grid_shape,
            element_size_m=self.element_size_m,
            material=mat,
            boundary=bc,
        )

        if density_field is not None:
            heat = (density_field * self.activity * self.frequency_Hz
                    * E_switch)
        else:
            heat = np.full(
                self.grid_shape,
                gate_density * self.activity * self.frequency_Hz * E_switch,
            )

        for _ in range(self.thermal_steps):
            thermal.step(heat)
            if thermal.thermal_runaway:
                break

        return thermal

    def find_max_density(self, material_key: str = "silicon",
                         h_conv: float = 1000.0,
                         T_max_target: float = None,
                         paradigm: str = "cmos") -> dict:
        """
        Binary search for the maximum sustainable gate density.

        Uses 3D thermal simulation (not analytical estimate) to find the
        highest density where T_max stays below the material limit.

        Parameters
        ----------
        material_key : str
            Substrate material.
        h_conv : float
            Convective cooling coefficient (W/(m²·K)).
        T_max_target : float or None
            Target maximum temperature. If None, uses material limit.
        paradigm : str
            Energy model ("cmos" or "adiabatic").

        Returns
        -------
        dict with max_density, T_max_K, power_W, power_density_W_cm2,
        landauer_gap, thermal_headroom_K.
        """
        mat = get_material(material_key)
        if T_max_target is None:
            T_max_target = mat.max_operating_temp

        # Binary search
        lo, hi = 1e3, 1e10
        best = {"max_density": 0, "T_max_K": self.T_ambient}

        for _ in range(40):  # ~40 iterations gives 1e-12 precision
            mid = (lo + hi) / 2.0
            thermal = self._run_thermal(mid, material_key, h_conv,
                                        paradigm=paradigm)
            T_max = thermal.max_temperature()

            if thermal.thermal_runaway or T_max > T_max_target:
                hi = mid
            else:
                lo = mid
                best["max_density"] = mid
                best["T_max_K"] = T_max

        # Final simulation at the best density
        thermal = self._run_thermal(best["max_density"], material_key,
                                    h_conv, paradigm=paradigm)
        n_elements = int(np.prod(self.grid_shape))
        die_area_cm2 = (self.grid_shape[0] * self.grid_shape[1]
                        * self.element_size_m ** 2 * 1e4)

        if paradigm == "cmos":
            model = CMOSGateEnergy(tech_node_nm=self.tech_node_nm)
        else:
            model = AdiabaticGateEnergy(tech_node_nm=self.tech_node_nm)

        E_switch = model.energy_per_switch(self.frequency_Hz, best["T_max_K"])
        total_power = (best["max_density"] * self.activity
                       * self.frequency_Hz * E_switch * n_elements)

        best.update({
            "material": material_key,
            "material_name": mat.name,
            "h_conv": h_conv,
            "paradigm": paradigm,
            "power_W": total_power,
            "power_density_W_cm2": total_power / die_area_cm2,
            "landauer_gap": E_switch / landauer_limit(best["T_max_K"]),
            "thermal_headroom_K": mat.max_operating_temp - best["T_max_K"],
            "throughput_ops_s": (best["max_density"] * self.activity
                                * self.frequency_Hz * n_elements),
        })
        return best

    def find_min_cooling(self, material_key: str = "silicon",
                         gate_density: float = 1e7,
                         T_max_target: float = None) -> dict:
        """
        Find the minimum cooling coefficient needed for a target density.

        Uses combined conduction + convection 1D model:
            T_max = T_ambient + Q · (1/(h·A) + dx/(2·k·A))

        Solving for h:
            h_min = Q / (A · (ΔT - Q·dx/(2·k·A)))

        If the conduction floor Q·dx/(2·k·A) already exceeds ΔT,
        then no amount of convective cooling can keep T_max below the
        target — the design is conduction-limited.

        Returns
        -------
        dict with min_h_conv, T_max_K, conduction_floor_K, and cooling
        category description.
        """
        mat = get_material(material_key)
        if T_max_target is None:
            T_max_target = mat.max_operating_temp

        model = CMOSGateEnergy(tech_node_nm=self.tech_node_nm)
        E_switch = model.energy_per_switch(self.frequency_Hz, self.T_ambient)
        power = gate_density * self.activity * self.frequency_Hz * E_switch

        dx = self.element_size_m
        A = dx ** 2
        k = mat.thermal_conductivity
        delta_T = T_max_target - self.T_ambient

        # Conduction floor: even with h → ∞
        delta_T_cond = power * dx / (2.0 * k * A)

        if delta_T_cond >= delta_T:
            return {
                "min_h_conv": float('inf'),
                "material": material_key,
                "gate_density": gate_density,
                "T_max_target_K": T_max_target,
                "conduction_floor_K": self.T_ambient + delta_T_cond,
                "cooling_category": (
                    "impossible: conduction through die already exceeds "
                    f"limit (floor = {self.T_ambient + delta_T_cond:.0f} K, "
                    f"target = {T_max_target:.0f} K). "
                    f"Need higher-k material or lower density."),
                "note": "combined conduction + convection 1D model",
            }

        # h_min from: ΔT = Q/(h·A) + Q·dx/(2·k·A)
        # h_min = Q / (A · (ΔT - ΔT_cond))
        h_min = power / (A * (delta_T - delta_T_cond))

        # Classify cooling requirement
        if h_min < 15:
            category = "natural air convection"
        elif h_min < 150:
            category = "forced air (fan)"
        elif h_min < 2000:
            category = "fan + heatsink"
        elif h_min < 10000:
            category = "liquid cold plate"
        elif h_min < 30000:
            category = "jet impingement / microchannel"
        else:
            category = "beyond practical (requires exotic cooling)"

        return {
            "min_h_conv": h_min,
            "material": material_key,
            "gate_density": gate_density,
            "T_max_target_K": T_max_target,
            "conduction_floor_K": self.T_ambient + delta_T_cond,
            "cooling_category": category,
            "note": "combined conduction + convection 1D model",
        }

    def material_ranking(self, h_conv: float = 1000.0,
                         materials: List[str] = None,
                         paradigm: str = "cmos") -> List[dict]:
        """
        Rank substrate materials by maximum achievable density.

        Returns sorted list (best first) with density, power, headroom.
        """
        if materials is None:
            materials = ["silicon", "diamond", "silicon_carbide",
                         "gallium_arsenide", "gallium_nitride"]

        results = []
        for mat_key in materials:
            r = self.find_max_density(mat_key, h_conv, paradigm=paradigm)
            results.append(r)

        results.sort(key=lambda x: x["max_density"], reverse=True)
        return results

    def format_material_ranking(self, results: List[dict] = None,
                                h_conv: float = 1000.0) -> str:
        """Format material ranking as a readable table."""
        if results is None:
            results = self.material_ranking(h_conv)

        lines = [
            "MATERIAL RANKING BY MAX ACHIEVABLE DENSITY",
            f"Config: {self.tech_node_nm:.0f} nm, {self.frequency_Hz/1e9:.0f} GHz, "
            f"h = {h_conv:.0f} W/(m²·K), activity = {self.activity:.0%}",
            "",
            f"{'Rank':>4s}  {'Material':<30s}  {'Max Density':>12s}  "
            f"{'Power (W)':>10s}  {'W/cm²':>8s}  {'T_max (K)':>9s}  "
            f"{'Headroom':>9s}",
            "-" * 95,
        ]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i:>4d}  {r['material_name']:<30s}  "
                f"{r['max_density']:>12.2e}  {r['power_W']:>10.1f}  "
                f"{r['power_density_W_cm2']:>8.1f}  "
                f"{r['T_max_K']:>9.1f}  {r['thermal_headroom_K']:>8.1f} K"
            )
        if results:
            best = results[0]
            worst = results[-1]
            ratio = best["max_density"] / max(worst["max_density"], 1)
            lines.append(
                f"\n  {best['material_name']} sustains {ratio:.0f}× higher "
                f"density than {worst['material_name']}"
            )
        return "\n".join(lines)

    def cooling_sweep(self, material_key: str = "silicon",
                      gate_density: float = 1e7,
                      h_values: List[float] = None) -> List[dict]:
        """
        Sweep cooling coefficients to show temperature vs cooling trade-off.

        Uses combined conduction + convection 1D model.  Shows diminishing
        returns as h increases and the conduction floor is approached.

        Returns list of dicts with h_conv, T_max, thermal_headroom.
        """
        if h_values is None:
            h_values = [10, 50, 100, 500, 1000, 5000, 10000, 50000]

        mat = get_material(material_key)

        results = []
        for h in h_values:
            T_max = self._analytical_T_max(gate_density, material_key, h)
            runaway = T_max > 2000.0  # unphysical
            results.append({
                "h_conv": h,
                "T_max_K": min(T_max, 9999.0),
                "thermal_headroom_K": mat.max_operating_temp - T_max,
                "runaway": runaway,
                "safe": T_max < mat.max_operating_temp,
                "note": "combined conduction + convection 1D model",
            })
        return results

    def thermal_headroom_map(self, floorplan: ChipFloorplan,
                             frequency_Hz: float = 1e9,
                             h_conv: float = 1000.0,
                             steps: int = 500) -> List[dict]:
        """
        Analyse thermal headroom per block on a heterogeneous floorplan.

        For each functional block, reports:
        - Current T_max and thermal headroom
        - Whether the block is the thermal bottleneck
        - How much MORE density each block could sustain (density headroom)
        - Recommended action (increase density, reduce density, change paradigm)

        Uses the per-element combined conduction + convection analytical
        model for exact steady-state temperatures.  For uniform blocks
        (constant density across elements), the per-element model is exact
        because thermal symmetry eliminates lateral heat flow.

        This solves a problem that takes hours of manual iteration in
        traditional tools: "Where is my thermal budget being wasted?"

        Parameters
        ----------
        floorplan : ChipFloorplan
            Heterogeneous chip architecture.
        frequency_Hz : float
            Operating frequency (Hz).
        h_conv : float
            Convective cooling coefficient (W/(m²·K)).
        steps : int
            Unused (kept for API compatibility). Temperature is computed
            analytically—no simulation convergence required.

        Returns
        -------
        List of dicts per block with T_max, headroom, bottleneck flag,
        density_headroom_factor, and recommended action.
        """
        mat = get_material(floorplan.material)
        T_limit = mat.max_operating_temp
        dx = floorplan.element_size_m
        A = dx ** 2
        k = mat.thermal_conductivity
        R_elem = 1.0 / (h_conv * A) + dx / (2.0 * k * A)

        # Compute per-block analytical temperature
        block_temps = []
        for block in floorplan.blocks:
            model = (CMOSGateEnergy(tech_node_nm=block.tech_node_nm)
                     if block.paradigm == "cmos"
                     else AdiabaticGateEnergy(tech_node_nm=block.tech_node_nm))
            E_switch = model.energy_per_switch(frequency_Hz, self.T_ambient)
            ppg = block.activity * frequency_Hz * E_switch
            Q_elem = block.gate_density * ppg
            T_elem = self.T_ambient + Q_elem * R_elem
            block_temps.append({
                "name": block.name,
                "block": block,
                "ppg": ppg,
                "Q_elem": Q_elem,
                "T_max_K": T_elem,
                "T_mean_K": T_elem,  # uniform → max = mean
            })

        # Find the hottest block = bottleneck
        hottest_T = max(bt["T_max_K"] for bt in block_temps)

        results = []
        for bt in block_temps:
            block = bt["block"]
            headroom = T_limit - bt["T_max_K"]
            is_bottleneck = (bt["T_max_K"] >= hottest_T - 0.1)

            # Density headroom: how much can density increase before
            # hitting the thermal limit?
            if bt["ppg"] > 0 and headroom > 0:
                d_thermal_max = (T_limit - self.T_ambient) / (bt["ppg"] * R_elem)
                density_headroom = d_thermal_max / max(block.gate_density, 1)
            else:
                density_headroom = 1.0

            # Recommend action
            if headroom < 10:
                action = "CRITICAL: reduce density or improve cooling"
            elif headroom < 50:
                action = "near limit — consider paradigm switch or lower density"
            elif density_headroom > 5.0:
                action = f"underutilised — can increase density ~{density_headroom:.0f}×"
            elif density_headroom > 2.0:
                action = f"moderate headroom — can increase density ~{density_headroom:.1f}×"
            else:
                action = "well-utilised"

            results.append({
                "name": bt["name"],
                "paradigm": block.paradigm,
                "gate_density": block.gate_density,
                "T_max_K": bt["T_max_K"],
                "T_mean_K": bt["T_mean_K"],
                "thermal_headroom_K": headroom,
                "is_bottleneck": is_bottleneck,
                "density_headroom_factor": density_headroom,
                "recommended_action": action,
            })

        return results

    def optimize_power_distribution(self, floorplan: ChipFloorplan,
                                    power_budget_W: float,
                                    frequency_Hz: float = 1e9,
                                    h_conv: float = 1000.0,
                                    T_max_limit: float = None,
                                    iterations: int = 20) -> dict:
        """
        Optimise gate density distribution across blocks to maximise
        total throughput under a power budget and thermal limit.

        This is the core inverse-design capability of Aethermor.  It answers:

            "Given my power budget and cooling, how should I distribute
             compute across CPU, GPU, cache, and I/O to maximise total
             throughput without exceeding the thermal limit?"

        Tools like HotSpot solve the forward thermal problem; this solver
        works backwards from constraints to an optimal density distribution.

        Algorithm:
        1. Compute die-level thermal budget from h_conv and die area
        2. Distribute power budget across blocks proportional to element
           count (equal per-element power = equal temperature)
        3. Convert per-block power to gate density
        4. Adjust for block-specific constraints (paradigm, activity)
        5. Report optimised density per block and total throughput

        Uses die-level thermal model: T_die = T_amb + P_total / (h · A_die)
        which correctly accounts for lateral heat spreading.

        Parameters
        ----------
        floorplan : ChipFloorplan
            Heterogeneous chip architecture (will not be modified).
        power_budget_W : float
            Total power budget for the chip (W).
        frequency_Hz : float
            Operating frequency (Hz).
        h_conv : float
            Convective cooling coefficient (W/(m²·K)).
        T_max_limit : float or None
            Maximum allowed temperature (K). Default: material limit.
        iterations : int
            Number of optimisation iterations.

        Returns
        -------
        dict with:
        - optimised_blocks: list of per-block results
        - total_throughput_ops_s: total optimised throughput
        - total_power_W: total power (should be ≤ budget)
        - improvement_ratio: throughput vs original layout
        - iterations_run: number of iterations
        """
        mat = get_material(floorplan.material)
        if T_max_limit is None:
            T_max_limit = mat.max_operating_temp

        dx = floorplan.element_size_m
        A_elem = dx ** 2
        k = mat.thermal_conductivity

        # Per-element thermal resistance (combined conduction + convection).
        # For a uniform region, there is no lateral heat flow by symmetry,
        # so each element cools through its own "chimney" — this model is
        # exact for uniform blocks and conservative for hotspot blocks.
        R_elem = 1.0 / (h_conv * A_elem) + dx / (2.0 * k * A_elem)
        delta_T_budget = T_max_limit - self.T_ambient

        # Compute per-block info and thermal-max density
        block_info = []
        for block in floorplan.blocks:
            model = (CMOSGateEnergy(tech_node_nm=block.tech_node_nm)
                     if block.paradigm == "cmos"
                     else AdiabaticGateEnergy(tech_node_nm=block.tech_node_nm))
            E_switch = model.energy_per_switch(frequency_Hz, self.T_ambient)
            ppg = block.activity * frequency_Hz * E_switch

            # Max density before per-element thermal limit
            if ppg > 0:
                d_thermal = delta_T_budget / (ppg * R_elem)
            else:
                d_thermal = 1e12  # effectively unconstrained

            block_info.append({
                "block": block,
                "E_switch": E_switch,
                "ppg": ppg,
                "d_thermal": d_thermal,
            })

        # Original throughput for comparison
        original_throughput = sum(
            bi["block"].gate_density * bi["block"].activity * frequency_Hz
            * bi["block"].n_elements for bi in block_info
        )

        # Check total power if every block runs at thermal-max density
        P_at_thermal_max = sum(
            bi["d_thermal"] * bi["ppg"] * bi["block"].n_elements
            for bi in block_info
        )

        if P_at_thermal_max <= power_budget_W:
            # Thermally limited: each block at its per-element thermal max
            for bi in block_info:
                bi["d_opt"] = bi["d_thermal"]
            binding = "thermal"
        else:
            # Power limited: scale all blocks proportionally.
            # This preserves equal per-element temperature across the chip,
            # which is LP-optimal when throughput/watt is comparable.
            scale = power_budget_W / P_at_thermal_max
            for bi in block_info:
                bi["d_opt"] = bi["d_thermal"] * scale
            binding = "power"

        # Build results
        optimised_blocks = []
        total_throughput = 0.0
        total_power = 0.0

        for bi in block_info:
            block = bi["block"]
            d = bi["d_opt"]
            pwr = d * bi["ppg"] * block.n_elements
            thr = d * block.activity * frequency_Hz * block.n_elements
            T_elem = self.T_ambient + d * bi["ppg"] * R_elem

            total_throughput += thr
            total_power += pwr

            optimised_blocks.append({
                "name": block.name,
                "paradigm": block.paradigm,
                "original_density": block.gate_density,
                "optimised_density": d,
                "density_change": d / max(block.gate_density, 1),
                "power_W": pwr,
                "throughput_ops_s": thr,
                "T_estimated_K": T_elem,
                "thermal_headroom_K": T_max_limit - T_elem,
            })

        return {
            "optimised_blocks": optimised_blocks,
            "total_throughput_ops_s": total_throughput,
            "total_power_W": total_power,
            "power_budget_W": power_budget_W,
            "thermal_power_limit_W": P_at_thermal_max,
            "binding_constraint": binding,
            "improvement_ratio": total_throughput / max(original_throughput, 1),
        }

    def full_design_exploration(self, material_key: str = "silicon",
                                h_conv: float = 1000.0,
                                power_budget_W: float = 200.0,
                                T_max_limit: float = None) -> dict:
        """
        Run a complete design exploration — the one-call answer to:
        "Given my constraints, what's the best I can do?"

        Combines every analysis capability:
        1. Material ranking (which substrate is best?)
        2. Max density search (how far can I push it?)
        3. Cooling requirements (what cooling do I need?)
        4. Paradigm comparison (CMOS vs adiabatic?)
        5. Cooling sweep (how does temperature respond to cooling changes?)

        This is the function a researcher runs first to understand their
        entire design space in one shot.

        Returns
        -------
        dict with keys: material_ranking, best_material, max_density,
        cooling_requirement, paradigm_comparison, cooling_sweep, summary.
        """
        mat = get_material(material_key)
        if T_max_limit is None:
            T_max_limit = mat.max_operating_temp

        # 1. Material ranking
        ranking = self.material_ranking(h_conv=h_conv)

        # 2. Max density for the target material
        max_dens = self.find_max_density(material_key, h_conv,
                                         T_max_target=T_max_limit)

        # 3. Cooling needed for a moderate density
        target_density = max_dens["max_density"] * 0.5  # 50% of max
        cooling_req = self.find_min_cooling(
            material_key, gate_density=target_density,
            T_max_target=T_max_limit,
        )

        # 4. Paradigm comparison
        paradigm = self.paradigm_density_comparison(material_key, h_conv)

        # 5. Cooling sweep
        sweep = self.cooling_sweep(material_key, gate_density=target_density)

        # Summary insights
        best_mat = ranking[0]
        adiab_ratio = paradigm["adiabatic_advantage_ratio"]

        insights = []
        insights.append(
            f"Best material: {best_mat['material_name']} "
            f"({best_mat['max_density']:.2e} gates/elem at h={h_conv})"
        )
        insights.append(
            f"On {mat.name}: max density = {max_dens['max_density']:.2e} "
            f"gates/elem → {max_dens['power_W']:.0f} W, "
            f"T_max = {max_dens['T_max_K']:.0f} K"
        )
        if adiab_ratio > 2.0:
            insights.append(
                f"Adiabatic logic offers {adiab_ratio:.0f}× density advantage "
                f"over CMOS at {self.frequency_Hz/1e9:.0f} GHz"
            )
        if cooling_req["min_h_conv"] < float('inf'):
            insights.append(
                f"For {target_density:.1e} gates/elem: need h ≥ "
                f"{cooling_req['min_h_conv']:.0f} ({cooling_req['cooling_category']})"
            )

        # Safe h_conv values from sweep
        safe_points = [s for s in sweep if s["safe"]]
        if safe_points:
            min_safe_h = min(s["h_conv"] for s in safe_points)
            insights.append(
                f"Minimum safe cooling at half-max density: h = {min_safe_h}"
            )

        return {
            "material_ranking": ranking,
            "best_material": best_mat,
            "max_density": max_dens,
            "cooling_requirement": cooling_req,
            "paradigm_comparison": paradigm,
            "cooling_sweep": sweep,
            "insights": insights,
        }

    def paradigm_density_comparison(self, material_key: str = "silicon",
                                    h_conv: float = 1000.0) -> dict:
        """
        Compare max density achievable with CMOS vs adiabatic paradigm.

        This answers: "How much MORE compute can I pack if I switch from
        CMOS to adiabatic logic?"
        """
        cmos = self.find_max_density(material_key, h_conv, paradigm="cmos")
        adiab = self.find_max_density(material_key, h_conv, paradigm="adiabatic")

        ratio = adiab["max_density"] / max(cmos["max_density"], 1)
        return {
            "cmos": cmos,
            "adiabatic": adiab,
            "adiabatic_advantage_ratio": ratio,
            "material": material_key,
            "h_conv": h_conv,
        }
