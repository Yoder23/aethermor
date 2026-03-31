"""Aethermor — chip thermal analysis, cooling tradeoffs, and compute-density limits."""

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("aethermor")
except Exception:
    __version__ = "1.0.1"

# Convenience re-exports for clean top-level access:
#   from aethermor import ThermalOptimizer, CoolingStack, ChipFloorplan
from aethermor.physics.constants import k_B, LANDAUER_LIMIT, h_PLANCK, E_CHARGE
from aethermor.physics.materials import (
    Material,
    MATERIAL_DB,
    registry,
    register_material,
    unregister_material,
    get_material,
    list_materials,
    validate_material,
)
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
    EnergyModel,
    paradigm_registry,
    register_paradigm,
)
from aethermor.physics.thermal import FourierThermalTransport
from aethermor.physics.cooling import (
    CoolingStack,
    ThermalLayer,
    THERMAL_LAYERS,
    cooling_registry,
    register_cooling_layer,
)
from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from aethermor.analysis.thermal_optimizer import ThermalOptimizer
from aethermor.analysis.tech_roadmap import TechnologyRoadmap
