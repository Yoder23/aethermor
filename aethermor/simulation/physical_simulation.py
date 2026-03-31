"""
Physically-grounded thermodynamic computing simulation.

This module bridges the Aethermor lattice simulation framework with the
physics/ package, producing simulations parameterized in SI units with
real material properties, gate energy models, and Fourier thermal transport.

Unlike the original AethermorSimV2 (which uses abstract units), this
simulation tracks:
  - Energy in Joules (not arbitrary "compute_cost" units)
  - Temperature in Kelvin governed by Fourier's law with real k, ρ, cₚ
  - Gate switching energy from technology-node-specific CMOS models
  - Landauer gap at every element, every timestep
  - Heat generation tied to actual gate switching activity

This makes the simulation useful for hardware research because:
  1. You can change the substrate material and see real thermal consequences
  2. You can change the technology node and see how energy/temperature scale
  3. You can compare CMOS vs adiabatic vs reversible computing strategies
  4. Results produce quantitative design guidelines, not just relative rankings

Usage:
    sim = PhysicalSimulation(
        grid_shape=(40, 40, 8),
        material="silicon",
        tech_node_nm=7,
        frequency_Hz=1e9,
        gate_density=1e5,
    )
    sim.run()
    print(sim.summary())
"""

import numpy as np
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List

from aethermor.physics.constants import k_B, landauer_limit
from aethermor.physics.materials import Material, MATERIAL_DB, get_material
from aethermor.physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy, ReversibleGateEnergy
from aethermor.physics.thermal import FourierThermalTransport, ThermalBoundaryCondition


@dataclass
class PhysicalSimConfig:
    """
    Configuration for a physically-grounded simulation.

    All parameters have physical meaning and SI units.
    Hardware researchers should parameterize these based on their target
    architecture.

    Parameters
    ----------
    grid_shape : tuple
        (Nx, Ny, Nz) lattice dimensions.
    element_size_m : float
        Physical size of each compute element (m).
        Typical: 10 μm (10e-6) for on-chip, 1 mm (1e-3) for chiplet.
    material : str or Material
        Substrate material key or Material instance.
    tech_node_nm : float
        Technology node (nm). Determines gate switching energy.
    frequency_Hz : float
        Operating frequency (Hz).
    gate_density : float
        Number of logic gates per element.
    energy_paradigm : str
        "cmos", "adiabatic", or "reversible".
    steps : int
        Number of simulation time steps.
    T_ambient : float
        Ambient temperature (K).
    h_conv : float
        Convective cooling coefficient (W/(m²·K)).
        Typical: 100 (natural air), 1000 (forced air), 10000 (liquid).
    activity_factor : float
        Fraction of gates switching per cycle (0-1). Typical: 0.1-0.3.
    fault_injection : bool
        Whether to inject random faults during simulation.
    fault_rate : float
        Probability of an element faulting per step (if fault_injection=True).
    seed : int
        Random seed for reproducibility.
    """
    grid_shape: Tuple[int, int, int] = (40, 40, 8)
    element_size_m: float = 100e-6       # 100 μm
    material: str = "silicon"
    tech_node_nm: float = 7.0
    frequency_Hz: float = 1e9            # 1 GHz
    gate_density: float = 1e5            # 100k gates per element
    energy_paradigm: str = "cmos"        # "cmos", "adiabatic", "reversible"
    steps: int = 200
    T_ambient: float = 300.0             # Room temperature
    h_conv: float = 1000.0               # Forced air cooling
    activity_factor: float = 0.2         # 20% switching activity
    fault_injection: bool = False
    fault_rate: float = 0.001
    seed: int = 42


class PhysicalSimulation:
    """
    Physically-grounded thermodynamic computing lattice simulation.

    Each lattice element represents a tile of compute with:
      - A specific gate count and technology node
      - Real energy dissipation per operation
      - Temperature governed by Fourier's law with material-specific properties
      - Landauer gap tracking (distance from thermodynamic limit)

    The simulation answers questions like:
      - Where do thermal hotspots form?
      - At what compute density does temperature exceed safe limits?
      - How does changing the substrate material affect the thermal profile?
      - What is the energy efficiency relative to the Landauer limit?
    """

    def __init__(self, config: PhysicalSimConfig = None, **kwargs):
        """
        Initialize the simulation.

        Can be created with a PhysicalSimConfig or keyword arguments:
            sim = PhysicalSimulation(tech_node_nm=14, material="diamond")
        """
        if config is None:
            config = PhysicalSimConfig(**kwargs)
        self.config = config

        # RNG
        self.rng = np.random.default_rng(config.seed)

        # Material
        if isinstance(config.material, str):
            self.material = get_material(config.material)
        else:
            self.material = config.material

        # Energy model
        if config.energy_paradigm == "cmos":
            self.energy_model = CMOSGateEnergy(tech_node_nm=config.tech_node_nm)
        elif config.energy_paradigm == "adiabatic":
            self.energy_model = AdiabaticGateEnergy(tech_node_nm=config.tech_node_nm)
        elif config.energy_paradigm == "reversible":
            self.energy_model = ReversibleGateEnergy()
        else:
            raise ValueError(f"Unknown paradigm: {config.energy_paradigm}")

        # Thermal engine
        bc = ThermalBoundaryCondition(
            mode="convective",
            h_conv=config.h_conv,
            T_ambient=config.T_ambient,
        )
        self.thermal = FourierThermalTransport(
            grid_shape=config.grid_shape,
            element_size_m=config.element_size_m,
            material=self.material,
            boundary=bc,
        )

        # Per-element state
        Nx, Ny, Nz = config.grid_shape
        self.n_elements = Nx * Ny * Nz

        # Activity: fraction of gates switching per cycle at each element
        self.activity = np.full(config.grid_shape, config.activity_factor, dtype=np.float64)

        # Faulted elements (0 = healthy, 1 = faulted)
        self.faulted = np.zeros(config.grid_shape, dtype=np.float64)

        # Cumulative metrics
        self.total_operations = 0.0
        self.total_energy_J = 0.0
        self.total_landauer_min_J = 0.0

        # Time series
        self.metrics_history: List[dict] = []

    def _compute_heat_generation(self) -> np.ndarray:
        """
        Compute heat generation (W) at each element for this timestep.

        heat = gate_density × activity × frequency × E_per_switch × (1 - faulted)
        """
        cfg = self.config
        T_local = self.thermal.T

        # Energy per switch depends on local temperature (for leakage)
        # Use mean temperature for efficiency (per-element would be expensive)
        T_mean = float(np.mean(T_local))
        E_switch = self.energy_model.energy_per_switch(cfg.frequency_Hz, T_mean)

        # Heat per element (W) = gates × activity × frequency × E_switch
        heat_W = (cfg.gate_density * self.activity * cfg.frequency_Hz * E_switch
                  * (1.0 - self.faulted))
        return heat_W

    def _inject_faults(self, step: int):
        """Randomly fault elements based on temperature (hotter = more likely)."""
        if not self.config.fault_injection:
            return

        # Fault probability increases with temperature above ambient
        T_excess = np.maximum(self.thermal.T - self.config.T_ambient, 0.0)
        # Arrhenius-like: probability ∝ exp(α · ΔT)
        alpha = 0.01  # temperature sensitivity
        fault_prob = self.config.fault_rate * np.exp(alpha * T_excess)
        fault_prob = np.clip(fault_prob, 0, 1)

        new_faults = self.rng.random(self.config.grid_shape) < fault_prob
        # Only fault healthy elements
        self.faulted = np.maximum(self.faulted, new_faults.astype(np.float64))

    def _record_metrics(self, step: int, heat_W: np.ndarray):
        """Record per-step metrics for analysis."""
        cfg = self.config
        T_field = self.thermal.T
        T_mean = float(np.mean(T_field))

        # Operations this step
        ops_this_step = float(np.sum(
            cfg.gate_density * self.activity * cfg.frequency_Hz
            * (1.0 - self.faulted)
        )) * self.thermal.dt

        # Energy this step
        energy_this_step = float(np.sum(heat_W)) * self.thermal.dt

        # Landauer minimum for this step
        landauer_min = landauer_limit(T_mean) * ops_this_step

        self.total_operations += ops_this_step
        self.total_energy_J += energy_this_step
        self.total_landauer_min_J += landauer_min

        # Landauer gap (run-average)
        gap = self.total_energy_J / max(self.total_landauer_min_J, 1e-100)

        self.metrics_history.append({
            "step": step,
            "T_max_K": float(np.max(T_field)),
            "T_mean_K": T_mean,
            "T_min_K": float(np.min(T_field)),
            "total_power_W": float(np.sum(heat_W)),
            "energy_per_op_J": energy_this_step / max(ops_this_step, 1e-100),
            "landauer_gap": gap,
            "landauer_min_J_step": landauer_min,
            "operations_step": ops_this_step,
            "energy_step_J": energy_this_step,
            "faulted_fraction": float(np.mean(self.faulted)),
            "cumulative_energy_J": self.total_energy_J,
            "cumulative_operations": self.total_operations,
        })

    def step(self, t: int):
        """Advance the simulation by one timestep."""
        # 1. Compute heat generation from gate switching
        heat_W = self._compute_heat_generation()

        # 2. Thermal simulation step (heat injection + conduction + cooling)
        self.thermal.step(heat_W)

        # 3. Inject faults (temperature-dependent)
        self._inject_faults(t)

        # 4. Record metrics
        self._record_metrics(t, heat_W)

    def run(self) -> 'PhysicalSimulation':
        """Run the full simulation.

        Stops early if thermal runaway is detected (temperature diverges
        beyond any physically meaningful range).
        """
        for t in range(self.config.steps):
            self.step(t)
            if self.thermal.thermal_runaway:
                break
        return self

    def summary(self) -> dict:
        """
        Return a summary of the simulation results.

        This is what hardware researchers look at first: the key numbers
        that characterize the thermal and energy behavior of the system.
        """
        if not self.metrics_history:
            return {"error": "No simulation steps run yet."}

        last = self.metrics_history[-1]
        cfg = self.config

        E_switch = self.energy_model.energy_per_switch(cfg.frequency_Hz, last["T_mean_K"])
        E_landauer = landauer_limit(last["T_mean_K"])

        return {
            # Configuration echo
            "material": self.material.name,
            "tech_node_nm": cfg.tech_node_nm,
            "frequency_GHz": cfg.frequency_Hz / 1e9,
            "gate_density": cfg.gate_density,
            "paradigm": cfg.energy_paradigm,
            "grid_shape": list(cfg.grid_shape),
            "element_size_um": cfg.element_size_m * 1e6,
            "cooling_W_m2K": cfg.h_conv,

            # Thermal results
            "T_max_K": last["T_max_K"],
            "T_mean_K": last["T_mean_K"],
            "T_ambient_K": cfg.T_ambient,
            "thermal_headroom_K": self.material.max_operating_temp - last["T_max_K"],

            # Energy results
            "energy_per_gate_switch_J": E_switch,
            "landauer_limit_J": E_landauer,
            "landauer_gap": last["landauer_gap"],
            "total_power_W": last["total_power_W"],
            "power_density_W_cm2": last["total_power_W"] / (
                cfg.grid_shape[0] * cfg.grid_shape[1] * cfg.element_size_m ** 2 * 1e4
            ),

            # Reliability
            "faulted_fraction": last["faulted_fraction"],

            # Cumulative
            "total_energy_J": self.total_energy_J,
            "total_operations": self.total_operations,
            "simulation_steps": cfg.steps,

            # Stability
            "thermal_runaway": self.thermal.thermal_runaway,
        }

    def compare_paradigms(self) -> Dict[str, dict]:
        """
        Run the same configuration with CMOS, adiabatic, and reversible
        paradigms and compare results.

        Returns a dict keyed by paradigm name with summary for each.
        """
        results = {}
        for paradigm in ["cmos", "adiabatic", "reversible"]:
            cfg = PhysicalSimConfig(
                grid_shape=self.config.grid_shape,
                element_size_m=self.config.element_size_m,
                material=self.config.material,
                tech_node_nm=self.config.tech_node_nm,
                frequency_Hz=self.config.frequency_Hz,
                gate_density=self.config.gate_density,
                energy_paradigm=paradigm,
                steps=self.config.steps,
                T_ambient=self.config.T_ambient,
                h_conv=self.config.h_conv,
                activity_factor=self.config.activity_factor,
                seed=self.config.seed,
            )
            sim = PhysicalSimulation(config=cfg)
            sim.run()
            results[paradigm] = sim.summary()
        return results

    def compare_materials(self, material_keys: List[str] = None) -> Dict[str, dict]:
        """
        Run the same configuration with different substrate materials
        and compare thermal behavior.

        Returns a dict keyed by material name with summary for each.
        """
        if material_keys is None:
            material_keys = ["silicon", "diamond", "silicon_carbide", "gallium_arsenide"]

        results = {}
        for mat_key in material_keys:
            cfg = PhysicalSimConfig(
                grid_shape=self.config.grid_shape,
                element_size_m=self.config.element_size_m,
                material=mat_key,
                tech_node_nm=self.config.tech_node_nm,
                frequency_Hz=self.config.frequency_Hz,
                gate_density=self.config.gate_density,
                energy_paradigm=self.config.energy_paradigm,
                steps=self.config.steps,
                T_ambient=self.config.T_ambient,
                h_conv=self.config.h_conv,
                activity_factor=self.config.activity_factor,
                seed=self.config.seed,
            )
            sim = PhysicalSimulation(config=cfg)
            sim.run()
            results[mat_key] = sim.summary()
        return results
