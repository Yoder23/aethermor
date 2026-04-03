# physics/ — Physical foundation for thermodynamic computing simulation
#
# This package grounds the Aethermor simulation in real SI-unit physics:
#   - constants: Boltzmann, Landauer limit, Planck, etc.
#   - materials: Thermal properties of real substrates (Si, GaAs, graphene, etc.)
#   - energy_models: Gate switching energy at various technology nodes
#   - thermal: Heat transport via Fourier's law on a discretized lattice
#   - cooling: Full cooling stack model (die → TIM → IHS → heatsink → ambient)
#   - chip_floorplan: Heterogeneous chip architecture definition
#
# Extensibility:
#   All three core registries are importable from this package:
#     from physics import registry          # MaterialRegistry
#     from physics import paradigm_registry # ParadigmRegistry
#     from physics import cooling_registry  # CoolingRegistry

from aethermor.physics.constants import k_B, LANDAUER_LIMIT, h_PLANCK, E_CHARGE
from aethermor.physics.materials import (
    Material, MATERIAL_DB,
    registry, register_material, unregister_material,
    get_material, list_materials,
    validate_material, material_from_dict, material_to_dict,
)
from aethermor.physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
    EnergyModel,
    paradigm_registry, register_paradigm,
)
from aethermor.physics.thermal import FourierThermalTransport
from aethermor.physics.cooling import (
    CoolingStack, ThermalLayer, THERMAL_LAYERS,
    cooling_registry, register_cooling_layer,
    validate_layer, layer_from_dict, layer_to_dict,
)
from aethermor.physics.chip_floorplan import ChipFloorplan, FunctionalBlock

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("aethermor")
except Exception:
    __version__ = "1.0.1"
