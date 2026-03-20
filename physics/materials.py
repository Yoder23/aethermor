"""
Material properties database for thermodynamic computing substrates.

Each material provides the thermal and electrical properties needed to
simulate realistic heat transport and energy dissipation on a chip.

Hardware researchers can:
- Select a substrate material to see how thermal conductivity affects hotspots.
- Compare Si vs GaAs vs diamond vs graphene for heat spreading capability.
- Parameterize custom materials for novel substrates under investigation.

All values at 300 K unless noted. Sources: CRC Handbook, Ioffe Institute data.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import math


@dataclass(frozen=True)
class Material:
    """
    Thermal and electrical properties of a substrate material.

    Attributes
    ----------
    name : str
        Human-readable material name.
    thermal_conductivity : float
        Thermal conductivity k (W/(m·K)). Higher = better heat spreading.
    specific_heat : float
        Specific heat capacity c_p (J/(kg·K)).
    density : float
        Mass density ρ (kg/m³).
    electrical_resistivity : float
        Electrical resistivity (Ω·m). Inf for insulators.
    max_operating_temp : float
        Maximum recommended operating temperature (K).
    bandgap_eV : float
        Electronic bandgap (eV). 0 for metals.
    notes : str
        Additional context for researchers.
    """
    name: str
    thermal_conductivity: float    # W/(m·K)
    specific_heat: float           # J/(kg·K)
    density: float                 # kg/m³
    electrical_resistivity: float  # Ω·m
    max_operating_temp: float      # K
    bandgap_eV: float = 0.0
    notes: str = ""

    @property
    def thermal_diffusivity(self) -> float:
        """
        Thermal diffusivity α = k / (ρ · c_p)  [m²/s].

        This determines how fast temperature disturbances propagate.
        Higher α → faster thermal equilibration → fewer hotspots.
        """
        return self.thermal_conductivity / (self.density * self.specific_heat)

    @property
    def volumetric_heat_capacity(self) -> float:
        """
        Volumetric heat capacity C = ρ · c_p  [J/(m³·K)].

        Energy needed to raise 1 m³ of material by 1 K.
        """
        return self.density * self.specific_heat

    def temp_rise_per_joule(self, volume_m3: float) -> float:
        """
        Temperature rise (K) from depositing 1 Joule into a given volume.

        ΔT = Q / (ρ · c_p · V)

        Parameters
        ----------
        volume_m3 : float
            Volume of the element in m³.

        Returns
        -------
        float
            Temperature increase in Kelvin.
        """
        return 1.0 / (self.volumetric_heat_capacity * volume_m3)


# -------------------------------------------------------------------------
# Material database — curated for thermodynamic computing research
# -------------------------------------------------------------------------

MATERIAL_DB: Dict[str, Material] = {
    "silicon": Material(
        name="Silicon (Si)",
        thermal_conductivity=148.0,
        specific_heat=700.0,
        density=2330.0,
        electrical_resistivity=6.4e2,  # intrinsic; doped Si is much lower
        max_operating_temp=450.0 + 273.15,
        bandgap_eV=1.12,
        notes="Dominant semiconductor. Thermal conductivity drops ~T⁻¹·³ above 300 K.",
    ),
    "silicon_dioxide": Material(
        name="Silicon Dioxide (SiO₂)",
        thermal_conductivity=1.4,
        specific_heat=730.0,
        density=2200.0,
        electrical_resistivity=1e16,
        max_operating_temp=1400.0 + 273.15,
        bandgap_eV=9.0,
        notes="Primary gate dielectric. Very poor thermal conductor — creates thermal barriers.",
    ),
    "gallium_arsenide": Material(
        name="Gallium Arsenide (GaAs)",
        thermal_conductivity=55.0,
        specific_heat=330.0,
        density=5320.0,
        electrical_resistivity=3.3e8,
        max_operating_temp=350.0 + 273.15,
        bandgap_eV=1.42,
        notes="Higher electron mobility than Si. Worse thermal conductivity.",
    ),
    "diamond": Material(
        name="Diamond (C)",
        thermal_conductivity=2200.0,
        specific_heat=520.0,
        density=3510.0,
        electrical_resistivity=1e16,
        max_operating_temp=700.0 + 273.15,
        bandgap_eV=5.47,
        notes="Highest thermal conductivity of any bulk material. Ideal heat spreader.",
    ),
    "graphene_layer": Material(
        name="Graphene (monolayer, in-plane)",
        thermal_conductivity=5000.0,   # in-plane; cross-plane is ~6 W/m·K
        specific_heat=700.0,
        density=2267.0,  # graphite bulk; monolayer is sheet-like
        electrical_resistivity=1e-8,
        max_operating_temp=700.0 + 273.15,
        bandgap_eV=0.0,  # semimetal
        notes="Extreme in-plane conductivity. Cross-plane is ~1000× worse. "
              "Useful for lateral heat spreading in 2D architectures.",
    ),
    "copper": Material(
        name="Copper (Cu)",
        thermal_conductivity=401.0,
        specific_heat=385.0,
        density=8960.0,
        electrical_resistivity=1.68e-8,
        max_operating_temp=400.0 + 273.15,
        bandgap_eV=0.0,
        notes="Standard interconnect metal. Excellent thermal and electrical conductor.",
    ),
    "indium_phosphide": Material(
        name="Indium Phosphide (InP)",
        thermal_conductivity=68.0,
        specific_heat=310.0,
        density=4810.0,
        electrical_resistivity=4.6e7,
        max_operating_temp=400.0 + 273.15,
        bandgap_eV=1.35,
        notes="Used in high-frequency and optoelectronic devices. "
              "Moderate thermal properties.",
    ),
    "silicon_carbide": Material(
        name="Silicon Carbide (4H-SiC)",
        thermal_conductivity=490.0,
        specific_heat=690.0,
        density=3210.0,
        electrical_resistivity=1e6,
        max_operating_temp=600.0 + 273.15,
        bandgap_eV=3.26,
        notes="Wide bandgap, high thermal conductivity. Excellent for high-temp operation.",
    ),
    "gallium_nitride": Material(
        name="Gallium Nitride (GaN)",
        thermal_conductivity=130.0,
        specific_heat=490.0,
        density=6150.0,
        electrical_resistivity=1e10,
        max_operating_temp=600.0 + 273.15,
        bandgap_eV=3.40,
        notes="Wide bandgap. Power electronics and high-frequency applications.",
    ),
}


def get_material(name: str) -> Material:
    """
    Look up a material by key (case-insensitive, underscores optional).

    Raises KeyError with helpful message listing available materials.
    """
    key = name.lower().replace(" ", "_").replace("-", "_")
    if key in MATERIAL_DB:
        return MATERIAL_DB[key]
    raise KeyError(
        f"Unknown material '{name}'. Available: {sorted(MATERIAL_DB.keys())}"
    )


def list_materials() -> Dict[str, Material]:
    """Return the full material database."""
    return dict(MATERIAL_DB)
