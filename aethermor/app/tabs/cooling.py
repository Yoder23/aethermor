"""Cooling Analysis tab — layout and callback."""

import numpy as np
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

from aethermor.physics.materials import get_material
from aethermor.analysis.thermal_optimizer import ThermalOptimizer
from aethermor.app import COOLING_PRESETS, NODE_OPTIONS, _material_options


def layout():
    return html.Div([
        html.H3("How much cooling do you need?"),
        html.P("Shows temperature vs. cooling coefficient for a given "
               "material and gate density. See where diminishing returns "
               "kick in \u2014 the conduction floor.",
               style={"color": "#555", "marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.Label("Material"),
                dcc.Dropdown(id="cool-mat", options=_material_options(),
                             value="silicon", clearable=False),
            ], style={"width": "220px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Technology Node (nm)"),
                dcc.Dropdown(id="cool-node", options=[{"label": f"{n} nm", "value": n}
                             for n in NODE_OPTIONS], value=7, clearable=False),
            ], style={"width": "160px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Frequency (GHz)"),
                dcc.Slider(id="cool-freq", min=0.1, max=20, step=0.1, value=1,
                           marks={0.1: "0.1", 1: "1", 5: "5", 10: "10", 20: "20"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "300px", "display": "inline-block", "marginRight": "16px",
                       "verticalAlign": "top"}),
            html.Div([
                html.Label("Gate Density (gates/element)"),
                dcc.Slider(id="cool-density", min=3, max=8, step=0.1, value=5,
                           marks={3: "1e3", 4: "1e4", 5: "1e5", 6: "1e6", 7: "1e7", 8: "1e8"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "350px", "display": "inline-block",
                       "verticalAlign": "top"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(dcc.Graph(id="cool-chart", style={"height": "500px"})),
        html.Div(id="cool-detail"),
    ])


@callback(
    Output("cool-chart", "figure"),
    Output("cool-detail", "children"),
    Input("cool-mat", "value"),
    Input("cool-node", "value"),
    Input("cool-freq", "value"),
    Input("cool-density", "value"),
)
def update_cooling(mat_key, node, freq_ghz, log_density):
    density = 10 ** log_density
    opt = ThermalOptimizer(tech_node_nm=node, frequency_Hz=freq_ghz * 1e9)
    h_values = list(np.logspace(0.5, 4.8, 80))
    sweep = opt.cooling_sweep(material_key=mat_key, gate_density=density,
                              h_values=h_values)

    mat = get_material(mat_key)
    h_list = [s["h_conv"] for s in sweep]
    t_list = [min(s["T_max_K"], mat.max_operating_temp + 500) for s in sweep]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h_list, y=t_list, mode="lines+markers", name="T_max",
        marker=dict(size=4), line=dict(width=2, color="#2196F3"),
    ))
    fig.add_hline(y=mat.max_operating_temp, line_dash="dash",
                  line_color="red",
                  annotation_text=f"Thermal limit ({mat.max_operating_temp:.0f} K)")
    fig.add_hline(y=300, line_dash="dot", line_color="gray",
                  annotation_text="Ambient (300 K)")
    fig.add_hrect(y0=250, y1=mat.max_operating_temp,
                  fillcolor="green", opacity=0.05, line_width=0)

    fig.update_layout(
        title=f"Temperature vs. Cooling \u2014 {mat.name}, {density:.0e} gates/elem, "
              f"{node} nm @ {freq_ghz} GHz",
        xaxis_title="Cooling Coefficient h (W/m\u00b2\u00b7K)",
        yaxis_title="Peak Temperature (K)",
        xaxis_type="log",
        yaxis_range=[250, max(max(t_list) * 1.05, mat.max_operating_temp + 100)],
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    req = opt.find_min_cooling(mat_key, gate_density=density)
    if req["min_h_conv"] == float('inf'):
        detail = html.P(
            "\u26a0\ufe0f Impossible: conduction floor already exceeds thermal limit. "
            "Need a higher-k material or lower density.",
            style={"color": "red", "fontWeight": "bold"},
        )
    else:
        detail = html.P(
            f"\u2705 Minimum cooling: h = {req['min_h_conv']:.0f} W/(m\u00b2\u00b7K) \u2192 "
            f"{req['cooling_category']}. "
            f"Conduction floor: {req['conduction_floor_K']:.0f} K.",
            style={"color": "#2e7d32", "fontWeight": "bold"},
        )
    return fig, detail
