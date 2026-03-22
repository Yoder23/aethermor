"""
Cooling stack model — full thermal path from die to ambient.

Real chip packages have multiple layers between the die surface and the
ambient air, each with its own thermal resistance.  Capturing this stack
lets researchers evaluate realistic cooling solutions rather than guessing
a single h_conv value.

Thermal resistance network (1-D, normal to die surface):

    T_junction ──[R_die]── T_die_surface ──[R_TIM]── T_IHS_bottom
                ──[R_IHS]── T_IHS_top ──[R_heatsink]── T_ambient

Total junction-to-ambient resistance:
    R_ja = R_die + R_TIM + R_IHS + R_heatsink

The module converts any cooling stack into an effective h_conv so it
plugs directly into FourierThermalTransport.

Reference data (ITRS / IRDS roadmap):
    - Bare die in still air:    R_ja ≈ 30-60 K/W  →  ~50 W limit at ΔT=80K
    - Desktop heatsink + fan:   R_ja ≈ 0.3-1 K/W  →  ~100-250 W
    - Server liquid cold plate: R_ja ≈ 0.05-0.15   →  ~500-1500 W
    - Direct die liquid metal:  R_ja ≈ 0.02-0.05   →  >2000 W

Extensibility
-------------
Register custom thermal layers::

    from physics.cooling import cooling_registry, ThermalLayer

    cooling_registry.register("aerogel_insulator", ThermalLayer(
        "Aerogel thermal barrier", 1.0e-3, 0.015,
        "Ultra-low-k insulator for directed heat flow."
    ))

    # Or from a dict:
    cooling_registry.register("phase_change", {
        "name": "Phase-change material (PCM)",
        "thickness_m": 0.5e-3,
        "thermal_conductivity": 5.0,
        "notes": "Paraffin-based PCM for transient thermal buffering."
    })

    # Save and share with collaborators:
    cooling_registry.save_json("my_cooling_layers.json")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Union
from pathlib import Path
import json
import math
import warnings


# ── Pre-built thermal interface material library ──────────────────────

@dataclass(frozen=True)
class ThermalLayer:
    """
    A single layer in the cooling stack.

    Parameters
    ----------
    name : str
        Human-readable label (e.g. "thermal paste", "copper IHS").
    thickness_m : float
        Layer thickness (m).
    thermal_conductivity : float
        Thermal conductivity (W/(m·K)).
    notes : str
        Additional context.
    """
    name: str
    thickness_m: float           # m
    thermal_conductivity: float  # W/(m·K)
    notes: str = ""

    def resistance(self, area_m2: float) -> float:
        """Thermal resistance R = L / (k · A)  in K/W."""
        return self.thickness_m / (self.thermal_conductivity * area_m2)


# Pre-built layers researchers can pick from
THERMAL_LAYERS: Dict[str, ThermalLayer] = {
    "thermal_paste_low": ThermalLayer(
        "Thermal paste (low-end)", 50e-6, 3.0,
        "Silicone-based TIM.  k ≈ 1-5 W/m·K.  Typical consumer."
    ),
    "thermal_paste_high": ThermalLayer(
        "Thermal paste (high-end)", 25e-6, 8.0,
        "Metal-oxide loaded.  k ≈ 5-12 W/m·K.  Enthusiast / server."
    ),
    "indium_solder": ThermalLayer(
        "Indium solder TIM", 20e-6, 86.0,
        "Soldered TIM.  k ≈ 86 W/m·K.  Used in high-perf server CPUs."
    ),
    "liquid_metal": ThermalLayer(
        "Liquid metal (Ga alloy)", 15e-6, 73.0,
        "Gallium-based alloy.  k ≈ 40-73 W/m·K.  Best paste alternative."
    ),
    "copper_ihs": ThermalLayer(
        "Copper IHS", 2.0e-3, 401.0,
        "Integrated heat spreader.  Standard desktop / server."
    ),
    "nickel_plated_copper_ihs": ThermalLayer(
        "Nickel-plated copper IHS", 2.5e-3, 380.0,
        "Typical Intel / AMD desktop IHS."
    ),
    "aluminum_heatsink": ThermalLayer(
        "Aluminum heatsink base", 8.0e-3, 237.0,
        "Tower cooler base plate."
    ),
    "copper_heatsink": ThermalLayer(
        "Copper heatsink base", 6.0e-3, 401.0,
        "High-end tower cooler or cold plate base."
    ),
    "diamond_heat_spreader": ThermalLayer(
        "CVD diamond heat spreader", 0.3e-3, 2200.0,
        "Emerging.  ~15× better than copper.  Used in GaN power amplifiers."
    ),
    "silicon_interposer": ThermalLayer(
        "Silicon interposer (2.5D)", 0.1e-3, 148.0,
        "For 2.5D / chiplet packaging.  Adds ~0.5-1 K/W per cm²."
    ),
    "sic_substrate": ThermalLayer(
        "SiC substrate", 0.35e-3, 490.0,
        "Used as carrier for GaN-on-SiC."
    ),
}


@dataclass
class CoolingStack:
    """
    Complete cooling stack from die surface to ambient.

    Build a stack by adding layers from die outward, then specify
    the final-surface-to-ambient convection coefficient.

    Example — desktop CPU:
        >>> stack = CoolingStack.desktop_air()
        >>> h_eff = stack.effective_h(die_area_m2=150e-6)
        >>> print(f"Effective h = {h_eff:.0f} W/(m²·K)")

    Example — custom stack:
        >>> stack = CoolingStack(h_ambient=5000)  # liquid cold plate
        >>> stack.add_layer(THERMAL_LAYERS["liquid_metal"])
        >>> stack.add_layer(THERMAL_LAYERS["copper_ihs"])
        >>> h_eff = stack.effective_h(die_area_m2=200e-6)

    Parameters
    ----------
    h_ambient : float
        Heat transfer coefficient from the outermost surface to the
        ambient air or coolant (W/(m²·K)).
    T_ambient : float
        Ambient temperature (K).
    """
    h_ambient: float = 50.0       # W/(m²·K) — forced air over bare heatsink
    T_ambient: float = 300.0
    layers: List[ThermalLayer] = field(default_factory=list)

    def add_layer(self, layer: ThermalLayer) -> 'CoolingStack':
        """Add a thermal layer (from die outward). Returns self for chaining."""
        self.layers.append(layer)
        return self

    def total_resistance(self, area_m2: float) -> float:
        """
        Total thermal resistance from die surface to ambient (K/W).

        R_total = Σ R_layer + R_convection
        R_convection = 1 / (h_ambient · A)
        """
        R = sum(layer.resistance(area_m2) for layer in self.layers)
        R += 1.0 / (self.h_ambient * area_m2)
        return R

    def effective_h(self, die_area_m2: float) -> float:
        """
        Effective heat transfer coefficient (W/(m²·K)) that collapses the
        entire stack into a single number for FourierThermalTransport.

        h_eff = 1 / (R_total · A)

        This means the researcher can build a realistic cooling stack and
        get the right number to plug into the thermal solver.
        """
        R = self.total_resistance(die_area_m2)
        return 1.0 / (R * die_area_m2)

    def max_power_W(self, die_area_m2: float, T_junction_max: float = 378.0) -> float:
        """
        Maximum power the stack can dissipate before junction hits T_max.

        P_max = (T_junction_max - T_ambient) / R_total
        """
        R = self.total_resistance(die_area_m2)
        return (T_junction_max - self.T_ambient) / R

    def layer_temperatures(self, die_area_m2: float, power_W: float) -> List[dict]:
        """
        Compute temperature at each interface given a total die power.

        Returns list of dicts from junction (hottest) to ambient (coolest):
        [{"name": ..., "T_K": ..., "R_K_per_W": ...}, ...]
        """
        R_total = self.total_resistance(die_area_m2)
        T = self.T_ambient + power_W * R_total  # junction temp

        result = [{"name": "Die junction", "T_K": T, "R_K_per_W": 0.0}]
        for layer in self.layers:
            R_layer = layer.resistance(die_area_m2)
            T -= power_W * R_layer
            result.append({
                "name": layer.name,
                "T_K": T,
                "R_K_per_W": R_layer,
            })
        result.append({
            "name": "Ambient",
            "T_K": self.T_ambient,
            "R_K_per_W": 1.0 / (self.h_ambient * die_area_m2),
        })
        return result

    def describe(self, die_area_m2: float) -> str:
        """Human-readable description of the cooling stack."""
        lines = [f"Cooling stack ({len(self.layers)} layers):"]
        for layer in self.layers:
            R = layer.resistance(die_area_m2)
            lines.append(
                f"  {layer.name:40s}  {layer.thickness_m*1e6:8.1f} μm  "
                f"k={layer.thermal_conductivity:7.1f} W/m·K  R={R:.4f} K/W"
            )
        R_conv = 1.0 / (self.h_ambient * die_area_m2)
        lines.append(f"  {'Convection to ambient':40s}  h={self.h_ambient:.0f} W/(m²·K)"
                      f"{'':17s}  R={R_conv:.4f} K/W")
        R_total = self.total_resistance(die_area_m2)
        lines.append(f"  {'TOTAL':40s}{'':27s}  R={R_total:.4f} K/W")
        h_eff = self.effective_h(die_area_m2)
        lines.append(f"  Effective h_conv = {h_eff:.1f} W/(m²·K)")
        return "\n".join(lines)

    # ── Factory methods for common configurations ──

    @classmethod
    def bare_die_natural_air(cls) -> 'CoolingStack':
        """Bare die in still air — worst case."""
        return cls(h_ambient=10.0)

    @classmethod
    def desktop_air(cls) -> 'CoolingStack':
        """Standard desktop: thermal paste + IHS + tower cooler."""
        stack = cls(h_ambient=50.0)
        stack.add_layer(THERMAL_LAYERS["thermal_paste_high"])
        stack.add_layer(THERMAL_LAYERS["copper_ihs"])
        stack.add_layer(THERMAL_LAYERS["aluminum_heatsink"])
        return stack

    @classmethod
    def server_air(cls) -> 'CoolingStack':
        """Server: indium solder + IHS + high-CFM fan duct."""
        stack = cls(h_ambient=120.0)
        stack.add_layer(THERMAL_LAYERS["indium_solder"])
        stack.add_layer(THERMAL_LAYERS["nickel_plated_copper_ihs"])
        stack.add_layer(THERMAL_LAYERS["copper_heatsink"])
        return stack

    @classmethod
    def liquid_cooled(cls) -> 'CoolingStack':
        """Liquid cold plate: liquid metal + copper cold plate."""
        stack = cls(h_ambient=5000.0)
        stack.add_layer(THERMAL_LAYERS["liquid_metal"])
        stack.add_layer(THERMAL_LAYERS["copper_heatsink"])
        return stack

    @classmethod
    def direct_liquid(cls) -> 'CoolingStack':
        """Direct-to-die liquid cooling (immersion or jet impingement)."""
        return cls(h_ambient=20000.0)

    @classmethod
    def diamond_spreader_liquid(cls) -> 'CoolingStack':
        """CVD diamond heat spreader + liquid cooling — exotic high performance."""
        stack = cls(h_ambient=10000.0)
        stack.add_layer(THERMAL_LAYERS["diamond_heat_spreader"])
        stack.add_layer(THERMAL_LAYERS["copper_heatsink"])
        return stack


# ── Serialization ────────────────────────────────────────────────────────

def layer_from_dict(d: dict) -> ThermalLayer:
    """
    Create a ThermalLayer from a dictionary.

    Required keys: name, thickness_m, thermal_conductivity
    Optional keys: notes (default "")
    """
    required = ["name", "thickness_m", "thermal_conductivity"]
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f"Missing required layer fields: {missing}")
    return ThermalLayer(
        name=d["name"],
        thickness_m=d["thickness_m"],
        thermal_conductivity=d["thermal_conductivity"],
        notes=d.get("notes", ""),
    )


def layer_to_dict(layer: ThermalLayer) -> dict:
    """Serialize a ThermalLayer to a plain dictionary."""
    return {
        "name": layer.name,
        "thickness_m": layer.thickness_m,
        "thermal_conductivity": layer.thermal_conductivity,
        "notes": layer.notes,
    }


# ── Cooling Layer Registry ──────────────────────────────────────────────

# Validation ranges for thermal layers
_LAYER_RANGES = {
    "thickness_m":          (1e-9,  1.0,    "m"),     # monolayer → 1 m
    "thermal_conductivity": (0.001, 10000,  "W/(m·K)"),
}


def validate_layer(layer: ThermalLayer) -> List[str]:
    """
    Validate a ThermalLayer's properties.

    Returns list of "ERROR: ..." or "WARNING: ..." strings.
    """
    issues: List[str] = []

    if not layer.name or not layer.name.strip():
        issues.append("ERROR: name must be a non-empty string")

    for attr, (lo, hi, unit) in _LAYER_RANGES.items():
        val = getattr(layer, attr)
        if val <= 0:
            issues.append(f"ERROR: {attr}={val} {unit} — must be positive")
        elif val < lo:
            issues.append(
                f"WARNING: {attr}={val} {unit} is below typical range "
                f"[{lo}–{hi}]. Ensure this is intentional."
            )
        elif val > hi:
            issues.append(
                f"WARNING: {attr}={val} {unit} is above typical range "
                f"[{lo}–{hi}]. Ensure this is intentional."
            )

    return issues


class CoolingRegistry:
    """
    Registry for thermal interface layers.

    Manages both the built-in layer library (11 curated layers) and
    user-registered custom layers.  Supports validation, JSON
    import/export, and clean separation.

    Usage
    -----
    ::

        from physics.cooling import cooling_registry, ThermalLayer

        cooling_registry.register("my_tim", ThermalLayer(
            "Custom TIM", 30e-6, 12.0,
            "High-perf thermal interface material."
        ))

        # Build a stack with mix of built-in and custom layers
        stack = CoolingStack(h_ambient=5000)
        stack.add_layer(cooling_registry.get("my_tim"))
        stack.add_layer(cooling_registry.get("copper_heatsink"))
    """

    def __init__(self):
        self._builtins: Dict[str, ThermalLayer] = {}
        self._custom: Dict[str, ThermalLayer] = {}

    def _load_builtins(self, layers: Dict[str, ThermalLayer]):
        """Load built-in layers.  Called once at module init."""
        self._builtins = dict(layers)

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.lower().replace(" ", "_").replace("-", "_")

    def register(self, key: str, layer, *,
                 force: bool = False) -> ThermalLayer:
        """
        Register a custom thermal layer.

        Parameters
        ----------
        key : str
            Lookup key (e.g. "my_tim").
        layer : ThermalLayer or dict
            A ThermalLayer instance or dict of constructor kwargs.
        force : bool
            If True, allow overwriting a built-in layer.

        Returns
        -------
        ThermalLayer
            The registered layer.
        """
        key = self._normalize_key(key)

        if isinstance(layer, dict):
            layer = layer_from_dict(layer)

        issues = validate_layer(layer)
        errors = [i for i in issues if i.startswith("ERROR")]
        warns  = [i for i in issues if i.startswith("WARNING")]

        if errors:
            raise ValueError(
                f"Cannot register layer '{key}':\n" + "\n".join(errors)
            )
        for w in warns:
            warnings.warn(w, stacklevel=2)

        if key in self._builtins and not force:
            raise KeyError(
                f"'{key}' is a built-in layer.  Use force=True to override."
            )

        self._custom[key] = layer
        return layer

    def unregister(self, key: str) -> None:
        """Remove a custom layer.  Built-ins cannot be removed."""
        key = self._normalize_key(key)
        if key in self._custom:
            del self._custom[key]
        elif key in self._builtins:
            raise KeyError(f"Cannot remove built-in layer '{key}'.")
        else:
            raise KeyError(f"Unknown layer '{key}'.")

    def get(self, key: str) -> ThermalLayer:
        """Look up a layer by key (case-insensitive)."""
        key = self._normalize_key(key)
        if key in self._custom:
            return self._custom[key]
        if key in self._builtins:
            return self._builtins[key]
        all_keys = sorted(set(list(self._builtins) + list(self._custom)))
        raise KeyError(f"Unknown layer '{key}'. Available: {all_keys}")

    def list_all(self) -> Dict[str, ThermalLayer]:
        """Return all layers (built-in + custom)."""
        result = dict(self._builtins)
        result.update(self._custom)
        return result

    def list_custom(self) -> Dict[str, ThermalLayer]:
        """Return only user-registered layers."""
        return dict(self._custom)

    def reset(self) -> None:
        """Remove all custom layers."""
        self._custom.clear()

    def save_json(self, path, *, custom_only: bool = True) -> int:
        """Save layers to a JSON file.  Returns count saved."""
        layers = self._custom if custom_only else self.list_all()
        data = {k: layer_to_dict(v) for k, v in layers.items()}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return len(data)

    def load_json(self, path, *, force: bool = False) -> int:
        """Load layers from a JSON file.  Returns count loaded."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        count = 0
        for key, props in data.items():
            self.register(key, props, force=force)
            count += 1
        return count

    def __contains__(self, key: str) -> bool:
        key = self._normalize_key(key)
        return key in self._custom or key in self._builtins

    def __len__(self) -> int:
        return len(set(list(self._builtins) + list(self._custom)))


# ── Module-level registry singleton ──────────────────────────────────────

cooling_registry = CoolingRegistry()
cooling_registry._load_builtins(THERMAL_LAYERS)

# Convenience aliases
register_cooling_layer = cooling_registry.register
