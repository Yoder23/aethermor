"""
Material properties database for thermodynamic computing substrates.

Each material provides the thermal and electrical properties needed to
simulate realistic heat transport and energy dissipation on a chip.

Hardware researchers can:
- Select a substrate material to see how thermal conductivity affects hotspots.
- Compare Si vs GaAs vs diamond vs graphene for heat spreading capability.
- Register custom materials for novel substrates under investigation.
- Validate material properties against physical bounds.
- Save / load custom material databases as JSON for sharing with collaborators.

All values at 300 K unless noted. Sources: CRC Handbook, Ioffe Institute data.

Extensibility
-------------
Register your own materials::

    from physics.materials import registry, Material

    registry.register("boron_nitride", Material(
        name="Hexagonal Boron Nitride (h-BN)",
        thermal_conductivity=600.0,
        specific_heat=800.0,
        density=2100.0,
        electrical_resistivity=1e15,
        max_operating_temp=1000 + 273.15,
        bandgap_eV=6.0,
        notes="2D insulator with excellent thermal interface properties."
    ))

    # Now available everywhere:
    from physics.materials import get_material
    mat = get_material("boron_nitride")

Or from a JSON file::

    registry.load_json("my_materials.json")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from pathlib import Path
import json
import math
import warnings


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

    Checks the registry (which includes both built-in and custom materials).
    Raises KeyError with helpful message listing available materials.
    """
    return registry.get(name)


def list_materials() -> Dict[str, Material]:
    """Return the full material database (built-in + custom)."""
    return registry.list_all()


# ── Validation ───────────────────────────────────────────────────────────

# Physical sanity bounds for material property validation.
# Values outside these ranges trigger warnings (unusual but possible)
# or errors (physically impossible — e.g. negative conductivity).
_VALID_RANGES = {
    "thermal_conductivity": (0.01, 10000.0, "W/(m·K)"),    # aerogel → graphene
    "specific_heat":        (50.0, 5000.0,  "J/(kg·K)"),   # metals → water
    "density":              (1.0,  25000.0, "kg/m³"),       # aerogel → osmium
    "electrical_resistivity": (1e-9, 1e20,  "Ω·m"),        # metals → perfect insulator
    "max_operating_temp":   (50.0,  4000.0, "K"),           # cryogenic → tungsten
    "bandgap_eV":           (0.0,   15.0,   "eV"),          # metals → wide-gap insulators
}


def validate_material(material: Material) -> List[str]:
    """
    Validate material properties against physical bounds.

    Returns a list of diagnostic strings:
    - "ERROR: ..." for physically impossible values (registration will fail)
    - "WARNING: ..." for unusual but technically possible values

    Examples
    --------
    >>> issues = validate_material(Material("Test", -1, 100, 100, 1, 300))
    >>> any("ERROR" in i for i in issues)
    True

    >>> issues = validate_material(get_material("silicon"))
    >>> issues
    []
    """
    issues: List[str] = []

    if not material.name or not material.name.strip():
        issues.append("ERROR: name must be a non-empty string")

    for attr, (lo, hi, unit) in _VALID_RANGES.items():
        val = getattr(material, attr)
        if val < 0 and attr != "bandgap_eV":
            issues.append(
                f"ERROR: {attr}={val} {unit} — must be non-negative"
            )
        elif val < lo and attr != "bandgap_eV":
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


# ── Serialization ────────────────────────────────────────────────────────

def material_from_dict(d: dict) -> Material:
    """
    Create a Material from a dictionary of properties.

    Required keys: name, thermal_conductivity, specific_heat, density,
                   electrical_resistivity, max_operating_temp
    Optional keys: bandgap_eV (default 0.0), notes (default "")

    Examples
    --------
    >>> m = material_from_dict({
    ...     "name": "Test",
    ...     "thermal_conductivity": 100.0,
    ...     "specific_heat": 500.0,
    ...     "density": 2000.0,
    ...     "electrical_resistivity": 1e6,
    ...     "max_operating_temp": 600.0,
    ... })
    >>> m.thermal_diffusivity > 0
    True
    """
    required = [
        "name", "thermal_conductivity", "specific_heat",
        "density", "electrical_resistivity", "max_operating_temp",
    ]
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f"Missing required material fields: {missing}")
    valid_fields = set(Material.__dataclass_fields__.keys())
    return Material(**{k: v for k, v in d.items() if k in valid_fields})


def material_to_dict(m: Material) -> dict:
    """
    Serialize a Material to a plain dictionary (JSON-safe).

    >>> d = material_to_dict(get_material("silicon"))
    >>> d["name"]
    'Silicon (Si)'
    """
    return {
        "name": m.name,
        "thermal_conductivity": m.thermal_conductivity,
        "specific_heat": m.specific_heat,
        "density": m.density,
        "electrical_resistivity": m.electrical_resistivity,
        "max_operating_temp": m.max_operating_temp,
        "bandgap_eV": m.bandgap_eV,
        "notes": m.notes,
    }


# ── Material Registry ───────────────────────────────────────────────────

class MaterialRegistry:
    """
    Validating registry for substrate materials.

    Manages both the built-in material database (9 curated substrates)
    and user-registered custom materials.  Provides validation, JSON
    import/export, and clean separation between built-in and custom
    entries.

    Usage
    -----
    Import the module-level singleton::

        from physics.materials import registry

    Register a custom material::

        registry.register("my_alloy", Material(
            name="My Custom Alloy",
            thermal_conductivity=250.0,
            specific_heat=450.0,
            density=5000.0,
            electrical_resistivity=1e-7,
            max_operating_temp=800.0,
            bandgap_eV=0.0,
            notes="Experimental Cu-Ag alloy for heat spreading."
        ))

    Or pass a dict (e.g. from a config file)::

        registry.register("my_alloy", {
            "name": "My Custom Alloy",
            "thermal_conductivity": 250.0,
            "specific_heat": 450.0,
            "density": 5000.0,
            "electrical_resistivity": 1e-7,
            "max_operating_temp": 800.0,
        })

    Save and load to share with collaborators::

        registry.save_json("my_materials.json")
        registry.load_json("colleague_materials.json")

    All registered materials immediately appear in `get_material()`,
    `list_materials()`, the interactive UI, and every analysis function.
    """

    def __init__(self):
        self._builtins: Dict[str, Material] = {}
        self._custom: Dict[str, Material] = {}

    def _load_builtins(self, materials: Dict[str, Material]):
        """Load built-in material database.  Called once at module init."""
        self._builtins = dict(materials)

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Normalize a material key: lowercase, underscores for spaces/hyphens."""
        return key.lower().replace(" ", "_").replace("-", "_")

    def register(self, key: str, material, *, force: bool = False) -> Material:
        """
        Register a custom material.

        Parameters
        ----------
        key : str
            Lookup key (e.g. "boron_nitride").  Normalized automatically.
        material : Material or dict
            A Material instance or a dict of constructor kwargs.
        force : bool
            If True, allow overwriting a built-in material key.

        Returns
        -------
        Material
            The registered Material (useful when passing a dict).

        Raises
        ------
        ValueError
            If properties are physically impossible (negative conductivity, etc.).
        KeyError
            If *key* collides with a built-in and *force* is False.
        """
        key = self._normalize_key(key)

        if isinstance(material, dict):
            material = material_from_dict(material)

        # Validate
        issues = validate_material(material)
        errors = [i for i in issues if i.startswith("ERROR")]
        warns  = [i for i in issues if i.startswith("WARNING")]

        if errors:
            raise ValueError(
                f"Cannot register '{key}' — physically invalid:\n"
                + "\n".join(errors)
            )
        for w in warns:
            warnings.warn(w, stacklevel=2)

        if key in self._builtins and not force:
            raise KeyError(
                f"'{key}' is a built-in material.  Use force=True to "
                f"override, or choose a different key."
            )

        self._custom[key] = material
        return material

    def unregister(self, key: str) -> None:
        """
        Remove a custom material.  Built-in materials cannot be removed.

        Raises KeyError if the key is a built-in or doesn't exist.
        """
        key = self._normalize_key(key)
        if key in self._custom:
            del self._custom[key]
        elif key in self._builtins:
            raise KeyError(f"Cannot remove built-in material '{key}'.")
        else:
            raise KeyError(f"Unknown material '{key}'.")

    def get(self, key: str) -> Material:
        """
        Look up a material (case-insensitive, underscores optional).

        Custom materials shadow built-ins if registered with force=True.
        """
        key = self._normalize_key(key)
        if key in self._custom:
            return self._custom[key]
        if key in self._builtins:
            return self._builtins[key]
        all_keys = sorted(set(list(self._builtins) + list(self._custom)))
        raise KeyError(f"Unknown material '{key}'. Available: {all_keys}")

    def list_all(self) -> Dict[str, Material]:
        """Return all materials (built-in + custom)."""
        result = dict(self._builtins)
        result.update(self._custom)
        return result

    def list_builtins(self) -> Dict[str, Material]:
        """Return only built-in materials."""
        return dict(self._builtins)

    def list_custom(self) -> Dict[str, Material]:
        """Return only user-registered materials."""
        return dict(self._custom)

    def reset(self) -> None:
        """Remove all custom materials, restoring built-in defaults only."""
        self._custom.clear()

    def save_json(self, path, *, custom_only: bool = True) -> int:
        """
        Save materials to a JSON file.

        Parameters
        ----------
        path : str or Path
            Output file path.
        custom_only : bool
            If True (default), save only custom materials.
            If False, save everything including built-ins.

        Returns
        -------
        int
            Number of materials saved.
        """
        materials = self._custom if custom_only else self.list_all()
        data = {k: material_to_dict(v) for k, v in materials.items()}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return len(data)

    def load_json(self, path, *, force: bool = False) -> int:
        """
        Load materials from a JSON file and register them.

        Parameters
        ----------
        path : str or Path
            Input file path.
        force : bool
            If True, allow overwriting built-in materials.

        Returns
        -------
        int
            Number of materials loaded.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        count = 0
        for key, props in data.items():
            self.register(key, props, force=force)
            count += 1
        return count

    # Container protocol support
    def __contains__(self, key: str) -> bool:
        key = self._normalize_key(key)
        return key in self._custom or key in self._builtins

    def __len__(self) -> int:
        return len(set(list(self._builtins) + list(self._custom)))

    def __iter__(self):
        seen = set()
        for k in self._custom:
            seen.add(k)
            yield k
        for k in self._builtins:
            if k not in seen:
                yield k


# ── Module-level registry singleton ──────────────────────────────────────

registry = MaterialRegistry()
registry._load_builtins(MATERIAL_DB)


# Convenience aliases for quick scripting
register_material = registry.register
unregister_material = registry.unregister
