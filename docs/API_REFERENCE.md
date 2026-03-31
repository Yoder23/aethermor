# API Reference

Complete reference for all public classes, functions, and registries in Aethermor.

---

## `physics.constants` — Fundamental Constants (SI Units)

| Constant | Value | Unit | Description |
|----------|-------|------|-------------|
| `k_B` | 1.380649e-23 | J/K | Boltzmann constant (CODATA 2018) |
| `h_PLANCK` | 6.62607015e-34 | J·s | Planck constant |
| `h_BAR` | h_PLANCK / 2π | J·s | Reduced Planck constant |
| `E_CHARGE` | 1.602176634e-19 | C | Elementary charge |
| `LANDAUER_LIMIT` | ~2.85e-21 | J | Pre-computed Landauer limit at 300 K |

### Functions

```python
landauer_limit(T: float) → float
```
Minimum energy to irreversibly erase one bit: k_B·T·ln(2).

```python
thermal_noise_voltage(T: float, R: float, bandwidth: float) → float
```
Johnson-Nyquist RMS noise voltage: √(4·k_B·T·R·Δf).

```python
thermal_energy(T: float) → float
```
Characteristic thermal energy: k_B·T.

```python
bits_per_joule(T: float) → float
```
Theoretical maximum irreversible bit erasures per Joule at temperature T.

---

## `physics.materials` — Material Database & Registry

### Class: `Material` (frozen dataclass)

| Attribute | Type | Unit | Description |
|-----------|------|------|-------------|
| `name` | str | — | Human-readable name |
| `thermal_conductivity` | float | W/(m·K) | Thermal conductivity |
| `specific_heat` | float | J/(kg·K) | Specific heat capacity |
| `density` | float | kg/m³ | Mass density |
| `electrical_resistivity` | float | Ω·m | Electrical resistivity |
| `max_operating_temp` | float | K | Maximum operating temperature |
| `bandgap_eV` | float | eV | Electronic bandgap |

**Properties:** `thermal_diffusivity` (m²/s), `volumetric_heat_capacity` (J/(m³·K))

**Methods:** `temp_rise_per_joule(volume_m3)` → K

### Built-in Materials

`silicon`, `silicon_dioxide`, `gallium_arsenide`, `diamond`, `graphene_layer`,
`copper`, `indium_phosphide`, `silicon_carbide`, `gallium_nitride`

### Class: `MaterialRegistry`

```python
registry.register(key, material, *, force=False) → Material
registry.unregister(key) → None
registry.get(key) → Material
registry.list_all() → Dict[str, Material]
registry.list_builtins() → Dict[str, Material]
registry.save_json(filepath) → None
registry.load_json(filepath) → None
```

### Module Functions

```python
get_material(name) → Material
list_materials() → Dict[str, Material]
validate_material(material) → List[str]     # Returns errors/warnings
material_from_dict(d) → Material
material_to_dict(m) → dict
```

---

## `physics.energy_models` — Gate Energy Models

### Protocol: `EnergyModel` (runtime-checkable)

Any class with `energy_per_switch(frequency, T) → float` and
`landauer_gap(T, frequency) → float` can be used as an energy model.

### Class: `CMOSGateEnergy`

```python
CMOSGateEnergy(tech_node_nm=7.0, V_dd=None, C_load=None, I_leak_ref=1e-9)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `dynamic_energy()` | J | C_load·V_dd² |
| `leakage_power(T=300.0)` | W | Temperature-dependent leakage per gate |
| `energy_per_switch(frequency=1e9, T=300.0)` | J | Dynamic + amortized leakage |
| `landauer_gap(T=300.0, frequency=1e9)` | ratio | Actual/Landauer |

### Class: `AdiabaticGateEnergy`

```python
AdiabaticGateEnergy(tech_node_nm=7.0, V_dd=None, C_load=None, R_switch=1000.0)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `energy_per_switch(frequency=1e9, T=300.0)` | J | R·C²·V²·f + floor |
| `crossover_frequency(cmos, T=300.0)` | Hz | Frequency below which adiabatic wins |
| `landauer_gap(T=300.0, frequency=1e9)` | ratio | Actual/Landauer |

### Class: `ReversibleGateEnergy`

```python
ReversibleGateEnergy(erasures_per_gate=1.0, gate_overhead_factor=3.0, clock_overhead_J=1e-20)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `energy_per_switch(frequency=1e9, T=300.0)` | J | Scales with T, not V²·C |
| `temperature_crossover(cmos, frequency=1e9)` | K | Temperature below which reversible wins |
| `landauer_gap(T=300.0, frequency=1e9)` | ratio | Actual/Landauer |

### Class: `LandauerLimitEnergy`

```python
LandauerLimitEnergy(bits_per_gate=1.0)
```

Theoretical floor. `landauer_gap()` always returns 1.0.

### Class: `ParadigmRegistry`

```python
paradigm_registry.register(name, model_class, *, force=False) → None
paradigm_registry.create(name, **kwargs) → EnergyModel
paradigm_registry.list_paradigms() → List[str]
paradigm_registry.paradigm_id(name) → int
```

Built-in paradigms: `"cmos"`, `"adiabatic"`, `"reversible"`, `"landauer"`, `"idle"`

---

## `physics.thermal` — 3D Fourier Thermal Solver

### Class: `FourierThermalTransport`

```python
FourierThermalTransport(
    grid_shape=(60, 60, 10),
    element_size_m=100e-6,
    material=None,          # Default: silicon
    dt=1e-6,                # Auto-adjusted for CFL stability
    boundary=None           # ThermalBoundaryCondition
)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `reset(T_initial=None)` | — | Reset temperature field |
| `inject_heat(heat_W_per_m3)` | — | Volumetric heat generation (W/m³) |
| `inject_heat_watts(heat_W)` | — | Heat generation per element (W) |
| `conduct()` | — | Advance conduction one timestep |
| `apply_boundary_cooling()` | — | Apply boundary conditions |
| `step(heat_generation_W=None)` | — | Full timestep (heat + conduct + cool) |
| `hotspot_map()` | ndarray | Temperature elevation above ambient |
| `max_temperature()` | K | Peak temperature |
| `mean_temperature()` | K | Mean temperature |
| `thermal_gradient_magnitude()` | ndarray | Gradient magnitudes (K/m) |
| `energy_balance()` | dict | Conservation check (generated/removed/stored/error) |
| `steady_state_temperature(heat_W, max_steps=10000, tol=0.01)` | ndarray | Run to steady state |

**`energy_balance()` return dict:**

| Key | Type | Description |
|-----|------|-------------|
| `generated_J` | float | Total energy injected (J) |
| `removed_J` | float | Total energy removed by boundaries (J) |
| `stored_J` | float | Energy stored as temperature rise (J) |
| `error_pct` | float | Conservation error: ‖gen − rem − stored‖ / gen × 100 |

### Class: `ThermalBoundaryCondition`

```python
ThermalBoundaryCondition(
    mode="convective",    # "convective", "fixed", or "adiabatic"
    h_conv=1000.0,        # W/(m²·K)
    T_ambient=300.0,      # K
    T_fixed=300.0         # K (for mode="fixed")
)
```

---

## `physics.cooling` — Cooling Stack Model

### Class: `ThermalLayer` (frozen dataclass)

| Attribute | Type | Unit |
|-----------|------|------|
| `name` | str | — |
| `thickness_m` | float | m |
| `thermal_conductivity` | float | W/(m·K) |

**Method:** `resistance(area_m2)` → K/W

### Class: `CoolingStack`

```python
CoolingStack(h_ambient=50.0, T_ambient=300.0, layers=[])
```

| Method | Returns | Description |
|--------|---------|-------------|
| `add_layer(layer)` | self | Add layer (chainable) |
| `total_resistance(area_m2)` | K/W | Die-to-ambient thermal resistance |
| `effective_h(die_area_m2)` | W/(m²·K) | Collapse stack to single h |
| `max_power_W(die_area_m2, T_junction_max=378.0)` | W | Max dissipable power |
| `layer_temperatures(die_area_m2, power_W)` | List[dict] | Per-interface temperatures |
| `describe(die_area_m2)` | str | Human-readable breakdown |

**Factory methods (class methods):**

| Method | Configuration |
|--------|---------------|
| `bare_die_natural_air()` | Worst case (h=10) |
| `desktop_air()` | Thermal paste + IHS + tower cooler |
| `server_air()` | Indium solder + IHS + high-CFM duct |
| `liquid_cooled()` | Liquid metal + copper cold plate |
| `direct_liquid()` | Direct-to-die (immersion/jet) |
| `diamond_spreader_liquid()` | CVD diamond + liquid (exotic) |

### Class: `CoolingRegistry`

```python
cooling_registry.register(key, layer, *, force=False) → ThermalLayer
cooling_registry.get(key) → ThermalLayer
cooling_registry.list_all() → Dict[str, ThermalLayer]
cooling_registry.save_json(filepath) → None
cooling_registry.load_json(filepath) → None
```

11 built-in layers: `thermal_paste_low`, `thermal_paste_high`, `indium_solder`,
`liquid_metal`, `copper_ihs`, `nickel_plated_copper_ihs`, `aluminum_heatsink`,
`copper_heatsink`, `diamond_heat_spreader`, `silicon_interposer`, `sic_substrate`

---

## `physics.chip_floorplan` — Heterogeneous SoC Model

### Class: `FunctionalBlock`

```python
FunctionalBlock(
    name="block",
    x_range=(0, 10), y_range=(0, 10), z_range=(0, 8),
    gate_density=1e6,       # gates per element
    activity=0.2,           # fraction switching per cycle
    tech_node_nm=7.0,
    paradigm="cmos"         # or "adiabatic", "reversible", custom
)
```

### Class: `ChipFloorplan`

```python
ChipFloorplan(
    grid_shape=(60, 60, 8),
    element_size_m=50e-6,
    material="silicon",
    T_ambient=300.0,
    h_conv=1000.0,
    blocks=[]
)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `add_block(block)` | self | Add functional block (chainable) |
| `heat_map(frequency_Hz=1e9, T=300.0)` | ndarray | Per-element heat (W) |
| `gate_density_map()` | ndarray | Per-element gate density |
| `activity_map()` | ndarray | Per-element activity factor |
| `paradigm_map()` | ndarray | Per-element paradigm ID |
| `landauer_gap_map(frequency_Hz, T)` | ndarray | Per-element Landauer gap |
| `simulate(frequency_Hz, steps, h_conv, cooling_stack)` | FourierThermalTransport | Run thermal simulation |
| `block_temperatures(thermal)` | List[dict] | Per-block thermal stats |
| `total_power_W(frequency_Hz, T)` | W | Total chip power |
| `die_area_m2()` | m² | Die area |
| `power_density_W_cm2(frequency_Hz, T)` | W/cm² | Average power density |
| `summary(frequency_Hz, T)` | str | Human-readable summary |

**Factory:** `ChipFloorplan.modern_soc()` — pre-configured CPU+GPU+cache+IO layout

---

## `analysis.thermal_optimizer` — Inverse Design (8 Tools)

### Class: `ThermalOptimizer`

```python
ThermalOptimizer(
    grid_shape=(20, 20, 5),
    element_size_m=100e-6,
    tech_node_nm=7.0,
    frequency_Hz=1e9,
    T_ambient=300.0,
    activity=0.2,
    thermal_steps=500
)
```

| Method | What It Answers |
|--------|----------------|
| `find_max_density(material, h_conv, T_max, paradigm)` | Max sustainable gate density (3D sim binary search) |
| `find_min_cooling(material, density, T_max)` | Minimum h_conv needed (1D analytical) |
| `material_ranking(h_conv, materials, paradigm)` | Which substrate allows highest density? |
| `cooling_sweep(material, density, h_values)` | Temperature vs cooling tradeoff + conduction floor |
| `thermal_headroom_map(floorplan, freq, h_conv)` | Per-block thermal budget utilization |
| `optimize_power_distribution(floorplan, ...)` | Optimal density allocation under constraints |
| `paradigm_density_comparison(material, h_conv)` | CMOS vs adiabatic max-density comparison |
| `full_design_exploration(material, h_conv, power, T_max)` | Comprehensive one-call analysis |

All methods return structured dicts. Use `format_material_ranking()` for
human-readable output of material comparison results.

### Return Type Details

**`find_max_density()` → dict**

| Key | Type | Description |
|-----|------|-------------|
| `max_density` | float | Maximum sustainable gates per element |
| `T_max_K` | float | Peak temperature at max density (K) |
| `power_W` | float | Total chip power (W) |
| `power_density_W_cm2` | float | Power density (W/cm²) |
| `landauer_gap` | float | Ratio of actual to Landauer energy |
| `thermal_headroom_K` | float | Material limit − T_max (K) |
| `material` | str | Material key |
| `material_name` | str | Human-readable material name |
| `h_conv` | float | Cooling coefficient used |
| `paradigm` | str | Energy model used |
| `throughput_ops_s` | float | Total switching operations per second |

**`find_min_cooling()` → dict**

| Key | Type | Description |
|-----|------|-------------|
| `min_h_conv` | float | Minimum cooling coefficient (W/(m²·K)), `inf` if conduction-limited |
| `material` | str | Material key |
| `gate_density` | float | Target density |
| `T_max_target_K` | float | Target temperature (K) |
| `conduction_floor_K` | float | Temperature at h→∞ (conduction-only limit) |
| `cooling_category` | str | Human-readable category (e.g., "liquid cold plate") |
| `note` | str | Model description |

**`thermal_headroom_map()` → List[dict]**

| Key | Type | Description |
|-----|------|-------------|
| `name` | str | Block name |
| `paradigm` | str | Block energy model |
| `gate_density` | float | Block gate density |
| `T_max_K` | float | Block peak temperature (K) |
| `T_mean_K` | float | Block mean temperature (K) |
| `thermal_headroom_K` | float | Material limit − T_max (K) |
| `is_bottleneck` | bool | True if this is the hottest block |
| `density_headroom_factor` | float | Multiplier: how much more density is sustainable |
| `recommended_action` | str | Engineering recommendation |

**`optimize_power_distribution()` → dict**

| Key | Type | Description |
|-----|------|-------------|
| `optimised_blocks` | List[dict] | Per-block optimised densities and temperatures |
| `total_throughput_ops_s` | float | Total optimised throughput |
| `total_power_W` | float | Total power (W) |
| `power_budget_W` | float | Requested power budget (W) |
| `thermal_power_limit_W` | float | Power at which all blocks hit thermal limit |
| `binding_constraint` | str | `"thermal"` or `"power"` |
| `improvement_ratio` | float | Throughput ratio vs original layout |

**`paradigm_density_comparison()` → dict**

| Key | Type | Description |
|-----|------|-------------|
| `cmos` | dict | `find_max_density()` result for CMOS |
| `adiabatic` | dict | `find_max_density()` result for adiabatic |
| `adiabatic_advantage_ratio` | float | Adiabatic max density / CMOS max density |
| `material` | str | Material key |
| `h_conv` | float | Cooling coefficient used |

**`full_design_exploration()` → dict**

| Key | Type | Description |
|-----|------|-------------|
| `material_ranking` | List[dict] | Ranked substrates by max density |
| `best_material` | dict | Top-ranked material result |
| `max_density` | dict | `find_max_density()` result for target material |
| `cooling_requirement` | dict | `find_min_cooling()` at 50% of max density |
| `paradigm_comparison` | dict | `paradigm_density_comparison()` result |
| `cooling_sweep` | List[dict] | Temperature vs h_conv sweep |
| `insights` | List[str] | Auto-generated engineering insights |

---

## `analysis.tech_roadmap` — Technology Scaling Projection

### Class: `TechnologyRoadmap`

```python
TechnologyRoadmap(
    tech_nodes=[130, 65, 45, 28, 14, 7, 5, 3, 2, 1.4],
    frequencies=[1e9, 5e9, 10e9],
    T_ambient=300.0
)
```

| Method | What It Shows |
|--------|---------------|
| `energy_roadmap(frequency_Hz)` | Energy per gate across nodes for all paradigms |
| `thermal_wall_roadmap(h_conv)` | Max density per node per material |
| `paradigm_crossover_map()` | Adiabatic/CMOS crossover frequency per node |
| `gap_closure_projection(frequency_Hz)` | How Landauer gap closes with scaling |

All methods have companion `format_*()` methods for readable output.

---

## `analysis.design_space` — Parameter Sweeps & Pareto

### Class: `DesignSpaceSweep`

```python
DesignSpaceSweep(
    tech_nodes=[7, 14, 28],
    frequencies=[1e9, 5e9, 10e9],
    gate_densities=[1e4, 1e5, 1e6],
    materials=["silicon", "diamond", "silicon_carbide"],
    h_conv_values=[500, 1000, 5000]
)
```

| Method | Returns |
|--------|---------|
| `run(progress_callback)` | List[DesignPoint] |
| `run_and_extract_pareto(minimize, callback)` | (all_points, pareto_frontier) |

### Functions

```python
extract_pareto_frontier(points, minimize) → List[DesignPoint]
export_results_csv(points, filepath)
export_results_json(points, filepath)
```

---

## `analysis.regime_map` — Operating Regime Classification

### Functions

```python
classify_regime(landauer_gap) → str
# Returns: "deep_classical" | "classical" | "transitional" | "thermodynamic" | "near_limit"

regime_map_vs_node_and_frequency(tech_nodes, frequencies, T) → dict
find_crossover_node(frequency_Hz, T, gap_threshold) → float
thermal_density_limit(material, node, freq, max_temp, ...) → dict
paradigm_comparison(T, frequencies) → dict
```

---

## `analysis.landauer_gap` — Distance-from-Limit Analysis

### Functions

```python
compute_gap(E_actual_J, T) → LandauerGapResult
spatial_gap_map(energy, temperature, operations) → ndarray
gap_vs_technology_node(nodes, frequency, T) → dict
gap_vs_temperature(energy_model, temperatures, frequency) → list
identify_efficiency_bottlenecks(gap_map, threshold) → dict
```

---

## `analysis.thermal_map` — Hotspot Detection

### Functions

```python
detect_hotspots(temperature_field, T_ambient, threshold, element_size, max_temp) → List[HotspotInfo]
cooling_efficiency_map(thermal, heat_generation_W) → ndarray
thermal_summary(temperature_field, T_ambient, max_temp) → dict
```

### Class: `HotspotInfo`

| Attribute | Type | Description |
|-----------|------|-------------|
| `center` | tuple | (x, y, z) coordinates |
| `peak_temp_K` | float | Peak temperature |
| `extent` | int | Number of elements |
| `thermal_risk` | str | "low" / "medium" / "high" / "critical" |

---

## Orchestration Example: ChipFloorplan → ThermalOptimizer

End-to-end workflow showing how modules compose to answer a real
architecture question: *"Where is my thermal budget being wasted, and
how should I redistribute compute density?"*

```python
from aethermor.physics.chip_floorplan import ChipFloorplan
from aethermor.analysis.thermal_optimizer import ThermalOptimizer

# 1. Define a heterogeneous SoC
chip = ChipFloorplan.modern_soc(material="silicon", h_conv=2000.0)

# 2. Create the optimizer (matching the chip's grid)
opt = ThermalOptimizer(
    grid_shape=chip.grid_shape,
    element_size_m=chip.element_size_m,
    tech_node_nm=7.0,
    frequency_Hz=3e9,
    T_ambient=300.0,
)

# 3. Identify wasted thermal budget (per-block headroom)
headroom = opt.thermal_headroom_map(chip, frequency_Hz=3e9, h_conv=2000.0)
for block in headroom:
    print(f"{block['name']:>10s}  T={block['T_max_K']:.0f} K  "
          f"headroom={block['thermal_headroom_K']:.0f} K  "
          f"{'⚠ BOTTLENECK' if block['is_bottleneck'] else ''}")

# 4. Redistribute density to maximise throughput under constraints
result = opt.optimize_power_distribution(
    chip, power_budget_W=150.0, frequency_Hz=3e9, h_conv=2000.0,
)
print(f"\nTotal throughput: {result['total_throughput_ops_s']:.2e} ops/s")
print(f"Improvement over original: {result['improvement_ratio']:.1f}×")
print(f"Binding constraint: {result['binding_constraint']}")

# 5. Compare substrates — would diamond help?
ranking = opt.material_ranking(h_conv=2000.0)
print(opt.format_material_ranking(ranking, h_conv=2000.0))
```
