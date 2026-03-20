"""
Fourier-law thermal transport on a discretized 3D lattice.

This module provides physically accurate heat transport for the simulation:
  - Heat generation from gate switching (energy_model + activity)
  - Conduction via Fourier's law: q = -k · ∇T
  - Boundary conditions: convective cooling (Newton's law) or fixed temperature
  - Proper SI units throughout

The discretized heat equation on the lattice:

  ρ·cₚ · dT/dt = k · ∇²T + Q̇

where Q̇ is the volumetric heat generation rate (W/m³).

Hardware researchers can use this to:
  1. Predict thermal hotspot locations for a given chip architecture
  2. Compare substrate materials (Si vs diamond vs SiC)
  3. Evaluate cooling strategies (uniform vs targeted)
  4. Find the compute density limit before thermal runaway
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple
from scipy.ndimage import convolve

from physics.constants import k_B
from physics.materials import Material, MATERIAL_DB


@dataclass
class ThermalBoundaryCondition:
    """
    Boundary condition for the thermal simulation.

    Modes:
      - "convective": Newton's law of cooling: q = h·(T - T_ambient)
      - "fixed": Dirichlet boundary at T_fixed
      - "adiabatic": No heat flow through boundary (dT/dn = 0)
    """
    mode: str = "convective"          # "convective", "fixed", or "adiabatic"
    h_conv: float = 1000.0            # convective heat transfer coeff (W/(m²·K))
    T_ambient: float = 300.0          # ambient temperature (K)
    T_fixed: float = 300.0            # for fixed mode


@dataclass
class FourierThermalTransport:
    """
    3D Fourier-law heat transport engine for lattice simulations.

    Solves the discretized heat equation on a regular grid with
    material-specific thermal properties and realistic boundary conditions.

    This is the core thermal engine that makes the simulation physically
    meaningful. Without it, temperature is just a number; with it,
    temperature reflects real heat transport physics.

    Parameters
    ----------
    grid_shape : tuple
        (Nx, Ny, Nz) lattice dimensions.
    element_size_m : float
        Physical size of each lattice element (m). For a chip simulation,
        this might be 10e-6 (10 μm) to 1e-3 (1 mm).
    material : Material
        Substrate material providing k, ρ, cₚ.
    dt : float
        Time step in seconds. Must satisfy CFL condition for stability.
    boundary : ThermalBoundaryCondition
        Boundary condition specification.
    """
    grid_shape: Tuple[int, int, int] = (60, 60, 10)
    element_size_m: float = 100e-6       # 100 μm per element
    material: Material = None
    dt: float = 1e-6                      # 1 μs time step
    boundary: ThermalBoundaryCondition = None

    def __post_init__(self):
        if self.material is None:
            self.material = MATERIAL_DB["silicon"]
        if self.boundary is None:
            self.boundary = ThermalBoundaryCondition()

        # Derived constants
        self.alpha = self.material.thermal_diffusivity  # m²/s
        self.dx = self.element_size_m                    # m
        self.element_volume = self.dx ** 3               # m³
        self.rho_cp = self.material.volumetric_heat_capacity  # J/(m³·K)

        # CFL stability factor: α·dt/dx² must be < 1/6 for 3D
        self.cfl_number = self.alpha * self.dt / (self.dx ** 2)
        if self.cfl_number > 1.0 / 6.0:
            # Auto-adjust dt for stability instead of crashing
            self.dt = (1.0 / 7.0) * (self.dx ** 2) / self.alpha
            self.cfl_number = self.alpha * self.dt / (self.dx ** 2)

        # 3D Laplacian stencil (6-point)
        self.laplacian = np.zeros((3, 3, 3))
        self.laplacian[1, 1, 0] = 1.0
        self.laplacian[1, 1, 2] = 1.0
        self.laplacian[1, 0, 1] = 1.0
        self.laplacian[1, 2, 1] = 1.0
        self.laplacian[0, 1, 1] = 1.0
        self.laplacian[2, 1, 1] = 1.0
        self.laplacian[1, 1, 1] = -6.0

        # Temperature field (K)
        self.T = np.full(self.grid_shape, self.boundary.T_ambient, dtype=np.float64)

        # Cumulative energy tracking (Joules)
        self.total_heat_generated_J = 0.0
        self.total_heat_removed_J = 0.0
        self.thermal_runaway = False

    def reset(self, T_initial: float = None):
        """Reset temperature field to uniform value."""
        if T_initial is None:
            T_initial = self.boundary.T_ambient
        self.T[:] = T_initial
        self.total_heat_generated_J = 0.0
        self.total_heat_removed_J = 0.0
        self.thermal_runaway = False  # set if temperature goes beyond physical range

    def inject_heat(self, heat_W_per_m3: np.ndarray):
        """
        Apply volumetric heat generation to the temperature field.

        Parameters
        ----------
        heat_W_per_m3 : ndarray
            Volumetric heat generation rate at each element (W/m³).
            Shape must match grid_shape.
        """
        # ΔT = Q̇ · dt / (ρ · cₚ)
        dT = heat_W_per_m3 * self.dt / self.rho_cp
        self.T += dT
        self.total_heat_generated_J += float(np.sum(heat_W_per_m3)) * self.element_volume * self.dt

        # Detect thermal runaway (beyond any physical chip scenario)
        if np.any(~np.isfinite(self.T)) or np.any(self.T > 1e6):
            self.thermal_runaway = True
            self.T = np.clip(self.T, 0.0, 1e6)
            self.T[~np.isfinite(self.T)] = 1e6

    def inject_heat_watts(self, heat_W: np.ndarray):
        """
        Apply heat generation in Watts per element (not per m³).

        Parameters
        ----------
        heat_W : ndarray
            Heat generation rate at each element (W). Shape must match grid_shape.
        """
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            heat_W_per_m3 = heat_W / self.element_volume
        self.inject_heat(heat_W_per_m3)

    def conduct(self):
        """
        Advance thermal conduction by one time step using Fourier's law.

        Uses explicit Euler integration of:
          dT/dt = α · ∇²T

        where α = k/(ρ·cₚ) is thermal diffusivity and ∇² is the discrete Laplacian.

        Boundary handling for the Laplacian:
          - convective: mode='constant' with cval=T_ambient. This models the chip
            conductively coupled to a thermal reservoir (package/heatsink) at
            T_ambient — the dominant cooling path in real chip packages. The
            separate apply_boundary_cooling() adds surface convection on top.
          - fixed: mode='constant' with cval=T_fixed (Dirichlet boundary).
          - adiabatic: mode='nearest' (zero gradient — no heat leakage).
        """
        bc = self.boundary
        if bc.mode == "adiabatic":
            conv_mode = "nearest"
            conv_cval = 0.0  # unused for 'nearest'
        elif bc.mode == "fixed":
            conv_mode = "constant"
            conv_cval = bc.T_fixed
        else:
            # Convective: chip is conductively coupled to a thermal reservoir
            # at T_ambient (heat sink / package substrate). This is the dominant
            # cooling mechanism in real chip packages.
            conv_mode = "constant"
            conv_cval = bc.T_ambient

        laplacian_T = convolve(self.T, self.laplacian, mode=conv_mode,
                               cval=conv_cval)
        dT_conduction = (self.alpha * self.dt / (self.dx ** 2)) * laplacian_T
        self.T += dT_conduction

        # Track energy exchanged through boundary conduction (Dirichlet BC).
        # Interior conduction is conservative: for every element that loses
        # heat to a neighbour, that neighbour gains the same amount. So the
        # pairwise interior contributions sum to zero across the whole grid.
        # The only net contribution comes from the ghost cells at T_ambient.
        # Therefore: sum(dT_conduction over all elements) = boundary flux.
        if bc.mode in ("convective", "fixed"):
            boundary_loss_J = (
                -float(np.sum(dT_conduction)) * self.rho_cp * self.element_volume
            )
            if boundary_loss_J > 0:
                self.total_heat_removed_J += boundary_loss_J

    def apply_boundary_cooling(self):
        """
        Apply boundary condition cooling on all six faces of the lattice.
        """
        bc = self.boundary

        if bc.mode == "fixed":
            # Dirichlet: clamp boundary elements to T_fixed
            self.T[0, :, :] = bc.T_fixed
            self.T[-1, :, :] = bc.T_fixed
            self.T[:, 0, :] = bc.T_fixed
            self.T[:, -1, :] = bc.T_fixed
            self.T[:, :, 0] = bc.T_fixed
            self.T[:, :, -1] = bc.T_fixed

        elif bc.mode == "convective":
            # Newton's law of cooling on boundary faces
            # q = h · (T_surface - T_ambient)
            # ΔT = -h · (T - T_amb) · dt · A / (ρ·cₚ·V)
            # where A/V = 1/dx for a boundary element
            cool_rate = bc.h_conv * self.dt / (self.rho_cp * self.dx)

            for face in [
                (slice(0, 1), slice(None), slice(None)),
                (slice(-1, None), slice(None), slice(None)),
                (slice(None), slice(0, 1), slice(None)),
                (slice(None), slice(-1, None), slice(None)),
                (slice(None), slice(None), slice(0, 1)),
                (slice(None), slice(None), slice(-1, None)),
            ]:
                dT = cool_rate * (self.T[face] - bc.T_ambient)
                heat_removed = float(np.sum(dT)) * self.rho_cp * self.element_volume
                self.total_heat_removed_J += max(0.0, heat_removed)
                self.T[face] -= dT

        # "adiabatic" mode: do nothing (zero gradient at boundary)

    def step(self, heat_generation_W: Optional[np.ndarray] = None):
        """
        Advance the thermal simulation by one time step.

        Parameters
        ----------
        heat_generation_W : ndarray or None
            Heat generation per element in Watts. Shape = grid_shape.
            If None, only conduction and cooling occur.
        """
        if heat_generation_W is not None:
            self.inject_heat_watts(heat_generation_W)
        self.conduct()
        self.apply_boundary_cooling()

    # -----------------------------------------------------------------
    # Analysis helpers for research
    # -----------------------------------------------------------------

    def hotspot_map(self) -> np.ndarray:
        """
        Temperature elevation above ambient at each element.

        Use this to identify thermal bottlenecks.
        """
        return self.T - self.boundary.T_ambient

    def max_temperature(self) -> float:
        """Peak temperature anywhere in the lattice (K)."""
        return float(np.max(self.T))

    def mean_temperature(self) -> float:
        """Mean temperature across the lattice (K)."""
        return float(np.mean(self.T))

    def thermal_gradient_magnitude(self) -> np.ndarray:
        """
        Magnitude of the temperature gradient at each element (K/m).

        Large gradients indicate steep thermal slopes — potential for
        thermal stress and reliability concerns.
        """
        gx = np.gradient(self.T, self.dx, axis=0)
        gy = np.gradient(self.T, self.dx, axis=1)
        gz = np.gradient(self.T, self.dx, axis=2)
        return np.sqrt(gx**2 + gy**2 + gz**2)

    def energy_balance(self) -> dict:
        """
        Return cumulative energy balance for validation.

        The difference between generated and removed energy should
        approximately equal the thermal energy stored in the lattice
        (conservation of energy check).
        """
        T_excess = self.T - self.boundary.T_ambient
        stored_J = float(np.sum(T_excess)) * self.rho_cp * self.element_volume
        return {
            "generated_J": self.total_heat_generated_J,
            "removed_J": self.total_heat_removed_J,
            "stored_J": stored_J,
            "balance_error_J": self.total_heat_generated_J - self.total_heat_removed_J - stored_J,
        }

    def steady_state_temperature(
        self,
        heat_generation_W: np.ndarray,
        max_steps: int = 10000,
        tol: float = 0.01,
    ) -> np.ndarray:
        """
        Run until steady state (temperature change < tol per step).

        Returns the steady-state temperature field.

        Parameters
        ----------
        heat_generation_W : ndarray
            Constant heat generation per element (W).
        max_steps : int
            Maximum iterations before giving up.
        tol : float
            Convergence tolerance (max |ΔT| per step).

        Returns
        -------
        ndarray
            Steady-state temperature field.
        """
        for i in range(max_steps):
            T_prev = self.T.copy()
            self.step(heat_generation_W)
            max_dT = float(np.max(np.abs(self.T - T_prev)))
            if max_dT < tol:
                break
        return self.T.copy()
