"""Paradigm Comparison tab — layout and callback."""

import numpy as np
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

from aethermor.physics.constants import landauer_limit
from aethermor.physics.energy_models import (
    CMOSGateEnergy, AdiabaticGateEnergy, ReversibleGateEnergy,
)
from aethermor.app import NODE_OPTIONS


def layout():
    return html.Div([
        html.H3("CMOS vs. Adiabatic vs. Reversible \u2014 Which wins?"),
        html.P("Compare energy per gate switch across paradigms. "
               "Drag the frequency slider to see the adiabatic crossover "
               "point shift in real time.",
               style={"color": "#555", "marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.Label("Technology Node (nm)"),
                dcc.Dropdown(id="par-node", options=[{"label": f"{n} nm", "value": n}
                             for n in NODE_OPTIONS], value=7, clearable=False),
            ], style={"width": "160px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Temperature (K)"),
                dcc.Slider(id="par-temp", min=4, max=500, step=1, value=300,
                           marks={4: "4 K", 77: "77 K", 300: "300 K", 400: "400 K", 500: "500 K"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "400px", "display": "inline-block",
                       "verticalAlign": "top"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(dcc.Graph(id="par-chart", style={"height": "500px"})),
        html.Div(id="par-detail"),
    ])


@callback(
    Output("par-chart", "figure"),
    Output("par-detail", "children"),
    Input("par-node", "value"),
    Input("par-temp", "value"),
)
def update_paradigm(node, T):
    freqs = np.logspace(5, 11, 100)
    E_landauer = landauer_limit(T)

    cmos_model = CMOSGateEnergy(tech_node_nm=node)
    adiab_model = AdiabaticGateEnergy(tech_node_nm=node)
    rev_model = ReversibleGateEnergy()

    cmos_e = [cmos_model.energy_per_switch(f, T) for f in freqs]
    adiab_e = [adiab_model.energy_per_switch(f, T) for f in freqs]
    rev_e = [rev_model.energy_per_switch(f, T) for f in freqs]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=freqs, y=cmos_e, name="CMOS",
                             line=dict(width=2, color="#e53935")))
    fig.add_trace(go.Scatter(x=freqs, y=adiab_e, name="Adiabatic",
                             line=dict(width=2, color="#1e88e5")))
    fig.add_trace(go.Scatter(x=freqs, y=rev_e, name="Reversible",
                             line=dict(width=2, color="#43a047")))
    fig.add_hline(y=E_landauer, line_dash="dash", line_color="orange",
                  annotation_text=f"Landauer limit ({E_landauer:.2e} J)")

    try:
        f_cross = adiab_model.crossover_frequency(cmos_model)
        fig.add_vline(x=f_cross, line_dash="dot", line_color="#888",
                      annotation_text=f"Crossover: {f_cross:.1e} Hz")
        cross_text = (
            f"\u26a1 Adiabatic beats CMOS below {f_cross:.1e} Hz "
            f"({f_cross/1e6:.0f} MHz) at {node} nm, {T} K."
        )
    except Exception:
        cross_text = "No crossover found in this range."

    fig.update_layout(
        title=f"Energy per Gate Switch \u2014 {node} nm at {T} K",
        xaxis_title="Frequency (Hz)",
        yaxis_title="Energy per Switch (J)",
        xaxis_type="log",
        yaxis_type="log",
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    detail = html.P(cross_text, style={"fontWeight": "bold", "color": "#1565c0"})
    return fig, detail
