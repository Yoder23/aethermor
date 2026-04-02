# API Stability Policy

Version: 1.0 (effective with Aethermor v1.1.0)

## Stable Public APIs

The following APIs are **stable** and covered by semantic versioning
compatibility promises:

### Core Classes (will not break in minor releases)

| Class | Module | Stable Since |
|-------|--------|-------------|
| `ThermalOptimizer` | `aethermor.analysis.thermal_optimizer` | v1.0.0 |
| `CoolingStack` | `aethermor.physics.cooling` | v1.0.0 |
| `PackageStack` | `aethermor.physics.cooling` | v1.1.0 |
| `ThermalLayer` | `aethermor.physics.cooling` | v1.0.0 |
| `Material` | `aethermor.physics.materials` | v1.0.0 |
| `ChipFloorplan` | `aethermor.physics.chip_floorplan` | v1.0.0 |
| `FunctionalBlock` | `aethermor.physics.chip_floorplan` | v1.0.0 |
| `CMOSGateEnergy` | `aethermor.physics.energy_models` | v1.0.0 |
| `AdiabaticGateEnergy` | `aethermor.physics.energy_models` | v1.0.0 |
| `TechnologyRoadmap` | `aethermor.analysis.tech_roadmap` | v1.0.0 |
| `FourierThermalTransport` | `aethermor.physics.thermal` | v1.0.0 |

### Stable Functions

| Function | Stable Since |
|----------|-------------|
| `get_material(key)` | v1.0.0 |
| `register_material(key, Material)` | v1.0.0 |
| `register_cooling_layer(key, ThermalLayer)` | v1.0.0 |
| `register_paradigm(key, EnergyModel)` | v1.0.0 |
| `landauer_limit(T)` | v1.0.0 |

### Stable CLI Commands

| Command | Stable Since |
|---------|-------------|
| `aethermor validate` | v1.0.0 |
| `aethermor version` | v1.0.0 |
| `aethermor dashboard` | v1.0.0 |

### Stable Data Formats

| Format | Description | Stable Since |
|--------|-------------|-------------|
| `Material.to_dict()` / `from_dict()` | Material JSON schema | v1.0.0 |
| `CoolingRegistry.save_json()` / `load_json()` | Cooling layer JSON | v1.0.0 |
| `MaterialRegistry.save_json()` / `load_json()` | Material registry JSON | v1.0.0 |
| `PackageStack.to_dict()` / `from_dict()` | Package stack JSON | v1.1.0 |
| Validation JSON output (`--json` flag) | Benchmark result schema | v1.1.0 |

## Deprecation Policy

1. **No breaking changes in minor releases** (1.x.y → 1.x+1.0).
2. **Deprecated APIs** will emit `DeprecationWarning` for at least one minor
   release before removal.
3. **Removal** only in major releases (1.x → 2.0).
4. **New parameters** added with defaults — existing code continues to work.
5. **New return dict keys** may be added in minor releases; existing keys
   will not be removed or renamed.

## Compatibility Promises

| Promise | Scope |
|---------|-------|
| Python version | ≥ 3.10 (tested on 3.10, 3.11, 3.12) |
| NumPy version | ≥ 1.24 |
| Deterministic output | Same seed + same NumPy version = identical results |
| Material database | Built-in materials will not be removed in minor releases |
| Factory methods | `CoolingStack.desktop_air()`, `.server_air()`, etc. will not change signature |
| `PackageStack` factories | `.desktop_cpu()`, `.server_gpu()`, `.mobile_soc()` stable from v1.1.0 |

## Versioned Output Schema

All `--json` benchmark outputs include:

```json
{
  "tool": "aethermor",
  "version": "1.1.0",
  "timestamp": "2026-04-01T12:00:00Z",
  "python_version": "3.10.x",
  "numpy_version": "1.24.x",
  ...
}
```

Schema changes are versioned: breaking changes bump a `schema_version` field.

## What Is NOT Stable

- Internal modules (`aethermor.physics.thermal` internals, `_analytical_T_max`)
- Dashboard layout and UI elements
- Benchmark script output formatting (use `--json` for stable output)
- Test file organization
