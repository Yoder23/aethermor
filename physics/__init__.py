# physics/ — Physical foundation for thermodynamic computing simulation
#
# This package grounds the Aethermor simulation in real SI-unit physics:
#   - constants: Boltzmann, Landauer limit, Planck, etc.
#   - materials: Thermal properties of real substrates (Si, GaAs, graphene, etc.)
#   - energy_models: Gate switching energy at various technology nodes
#   - thermal: Heat transport via Fourier's law on a discretized lattice
#   - cooling: Full cooling stack model (die → TIM → IHS → heatsink → ambient)
#   - chip_floorplan: Heterogeneous chip architecture definition

from physics.constants import k_B, LANDAUER_LIMIT, h_PLANCK, E_CHARGE
from physics.materials import Material, MATERIAL_DB
from physics.energy_models import (
    CMOSGateEnergy,
    AdiabaticGateEnergy,
    ReversibleGateEnergy,
    LandauerLimitEnergy,
)
from physics.thermal import FourierThermalTransport
from physics.cooling import CoolingStack, ThermalLayer, THERMAL_LAYERS
from physics.chip_floorplan import ChipFloorplan, FunctionalBlock
