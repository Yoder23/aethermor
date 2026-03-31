"""
Gate energy models for different computing paradigms.

Each model computes energy-per-gate-switch as a function of technology node,
supply voltage, temperature, and switching frequency. These are the models
hardware researchers use to estimate power budgets.

Built-in models:
  - CMOSGateEnergy: Conventional CMOS dynamic + leakage power
  - AdiabaticGateEnergy: Adiabatic/charge-recovery logic
  - ReversibleGateEnergy: Idealized reversible computing (Fredkin/Toffoli)
  - LandauerLimitEnergy: Theoretical floor (k_B T ln 2 per erasure)

Extensibility
-------------
Register a custom computing paradigm::

    from aethermor.physics.energy_models import paradigm_registry, EnergyModel

    @dataclass
    class SpintronicGateEnergy:
        '''Custom spintronic computing energy model.'''
        tech_node_nm: float = 7.0
        spin_current_A: float = 1e-6
        switching_time_s: float = 1e-9
        resistance_ohm: float = 1e4

        def energy_per_switch(self, frequency: float = 1e9,
                              T: float = 300.0) -> float:
            return self.spin_current_A**2 * self.resistance_ohm * self.switching_time_s

        def landauer_gap(self, T: float = 300.0,
                         frequency: float = 1e9) -> float:
            from aethermor.physics.constants import landauer_limit
            return self.energy_per_switch(frequency, T) / landauer_limit(T)

    paradigm_registry.register("spintronic", SpintronicGateEnergy)

    # Now "spintronic" works in FunctionalBlock(paradigm="spintronic", ...)
    # and everywhere else in the framework.

Usage example — find the technology node where adiabatic logic beats CMOS:

    >>> cmos = CMOSGateEnergy(tech_node_nm=7)
    >>> adiabatic = AdiabaticGateEnergy(tech_node_nm=7)
    >>> for freq in [1e9, 1e10, 1e11]:
    ...     print(f"{freq/1e9:.0f} GHz: CMOS={cmos.energy_per_switch(freq):.2e} J, "
    ...           f"Adiabatic={adiabatic.energy_per_switch(freq):.2e} J")
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any, Type, runtime_checkable
try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

from aethermor.physics.constants import k_B, landauer_limit


# ── Energy Model Protocol ────────────────────────────────────────────────

@runtime_checkable
class EnergyModel(Protocol):
    """
    Protocol that all computing paradigm energy models must satisfy.

    Any class with these two methods can be used as an energy model
    throughout Aethermor — in ChipFloorplan, ThermalOptimizer, the
    interactive UI, and all analysis tools.

    Required Methods
    ----------------
    energy_per_switch(frequency, T) -> float
        Energy in Joules per gate switching event.
    landauer_gap(T, frequency) -> float
        Ratio of actual energy to the Landauer limit (k_B T ln 2).
        Values >> 1 mean room for efficiency improvement.

    The protocol is runtime-checkable::

        >>> isinstance(CMOSGateEnergy(), EnergyModel)
        True
        >>> isinstance(my_custom_model, EnergyModel)
        True  # if it has the right methods
    """
    def energy_per_switch(self, frequency: float = 1e9,
                          T: float = 300.0) -> float: ...
    def landauer_gap(self, T: float = 300.0,
                     frequency: float = 1e9) -> float: ...


@dataclass
class CMOSGateEnergy:
    """
    Conventional CMOS gate switching energy model.

    E_dynamic = C_load · V_dd² per switch
    P_leakage = I_leak · V_dd (always-on, temperature-dependent)

    At 7 nm: C_load ≈ 0.5 fF, V_dd ≈ 0.7 V → E_dynamic ≈ 2.5e-16 J
    That's ~10⁵ × the Landauer limit at 300 K.

    Parameters
    ----------
    tech_node_nm : float
        Technology node in nanometers (e.g. 7, 14, 28, 45, 65, 130).
    V_dd : float or None
        Supply voltage in Volts. If None, estimated from tech node.
    C_load : float or None
        Load capacitance in Farads. If None, estimated from tech node.
    I_leak_ref : float
        Reference leakage current at 300 K in Amps (per gate).
    """
    tech_node_nm: float = 7.0
    V_dd: float = None
    C_load: float = None
    I_leak_ref: float = 1e-9  # ~1 nA per gate at 300 K for modern process

    def __post_init__(self):
        # Empirical V_dd scaling: follows Dennard scaling above ~20 nm,
        # but floors at ~0.7 V below 20 nm (Dennard breakdown).
        # Data points: 130nm→1.2V, 65nm→1.0V, 45nm→0.9V, 28nm→0.85V,
        #              14nm→0.75V, 7nm→0.7V, 3nm→0.7V
        if self.V_dd is None:
            if self.tech_node_nm >= 45:
                self.V_dd = 0.75 + 0.0035 * self.tech_node_nm
            else:
                # Below 45 nm, V_dd floors around 0.7-0.85 V
                self.V_dd = 0.65 + 0.007 * self.tech_node_nm
            self.V_dd = min(self.V_dd, 1.8)  # cap at older nodes
        if self.C_load is None:
            # C_load scales roughly linearly with feature size
            self.C_load = 0.5e-15 * (self.tech_node_nm / 7.0)

    def dynamic_energy(self) -> float:
        """Energy per gate switch (Joules) from charging/discharging C_load."""
        return self.C_load * self.V_dd ** 2

    def leakage_power(self, T: float = 300.0) -> float:
        """
        Leakage power per gate (Watts). Exponentially temperature-dependent.

        I_leak(T) ≈ I_leak_ref · exp(α · (T - 300))
        where α ≈ 0.02 per Kelvin (subthreshold leakage scaling).

        Clamped to prevent overflow at extreme temperatures (>1000 K).
        """
        alpha = 0.02  # per Kelvin
        exponent = alpha * (T - 300.0)
        # Clamp to prevent math overflow; exp(700) ≈ 1e304 (near float max)
        exponent = min(exponent, 700.0)
        I_leak = self.I_leak_ref * math.exp(exponent)
        return I_leak * self.V_dd

    def energy_per_switch(self, frequency: float = 1e9, T: float = 300.0) -> float:
        """
        Total energy per gate switching event, including amortized leakage.

        E_total = E_dynamic + P_leakage / frequency

        At high frequencies, dynamic dominates.
        At low frequencies, leakage dominates.
        """
        E_dyn = self.dynamic_energy()
        P_leak = self.leakage_power(T)
        E_leak_per_switch = P_leak / max(frequency, 1.0)
        return E_dyn + E_leak_per_switch

    def landauer_gap(self, T: float = 300.0, frequency: float = 1e9) -> float:
        """
        Ratio of actual energy to Landauer limit.

        Values >> 1 mean there's room for improvement.
        Current CMOS at 7 nm is typically ~10⁵ above Landauer.
        """
        return self.energy_per_switch(frequency, T) / landauer_limit(T)


@dataclass
class AdiabaticGateEnergy:
    """
    Adiabatic (charge-recovery) logic energy model.

    In adiabatic computing, charge is recycled rather than dumped to ground.
    Energy dissipation scales as (RC/T_switch) · C · V² instead of C · V².

    E_adiabatic = (R · C / T_clock) · C · V² = R · C² · V² · f

    This means energy per switch DECREASES with slower switching —
    the opposite of CMOS leakage behavior.

    The crossover frequency where adiabatic beats CMOS is a key research question.

    Parameters
    ----------
    tech_node_nm : float
        Technology node in nanometers.
    V_dd : float or None
        Supply voltage. If None, estimated from tech node.
    C_load : float or None
        Load capacitance. If None, estimated from tech node.
    R_switch : float
        On-resistance of the switching device (Ohms).
    """
    tech_node_nm: float = 7.0
    V_dd: float = None
    C_load: float = None
    R_switch: float = 1000.0  # ~1 kΩ typical FET on-resistance

    def __post_init__(self):
        if self.V_dd is None:
            if self.tech_node_nm >= 45:
                self.V_dd = 0.75 + 0.0035 * self.tech_node_nm
            else:
                self.V_dd = 0.65 + 0.007 * self.tech_node_nm
            self.V_dd = min(self.V_dd, 1.8)
        if self.C_load is None:
            self.C_load = 0.5e-15 * (self.tech_node_nm / 7.0)

    def energy_per_switch(self, frequency: float = 1e9, T: float = 300.0) -> float:
        """
        Energy per switching event for adiabatic logic.

        E = R · C² · V² · f + thermal_floor

        The thermal floor prevents claiming sub-Landauer operation:
        each irreversible bit erasure still costs ≥ k_B·T·ln(2).
        """
        # Dissipative component: RC²V²f
        E_dissipative = self.R_switch * (self.C_load ** 2) * (self.V_dd ** 2) * frequency

        # Irreversible floor: at least 1 bit erasure per switch
        E_floor = landauer_limit(T)

        return max(E_dissipative, E_floor)

    def crossover_frequency(self, cmos: CMOSGateEnergy, T: float = 300.0) -> float:
        """
        Frequency below which adiabatic logic uses less energy than CMOS.

        This is a KEY research metric. Below this frequency, charge-recovery
        logic is more efficient. Above it, the overhead isn't worth it.

        Returns
        -------
        float
            Crossover frequency in Hz. Returns inf if adiabatic never wins.
        """
        E_cmos_dynamic = cmos.dynamic_energy()
        # Solve: R · C² · V² · f = E_cmos_dynamic
        denom = self.R_switch * (self.C_load ** 2) * (self.V_dd ** 2)
        if denom <= 0:
            return float('inf')
        return E_cmos_dynamic / denom

    def landauer_gap(self, T: float = 300.0, frequency: float = 1e9) -> float:
        """Ratio of actual energy to Landauer limit."""
        return self.energy_per_switch(frequency, T) / landauer_limit(T)


@dataclass
class ReversibleGateEnergy:
    """
    Idealized reversible computing energy model (Fredkin/Toffoli gates).

    In fully reversible computation, no bits are erased, so the Landauer
    limit doesn't apply to the computation itself — only to:
      1. Input preparation (writing over old inputs)
      2. Output readout (if it destroys intermediate state)
      3. Error correction (syndrome measurement + erasure)

    E_reversible = (n_erasures_per_gate) · k_B · T · ln(2)  +  overhead

    The overhead comes from:
    - More gates needed (reversible circuits are larger than irreversible)
    - Ancilla bit management
    - Clock distribution for ordered evaluation

    Parameters
    ----------
    erasures_per_gate : float
        Average number of irreversible bit erasures per logical gate.
        Theoretical minimum is 0 for Toffoli/Fredkin, but practical
        implementations need ancilla cleanup → typically 1-3.
    gate_overhead_factor : float
        Multiplicative overhead from larger reversible circuits.
        A reversible version of an n-gate circuit typically needs 2-10× more gates.
    clock_overhead_J : float
        Energy overhead per gate from clock distribution and ordering.
    """
    erasures_per_gate: float = 1.0
    gate_overhead_factor: float = 3.0
    clock_overhead_J: float = 1e-20  # ~few k_B·T at 300 K

    def energy_per_switch(self, frequency: float = 1e9, T: float = 300.0) -> float:
        """
        Energy per logical gate operation.

        The key insight: this scales with T, not with V²·C.
        At lower temperatures, reversible computing gets cheaper.
        """
        E_erasure = self.erasures_per_gate * landauer_limit(T)
        return (E_erasure + self.clock_overhead_J) * self.gate_overhead_factor

    def landauer_gap(self, T: float = 300.0, frequency: float = 1e9) -> float:
        """Ratio of actual energy to Landauer limit per erasure."""
        E_actual = self.energy_per_switch(frequency, T)
        E_limit = landauer_limit(T) * max(self.erasures_per_gate, 1e-30)
        return E_actual / E_limit

    def temperature_crossover(self, cmos: CMOSGateEnergy, frequency: float = 1e9) -> float:
        """
        Temperature below which reversible logic beats CMOS at given frequency.

        Solve: E_reversible(T) = E_cmos(T, f)

        Returns temperature in Kelvin, or inf if reversible never wins.
        """
        # Binary search for crossover temperature
        T_lo, T_hi = 1.0, 1000.0
        E_cmos_ref = cmos.energy_per_switch(frequency, T_hi)
        E_rev_ref = self.energy_per_switch(frequency, T_hi)

        # If reversible is already cheaper at T_hi, crossover is above T_hi
        if E_rev_ref < E_cmos_ref:
            return float('inf')  # always cheaper in this range

        for _ in range(64):  # binary search
            T_mid = (T_lo + T_hi) / 2.0
            E_cmos = cmos.energy_per_switch(frequency, T_mid)
            E_rev = self.energy_per_switch(frequency, T_mid)
            if E_rev < E_cmos:
                T_lo = T_mid
            else:
                T_hi = T_mid

        return (T_lo + T_hi) / 2.0


@dataclass
class LandauerLimitEnergy:
    """
    Theoretical Landauer limit — the absolute floor.

    E = k_B · T · ln(2) per irreversible bit erasure.

    This model exists to serve as a reference line in comparisons.
    No physical device can do better than this for irreversible operations.
    """
    bits_per_gate: float = 1.0  # number of bit erasures per gate

    def energy_per_switch(self, frequency: float = 1e9, T: float = 300.0) -> float:
        """Energy per gate, assuming bits_per_gate erasures."""
        return self.bits_per_gate * landauer_limit(T)

    def landauer_gap(self, T: float = 300.0, frequency: float = 1e9) -> float:
        """Always 1.0 by definition."""
        return 1.0


# ── Paradigm Registry ───────────────────────────────────────────────────

class ParadigmRegistry:
    """
    Registry for computing paradigm energy models.

    Maps paradigm name strings (e.g. "cmos", "adiabatic", "spintronic")
    to model classes that satisfy the EnergyModel protocol.

    Built-in paradigms are pre-registered at module load.  Engineers can
    register custom paradigms at runtime and they immediately become
    available in ChipFloorplan, ThermalOptimizer, and the interactive UI.

    Usage
    -----
    ::

        from aethermor.physics.energy_models import paradigm_registry

        # Register a custom paradigm
        paradigm_registry.register("spintronic", SpintronicGateEnergy)

        # Create an instance with kwargs
        model = paradigm_registry.create("spintronic", tech_node_nm=7)

        # Use it in a chip floorplan
        block = FunctionalBlock(..., paradigm="spintronic")
    """

    def __init__(self):
        self._factories: Dict[str, type] = {}
        self._next_id: int = 5  # 0=idle, 1=cmos, 2=adiabatic, 3=reversible, 4=landauer
        self._ids: Dict[str, int] = {
            "idle": 0, "cmos": 1, "adiabatic": 2, "reversible": 3,
            "landauer": 4,
        }

    def register(self, name: str, model_class: type, *,
                 force: bool = False) -> None:
        """
        Register a computing paradigm.

        Parameters
        ----------
        name : str
            Paradigm name (lowercase).  e.g. "spintronic", "quantum"
        model_class : type
            A class whose instances satisfy the EnergyModel protocol.
            Must have ``energy_per_switch(frequency, T)`` and
            ``landauer_gap(T, frequency)`` methods.
        force : bool
            If True, allow overwriting a built-in paradigm.

        Raises
        ------
        TypeError
            If *model_class* does not satisfy the EnergyModel protocol.
        KeyError
            If *name* is a built-in paradigm and *force* is False.
        """
        name = name.lower()

        # Protocol check: instantiate with defaults and verify interface
        try:
            test_instance = model_class()
        except TypeError:
            # Class needs constructor args — check the class itself
            if not (hasattr(model_class, 'energy_per_switch')
                    and hasattr(model_class, 'landauer_gap')):
                raise TypeError(
                    f"{model_class.__name__} does not satisfy the EnergyModel "
                    f"protocol.  It must have energy_per_switch(frequency, T) "
                    f"and landauer_gap(T, frequency) methods."
                )
        else:
            if not isinstance(test_instance, EnergyModel):
                raise TypeError(
                    f"{model_class.__name__} does not satisfy the EnergyModel "
                    f"protocol.  It must have energy_per_switch(frequency, T) "
                    f"and landauer_gap(T, frequency) methods."
                )

        if name in self._factories and not force:
            if name in ("cmos", "adiabatic", "reversible", "landauer"):
                raise KeyError(
                    f"'{name}' is a built-in paradigm.  Use force=True to "
                    f"override, or choose a different name."
                )

        self._factories[name] = model_class

        # Assign a unique integer ID for paradigm maps
        if name not in self._ids:
            self._ids[name] = self._next_id
            self._next_id += 1

    def create(self, name: str, **kwargs) -> Any:
        """
        Create an energy model instance for the named paradigm.

        Parameters
        ----------
        name : str
            Paradigm name.
        **kwargs
            Passed to the model class constructor (e.g. tech_node_nm=7).

        Returns
        -------
        EnergyModel
            An instance of the registered model class.
        """
        name = name.lower()
        if name == "idle":
            return None
        if name not in self._factories:
            raise KeyError(
                f"Unknown paradigm '{name}'.  "
                f"Available: {sorted(self._factories.keys())}.  "
                f"Register custom paradigms with "
                f"paradigm_registry.register(name, ModelClass)."
            )
        return self._factories[name](**kwargs)

    def paradigm_id(self, name: str) -> int:
        """
        Integer ID for paradigm-map visualization.

        Built-in IDs: idle=0, cmos=1, adiabatic=2, reversible=3.
        Custom paradigms get IDs starting from 4.
        """
        name = name.lower()
        if name not in self._ids:
            raise KeyError(f"Unknown paradigm '{name}'.")
        return self._ids[name]

    def list_paradigms(self) -> List[str]:
        """Return all registered paradigm names."""
        return sorted(self._factories.keys())

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._factories or name.lower() == "idle"

    def __len__(self) -> int:
        return len(self._factories) + 1  # +1 for "idle"


# ── Module-level paradigm registry singleton ─────────────────────────────

paradigm_registry = ParadigmRegistry()
paradigm_registry.register("cmos", CMOSGateEnergy)
paradigm_registry.register("adiabatic", AdiabaticGateEnergy)
paradigm_registry.register("reversible", ReversibleGateEnergy)
paradigm_registry.register("landauer", LandauerLimitEnergy)

# Convenience aliases
register_paradigm = paradigm_registry.register
