"""Aethermor dashboard — shared utilities and constants."""

import numpy as np
import plotly.express as px

from aethermor.physics.materials import registry as material_registry


COOLING_PRESETS = {
    "natural_air": ("Bare die, natural air", 10),
    "forced_air": ("Forced air (fan)", 100),
    "heatsink": ("Fan + heatsink", 1000),
    "liquid": ("Liquid cold plate", 5000),
    "microchannel": ("Microchannel / jet", 20000),
    "extreme": ("Extreme (50k)", 50000),
}

NODE_OPTIONS = [130, 65, 45, 28, 14, 7, 5, 3, 2, 1.4]

COLORS = px.colors.qualitative.Set2


def _all_materials():
    """Dynamic material list (built-in + custom)."""
    return sorted(material_registry.list_all().keys())


def _material_labels():
    all_mats = material_registry.list_all()
    return {k: all_mats[k].name for k in sorted(all_mats.keys())}


def _material_options():
    labels = _material_labels()
    return [{"label": labels[k], "value": k} for k in sorted(labels.keys())]


def fmt_exp(v):
    """Format a number in engineering-style scientific notation."""
    if v == 0:
        return "0"
    exp = int(np.floor(np.log10(abs(v))))
    mantissa = v / 10**exp
    return f"{mantissa:.1f}\u00d710^{exp}"
