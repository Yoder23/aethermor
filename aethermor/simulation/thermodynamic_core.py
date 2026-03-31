# thermodynamic_core.py
import numpy as np
import math

class ThermodynamicAICore:
    """
    Minimal Landauer-aware bookkeeping layer.

    - Tracks an approximate number of "informational bits" processed.
    - Computes the associated Landauer lower-bound energy cost.
    - Exposes cumulative metrics so AethermorSimV2 can log them per step.

    This is deliberately simple: we're not claiming silicon-accurate Joules,
    just a consistent in-sim thermodynamic accounting.
    """

    def __init__(self,
                 k_B=1.380649e-23,  # Boltzmann constant
                 bits_per_unit_activity=1e5,
                 T_ref=300.0):
        self.k_B = float(k_B)
        self.bits_per_unit_activity = float(bits_per_unit_activity)
        self.T_ref = float(T_ref)

        self.total_bits = 0.0
        self.total_J = 0.0

    def optimal_activity(self, T_field, info_gain_coeff: float = 1.0) -> float:
        """
        Return a scalar activity factor u in [0,1] based on temperature.
        Warmer fields are "more expensive", so we reduce activity.
        """
        T_mean = float(np.mean(T_field))
        if T_mean <= 0.0:
            T_mean = self.T_ref
        cheapness = self.T_ref / T_mean  # >1 if cooler than reference
        u = info_gain_coeff * cheapness
        return float(np.clip(u, 0.0, 1.0))

    def step_accumulate(
        self,
        T_field,
        activity_mask=None,
        info_gain_coeff: float = 1.0,
        info_bits_step=None,
        landauer_J_step=None,
        **_unused,
    ):
        """
        Called once per simulator step.

        Two supported modes:
        1) Internal estimate:
           - Estimate activity from T_field/activity_mask.
           - Convert to bit count and compute Landauer lower bound.
        2) External feed-through:
           - Accept externally estimated `info_bits_step` and/or
             `landauer_J_step` from the simulator.
        """
        T_field = np.asarray(T_field, dtype=float)
        T_mean = float(np.mean(T_field))
        if T_mean <= 0.0:
            T_mean = self.T_ref

        if info_bits_step is None:
            if activity_mask is None:
                activity_mask = np.ones_like(T_field)
            activity_level = float(np.mean(activity_mask))
            u = self.optimal_activity(T_field, info_gain_coeff=info_gain_coeff)
            bits_step = self.bits_per_unit_activity * u * activity_level
        else:
            bits_step = float(max(0.0, info_bits_step))

        if landauer_J_step is None:
            landauer_per_bit = self.k_B * T_mean * math.log(2.0)
            J_step = landauer_per_bit * bits_step
        else:
            J_step = float(max(0.0, landauer_J_step))

        self.total_bits += bits_step
        self.total_J += J_step

        return bits_step, J_step

    def metrics(self):
        """
        Return cumulative metrics so they can be logged into sim.metrics.
        """
        return {
            "landauer_J": float(self.total_J),
            "info_bits": float(self.total_bits),
        }
