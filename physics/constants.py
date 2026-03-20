"""
Fundamental physical constants for thermodynamic computing.

All values in SI units. Sources: CODATA 2018 / NIST.
These are the constants that hardware research teams need when reasoning
about energy limits, thermal noise, and switching thresholds.
"""

import math

# Boltzmann constant (J/K)
k_B = 1.380649e-23

# Planck constant (J·s)
h_PLANCK = 6.62607015e-34

# Reduced Planck constant (J·s)
h_BAR = h_PLANCK / (2 * math.pi)

# Elementary charge (C)
E_CHARGE = 1.602176634e-19

# Speed of light (m/s)
C_LIGHT = 299792458.0

# Stefan-Boltzmann constant (W·m⁻²·K⁻⁴)
SIGMA_SB = 5.670374419e-8


def landauer_limit(T: float) -> float:
    """
    Minimum energy to irreversibly erase one bit at temperature T.

    E_min = k_B * T * ln(2)

    At 300 K this is ~2.85 × 10⁻²¹ J (~0.018 eV).
    This is the absolute floor for any irreversible computation.

    Parameters
    ----------
    T : float
        Temperature in Kelvin.

    Returns
    -------
    float
        Energy in Joules per bit erasure.
    """
    return k_B * T * math.log(2.0)


# Pre-computed common reference value
LANDAUER_LIMIT = landauer_limit(300.0)  # ~2.85e-21 J at room temp


def thermal_noise_voltage(T: float, R: float, bandwidth: float) -> float:
    """
    Johnson-Nyquist thermal noise voltage (RMS).

    V_n = sqrt(4 * k_B * T * R * Δf)

    This sets the noise floor for any electrical measurement at temperature T.
    Hardware teams use this to determine minimum signal levels.

    Parameters
    ----------
    T : float
        Temperature in Kelvin.
    R : float
        Resistance in Ohms.
    bandwidth : float
        Measurement bandwidth in Hz.

    Returns
    -------
    float
        RMS noise voltage in Volts.
    """
    return math.sqrt(4.0 * k_B * T * R * bandwidth)


def thermal_energy(T: float) -> float:
    """
    Characteristic thermal energy at temperature T.

    E_th = k_B * T

    This is the energy scale that competes with gate switching energy.
    When gate energy ≈ E_th, thermal noise dominates computation.

    Parameters
    ----------
    T : float
        Temperature in Kelvin.

    Returns
    -------
    float
        Thermal energy in Joules.
    """
    return k_B * T


def bits_per_joule(T: float) -> float:
    """
    Theoretical maximum irreversible bit erasures per Joule at temperature T.

    This is the inverse of the Landauer limit — the ultimate efficiency ceiling.

    Parameters
    ----------
    T : float
        Temperature in Kelvin.

    Returns
    -------
    float
        Maximum bit erasures per Joule.
    """
    return 1.0 / landauer_limit(T)
