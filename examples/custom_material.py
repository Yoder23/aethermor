#!/usr/bin/env python3
"""
Example: Register and test custom materials, paradigms, and cooling layers.

This shows the full extensibility of Aethermor -- how to add your own
substrate materials, computing paradigms, and thermal interface layers
so they work seamlessly throughout the framework.

Run:
    python examples/custom_material.py
"""

import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass
from physics.materials import registry, Material, get_material, validate_material
from physics.materials import material_to_dict, material_from_dict
from physics.energy_models import paradigm_registry, EnergyModel
from physics.cooling import cooling_registry, ThermalLayer, CoolingStack
from physics.constants import landauer_limit
from physics.chip_floorplan import ChipFloorplan, FunctionalBlock
from analysis.thermal_optimizer import ThermalOptimizer


# ── 1.  Register a custom substrate material ─────────────────────────

print("=" * 60)
print("1.  Register a custom material")
print("=" * 60)

# Hexagonal boron nitride: emerging 2D insulator
registry.register("hex_bn", Material(
    name="Hexagonal Boron Nitride (h-BN)",
    thermal_conductivity=600.0,      # W/(m*K)  in-plane; ~30 cross-plane
    specific_heat=800.0,             # J/(kg*K)
    density=2100.0,                  # kg/m³
    electrical_resistivity=1e15,     # Ohm*m (wide-gap insulator)
    max_operating_temp=1000 + 273.15,  # K
    bandgap_eV=6.0,
    notes="2D insulator, high in-plane thermal conductivity."
))

# Verify it's available everywhere
mat = get_material("hex_bn")
print(f"  Material: {mat.name}")
print(f"  k = {mat.thermal_conductivity} W/(m*K)")
print(f"  alpha = {mat.thermal_diffusivity:.2e} m^2/s")
print(f"  Validation: {validate_material(mat)}")
print()

# You can also register from a dictionary (e.g. loaded from a config file):
registry.register("aluminum_nitride", {
    "name": "Aluminum Nitride (AlN)",
    "thermal_conductivity": 285.0,
    "specific_heat": 740.0,
    "density": 3260.0,
    "electrical_resistivity": 1e13,
    "max_operating_temp": 1100 + 273.15,
    "bandgap_eV": 6.2,
    "notes": "Ceramic substrate for power electronics packaging."
})
print(f"  Also registered: {get_material('aluminum_nitride').name}")
print()


# ── 2.  Register a custom computing paradigm ─────────────────────────

print("=" * 60)
print("2.  Register a custom computing paradigm")
print("=" * 60)


@dataclass
class SpintronicGateEnergy:
    """
    Spintronic gate energy model.

    Models spin-transfer torque (STT) switching in magnetic tunnel
    junctions (MTJs).  Energy = I^2 * R * t_switch.
    """
    tech_node_nm: float = 7.0
    spin_current_A: float = 50e-6    # critical switching current
    switching_time_s: float = 2e-9   # STT switching time
    resistance_ohm: float = 5e3      # MTJ resistance

    def energy_per_switch(self, frequency: float = 1e9,
                          T: float = 300.0) -> float:
        """Energy per spin-torque switching event (Joules)."""
        E_switch = (self.spin_current_A ** 2
                    * self.resistance_ohm
                    * self.switching_time_s)
        return max(E_switch, landauer_limit(T))

    def landauer_gap(self, T: float = 300.0,
                     frequency: float = 1e9) -> float:
        return self.energy_per_switch(frequency, T) / landauer_limit(T)


# Register it -- now "spintronic" works everywhere
paradigm_registry.register("spintronic", SpintronicGateEnergy)

model = paradigm_registry.create("spintronic", tech_node_nm=7)
print(f"  Paradigm: spintronic")
print(f"  Energy/switch: {model.energy_per_switch():.2e} J")
print(f"  Landauer gap: {model.landauer_gap():.0f}x")
print(f"  Protocol check: isinstance(model, EnergyModel) = "
      f"{isinstance(model, EnergyModel)}")
print(f"  All paradigms: {paradigm_registry.list_paradigms()}")
print()


# ── 3.  Register a custom cooling layer ───────────────────────────────

print("=" * 60)
print("3.  Register a custom cooling layer")
print("=" * 60)

cooling_registry.register("phase_change_material", ThermalLayer(
    "Phase-change material (paraffin)",
    0.5e-3,     # 0.5 mm thick
    0.25,       # k = 0.25 W/(m*K) -- poor conductor, but absorbs heat
    "PCM for transient thermal buffering during burst workloads."
))

# Build a cooling stack mixing built-in and custom layers
stack = CoolingStack(h_ambient=5000.0)
stack.add_layer(cooling_registry.get("liquid_metal"))        # built-in
stack.add_layer(cooling_registry.get("phase_change_material"))  # custom
stack.add_layer(cooling_registry.get("copper_heatsink"))     # built-in

die_area = 100e-6  # 100 mm^2 die
print(f"  Stack description:")
print(f"  {stack.describe(die_area)}")
print(f"  Effective h_conv: {stack.effective_h(die_area):.0f} W/(m^2*K)")
print(f"  Max power @ T_j=105°C: {stack.max_power_W(die_area, 378):.0f} W")
print()


# ── 4.  Use your custom material in the optimizer ─────────────────────

print("=" * 60)
print("4.  Rank custom materials against built-ins")
print("=" * 60)

opt = ThermalOptimizer(
    grid_shape=(10, 10, 3),
    tech_node_nm=7,
    frequency_Hz=1e9,
)

materials_to_test = [
    "silicon", "diamond", "hex_bn", "aluminum_nitride",
    "silicon_carbide", "gallium_nitride",
]

ranking = opt.material_ranking(h_conv=1000, materials=materials_to_test)
print(f"  {'Material':<40s} {'Max Density':>15s}")
print(f"  {'-'*40} {'-'*15}")
for entry in ranking:
    print(f"  {entry['material_name']:<40s} {entry['max_density']:>15.2e}")
print()


# ── 5.  Build a chip with your custom paradigm + material ─────────────

print("=" * 60)
print("5.  Heterogeneous chip with custom paradigm + material")
print("=" * 60)

chip = ChipFloorplan(
    grid_shape=(20, 20, 4),
    element_size_m=50e-6,
    material="hex_bn",  # custom material
)

# Spintronic processing core
chip.add_block(FunctionalBlock(
    name="spintronic_core",
    x_range=(2, 10), y_range=(2, 10), z_range=(0, 4),
    gate_density=1e6,
    activity=0.3,
    paradigm="spintronic",  # custom paradigm
))

# Traditional CMOS control plane
chip.add_block(FunctionalBlock(
    name="cmos_controller",
    x_range=(12, 18), y_range=(2, 10), z_range=(0, 4),
    gate_density=5e5,
    activity=0.2,
    paradigm="cmos",
))

heat = chip.heat_map(frequency_Hz=1e9)
print(f"  Substrate: {get_material('hex_bn').name}")
print(f"  Grid: {chip.grid_shape}")
print(f"  Blocks: {len(chip.blocks)}")
print(f"  Peak heat generation: {heat.max():.2e} W/element")
print(f"  Total power: {heat.sum():.3f} W")
print()


# ── 6.  Save and share your custom materials ──────────────────────────

print("=" * 60)
print("6.  Save/load custom materials as JSON")
print("=" * 60)

n = registry.save_json("my_custom_materials.json")
print(f"  Saved {n} custom materials to my_custom_materials.json")

# Show what the JSON looks like
import json
with open("my_custom_materials.json") as f:
    data = json.load(f)
for key in data:
    print(f"    {key}: k={data[key]['thermal_conductivity']} W/(m*K)")

# Clean up
os.remove("my_custom_materials.json")
print()

print("=" * 60)
print("  Done!  Every custom component flowed through the")
print("  entire Aethermor pipeline — optimizer, floorplan,")
print("  thermal solver, and analysis.")
print("=" * 60)

# Clean up the registries so other scripts aren't affected
registry.reset()
