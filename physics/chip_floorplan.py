"""
Heterogeneous chip floorplan — define functional blocks on a 3D lattice.

Real chips are not uniform.  A modern SoC has CPU cores, GPU shader arrays,
memory controllers, I/O pads, and idle silicon — each with dramatically
different power densities and activity patterns.  Thermal hotspots form at
the *boundaries* between high-power and low-power regions, not just at the
highest-power spot.

This module lets researchers:
  1.  Define a chip floorplan with named functional blocks
  2.  Assign each block its own gate density, activity, tech node, and
      computing paradigm (CMOS / adiabatic / reversible)
  3.  Generate per-element heat maps that feed into FourierThermalTransport
  4.  Study how block placement affects thermal coupling and hotspots
  5.  Optimise floorplan placement for thermal balance

No other open-source tool combines Landauer-aware energy models with
heterogeneous chip floorplanning on a 3D thermal solver.

Example
-------
>>> from physics.chip_floorplan import ChipFloorplan, FunctionalBlock
>>> fp = ChipFloorplan(grid_shape=(60, 60, 8), element_size_m=50e-6)
>>> fp.add_block(FunctionalBlock(
...     name="CPU_cluster",
...     x_range=(0, 20), y_range=(0, 20), z_range=(0, 8),
...     gate_density=2e7, activity=0.3, tech_node_nm=5,
...     paradigm="cmos",
... ))
>>> fp.add_block(FunctionalBlock(
...     name="GPU_array",
...     x_range=(20, 60), y_range=(0, 40), z_range=(0, 8),
...     gate_density=5e6, activity=0.6, tech_node_nm=7,
...     paradigm="cmos",
... ))
>>> heat_map = fp.heat_map(frequency_Hz=2e9)
>>> print(fp.summary())
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from physics.constants import landauer_limit
from physics.materials import Material, MATERIAL_DB, get_material
from physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
    paradigm_registry,
)
from physics.thermal import FourierThermalTransport, ThermalBoundaryCondition


@dataclass
class FunctionalBlock:
    """
    A rectangular region of the chip with uniform properties.

    Parameters
    ----------
    name : str
        Human-readable block name (e.g. "CPU_core_0", "SRAM_L2").
    x_range, y_range, z_range : tuple of (int, int)
        Element index ranges (start, stop) — Python-style half-open interval.
    gate_density : float
        Logic gates per element in this block.
    activity : float
        Fraction of gates switching per cycle (0–1).
    tech_node_nm : float
        Technology node for this block (nm). Mixed-node chiplets are
        modeled by assigning different nodes to different blocks.
    paradigm : str
        Energy model: "cmos", "adiabatic", "reversible", "idle",
        or any custom paradigm registered via paradigm_registry.
    """
    name: str
    x_range: Tuple[int, int]
    y_range: Tuple[int, int]
    z_range: Tuple[int, int]
    gate_density: float = 1e6
    activity: float = 0.2
    tech_node_nm: float = 7.0
    paradigm: str = "cmos"

    @property
    def slices(self):
        """NumPy index slices for this block."""
        return (
            slice(self.x_range[0], self.x_range[1]),
            slice(self.y_range[0], self.y_range[1]),
            slice(self.z_range[0], self.z_range[1]),
        )

    @property
    def n_elements(self) -> int:
        """Number of elements in this block."""
        return (
            (self.x_range[1] - self.x_range[0])
            * (self.y_range[1] - self.y_range[0])
            * (self.z_range[1] - self.z_range[0])
        )


@dataclass
class ChipFloorplan:
    """
    Heterogeneous chip floorplan on a 3D lattice.

    Define functional blocks with different power characteristics, then
    generate heat maps, run thermal simulations, and analyze interactions.

    Parameters
    ----------
    grid_shape : tuple
        (Nx, Ny, Nz) lattice dimensions.
    element_size_m : float
        Physical size of each lattice element (m).
    material : str
        Default substrate material key.
    T_ambient : float
        Ambient temperature (K).
    h_conv : float
        Default convective cooling coefficient (W/(m²·K)).
    """
    grid_shape: Tuple[int, int, int] = (60, 60, 8)
    element_size_m: float = 50e-6
    material: str = "silicon"
    T_ambient: float = 300.0
    h_conv: float = 1000.0
    blocks: List[FunctionalBlock] = field(default_factory=list)

    def add_block(self, block: FunctionalBlock) -> 'ChipFloorplan':
        """Add a functional block. Returns self for chaining."""
        # Validate bounds
        Nx, Ny, Nz = self.grid_shape
        if (block.x_range[1] > Nx or block.y_range[1] > Ny
                or block.z_range[1] > Nz):
            raise ValueError(
                f"Block '{block.name}' exceeds grid bounds "
                f"{self.grid_shape}: x={block.x_range}, y={block.y_range}, "
                f"z={block.z_range}"
            )
        self.blocks.append(block)
        return self

    def _energy_model(self, paradigm: str, tech_node_nm: float):
        """Create the appropriate energy model for a paradigm.

        Uses the paradigm registry, so custom paradigms registered via
        ``paradigm_registry.register(name, ModelClass)`` work automatically.
        """
        try:
            return paradigm_registry.create(paradigm, tech_node_nm=tech_node_nm)
        except TypeError:
            # Model class may not accept tech_node_nm — try without
            return paradigm_registry.create(paradigm)

    def heat_map(self, frequency_Hz: float = 1e9,
                 T: float = 300.0) -> np.ndarray:
        """
        Generate per-element heat generation map (W per element).

        Parameters
        ----------
        frequency_Hz : float
            Operating frequency (Hz).
        T : float
            Temperature for leakage estimation (K).

        Returns
        -------
        ndarray of shape grid_shape
            Heat generation in Watts at each element.
        """
        heat = np.zeros(self.grid_shape, dtype=np.float64)
        for block in self.blocks:
            model = self._energy_model(block.paradigm, block.tech_node_nm)
            if model is None:
                continue
            E_switch = model.energy_per_switch(frequency_Hz, T)
            power_per_elem = (
                block.gate_density * block.activity * frequency_Hz * E_switch
            )
            heat[block.slices] += power_per_elem
        return heat

    def gate_density_map(self) -> np.ndarray:
        """Per-element gate density map."""
        density = np.zeros(self.grid_shape, dtype=np.float64)
        for block in self.blocks:
            density[block.slices] = block.gate_density
        return density

    def activity_map(self) -> np.ndarray:
        """Per-element activity factor map."""
        act = np.zeros(self.grid_shape, dtype=np.float64)
        for block in self.blocks:
            act[block.slices] = block.activity
        return act

    def paradigm_map(self) -> np.ndarray:
        """Per-element paradigm ID map.

        Built-in IDs: 0=idle, 1=cmos, 2=adiabatic, 3=reversible.
        Custom paradigms get IDs starting from 4, assigned by the
        paradigm registry in the order they were registered.
        """
        pmap = np.zeros(self.grid_shape, dtype=np.int32)
        for block in self.blocks:
            pmap[block.slices] = paradigm_registry.paradigm_id(block.paradigm)
        return pmap

    def landauer_gap_map(self, frequency_Hz: float = 1e9,
                         T: float = 300.0) -> np.ndarray:
        """
        Per-element Landauer gap map.

        Shows how far each element is from the thermodynamic limit.
        Regions close to Landauer (gap → 1) are near the physics floor;
        regions far from it (gap >> 1) have room for efficiency improvement.
        """
        gap = np.ones(self.grid_shape, dtype=np.float64)
        E_landauer = landauer_limit(T)
        for block in self.blocks:
            model = self._energy_model(block.paradigm, block.tech_node_nm)
            if model is None:
                continue
            E_switch = model.energy_per_switch(frequency_Hz, T)
            gap[block.slices] = E_switch / E_landauer
        return gap

    def simulate(self, frequency_Hz: float = 1e9, steps: int = 500,
                 h_conv: float = None,
                 cooling_stack=None) -> FourierThermalTransport:
        """
        Run a thermal simulation of the heterogeneous chip.

        Parameters
        ----------
        frequency_Hz : float
            Operating frequency (Hz).
        steps : int
            Number of thermal time steps.
        h_conv : float or None
            Override convective coefficient. If None, uses self.h_conv.
        cooling_stack : CoolingStack or None
            If provided, computes effective h_conv from the cooling stack.

        Returns
        -------
        FourierThermalTransport
            The thermal solver after simulation, with temperature field.
        """
        if cooling_stack is not None:
            Nx, Ny, _ = self.grid_shape
            die_area = (Nx * self.element_size_m) * (Ny * self.element_size_m)
            h = cooling_stack.effective_h(die_area)
        elif h_conv is not None:
            h = h_conv
        else:
            h = self.h_conv

        mat = get_material(self.material)
        bc = ThermalBoundaryCondition(
            mode="convective", h_conv=h, T_ambient=self.T_ambient
        )
        thermal = FourierThermalTransport(
            grid_shape=self.grid_shape,
            element_size_m=self.element_size_m,
            material=mat,
            boundary=bc,
        )

        heat = self.heat_map(frequency_Hz, self.T_ambient)
        for _ in range(steps):
            thermal.step(heat)
            if thermal.thermal_runaway:
                break

        return thermal

    def block_temperatures(self, thermal: FourierThermalTransport) -> List[dict]:
        """
        Extract per-block thermal statistics from a simulation result.

        Returns list of dicts with block name, T_max, T_mean, T_min,
        power, and Landauer gap.
        """
        results = []
        for block in self.blocks:
            T_block = thermal.T[block.slices]
            results.append({
                "name": block.name,
                "paradigm": block.paradigm,
                "tech_node_nm": block.tech_node_nm,
                "gate_density": block.gate_density,
                "activity": block.activity,
                "n_elements": block.n_elements,
                "T_max_K": float(np.max(T_block)),
                "T_mean_K": float(np.mean(T_block)),
                "T_min_K": float(np.min(T_block)),
            })
        return results

    def total_power_W(self, frequency_Hz: float = 1e9,
                      T: float = 300.0) -> float:
        """Total chip power (W)."""
        return float(np.sum(self.heat_map(frequency_Hz, T)))

    def die_area_m2(self) -> float:
        """Die area in m² (Nx × Ny × element_size²)."""
        Nx, Ny, _ = self.grid_shape
        return Nx * Ny * self.element_size_m ** 2

    def power_density_W_cm2(self, frequency_Hz: float = 1e9,
                            T: float = 300.0) -> float:
        """Average power density in W/cm²."""
        return self.total_power_W(frequency_Hz, T) / (self.die_area_m2() * 1e4)

    def summary(self, frequency_Hz: float = 1e9, T: float = 300.0) -> str:
        """Human-readable summary of the floorplan and power budget."""
        lines = [
            f"Chip floorplan: {self.grid_shape[0]}×{self.grid_shape[1]}"
            f"×{self.grid_shape[2]} lattice, "
            f"{self.element_size_m*1e6:.0f} μm/element",
            f"Die area: {self.die_area_m2()*1e6:.2f} mm²",
            f"Substrate: {self.material}",
            f"Total power: {self.total_power_W(frequency_Hz, T):.2f} W "
            f"({self.power_density_W_cm2(frequency_Hz, T):.1f} W/cm²)",
            "",
            f"{'Block':<25s} {'Paradigm':<10s} {'Node':>5s} "
            f"{'Density':>10s} {'Activity':>8s} {'Power (W)':>10s}",
            "-" * 75,
        ]
        for block in self.blocks:
            model = self._energy_model(block.paradigm, block.tech_node_nm)
            if model is None:
                power = 0.0
            else:
                E = model.energy_per_switch(frequency_Hz, T)
                power = (block.gate_density * block.activity * frequency_Hz
                         * E * block.n_elements)
            lines.append(
                f"{block.name:<25s} {block.paradigm:<10s} "
                f"{block.tech_node_nm:>4.0f}nm "
                f"{block.gate_density:>10.1e} {block.activity:>8.2f} "
                f"{power:>10.3f}"
            )

        idle_elements = int(np.prod(self.grid_shape)) - sum(
            b.n_elements for b in self.blocks
        )
        if idle_elements > 0:
            lines.append(
                f"{'(idle silicon)':<25s} {'idle':<10s} "
                f"{'---':>5s} {'0':>10s} {'0.00':>8s} {'0.000':>10s}"
            )
        return "\n".join(lines)

    # ── Factory methods for common architectures ──

    @classmethod
    def modern_soc(cls, grid_shape=(60, 60, 8),
                   element_size_m=50e-6) -> 'ChipFloorplan':
        """
        A realistic modern SoC floorplan: CPU cores, GPU, memory, I/O.

        Gate densities are calibrated so that total die power is in the
        50-250 W range for a ~9-36 mm² die with fan-heatsink cooling.
        """
        Nx, Ny, Nz = grid_shape
        fp = cls(grid_shape=grid_shape, element_size_m=element_size_m)

        # CPU cluster (high power density, 4 cores)
        cpu_w = Nx // 4
        fp.add_block(FunctionalBlock(
            name="CPU_cluster",
            x_range=(0, cpu_w), y_range=(0, Ny // 2), z_range=(0, Nz),
            gate_density=5e5, activity=0.3, tech_node_nm=5, paradigm="cmos",
        ))
        # GPU array (moderate density, high activity)
        fp.add_block(FunctionalBlock(
            name="GPU_array",
            x_range=(cpu_w, Nx), y_range=(0, Ny // 2), z_range=(0, Nz),
            gate_density=2e5, activity=0.5, tech_node_nm=7, paradigm="cmos",
        ))
        # L2/L3 cache (low activity)
        fp.add_block(FunctionalBlock(
            name="SRAM_cache",
            x_range=(0, Nx // 2), y_range=(Ny // 2, Ny), z_range=(0, Nz),
            gate_density=3e5, activity=0.05, tech_node_nm=7, paradigm="cmos",
        ))
        # I/O + memory controller
        fp.add_block(FunctionalBlock(
            name="IO_memctrl",
            x_range=(Nx // 2, Nx), y_range=(Ny // 2, Ny), z_range=(0, Nz),
            gate_density=1e4, activity=0.1, tech_node_nm=14, paradigm="cmos",
        ))
        return fp

    @classmethod
    def hybrid_paradigm(cls, grid_shape=(60, 60, 8),
                        element_size_m=50e-6) -> 'ChipFloorplan':
        """
        Hybrid CMOS + adiabatic chip: hot core uses CMOS, periphery uses
        adiabatic logic for lower power.  Research question: how much does
        the paradigm boundary placement affect total chip temperature?
        """
        Nx, Ny, Nz = grid_shape
        fp = cls(grid_shape=grid_shape, element_size_m=element_size_m)

        # Hot CMOS core
        cx, cy = Nx // 4, Ny // 4
        fp.add_block(FunctionalBlock(
            name="CMOS_core",
            x_range=(cx, 3 * cx), y_range=(cy, 3 * cy), z_range=(0, Nz),
            gate_density=5e5, activity=0.3, tech_node_nm=7, paradigm="cmos",
        ))
        # Adiabatic periphery — north
        fp.add_block(FunctionalBlock(
            name="Adiab_north",
            x_range=(0, Nx), y_range=(0, cy), z_range=(0, Nz),
            gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="adiabatic",
        ))
        # Adiabatic periphery — south
        fp.add_block(FunctionalBlock(
            name="Adiab_south",
            x_range=(0, Nx), y_range=(3 * cy, Ny), z_range=(0, Nz),
            gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="adiabatic",
        ))
        # Adiabatic periphery — west
        fp.add_block(FunctionalBlock(
            name="Adiab_west",
            x_range=(0, cx), y_range=(cy, 3 * cy), z_range=(0, Nz),
            gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="adiabatic",
        ))
        # Adiabatic periphery — east
        fp.add_block(FunctionalBlock(
            name="Adiab_east",
            x_range=(3 * cx, Nx), y_range=(cy, 3 * cy), z_range=(0, Nz),
            gate_density=2e5, activity=0.2, tech_node_nm=7, paradigm="adiabatic",
        ))
        return fp
