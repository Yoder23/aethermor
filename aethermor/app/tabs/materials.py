"""Material Ranking tab — layout and callback."""

from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

from aethermor.analysis.thermal_optimizer import ThermalOptimizer
from aethermor.app import COOLING_PRESETS, NODE_OPTIONS, COLORS, _material_options


def layout():
    return html.Div([
        html.H3("Which substrate lets you pack the most compute?"),
        html.P("Ranks materials by maximum gate density before hitting "
               "the thermal wall. Adjust tech node, frequency, and cooling "
               "to see how the ranking shifts.",
               style={"color": "#555", "marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.Label("Technology Node (nm)"),
                dcc.Dropdown(id="mat-node", options=[{"label": f"{n} nm", "value": n}
                             for n in NODE_OPTIONS], value=7, clearable=False),
            ], style={"width": "180px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Frequency (GHz)"),
                dcc.Slider(id="mat-freq", min=0.1, max=20, step=0.1, value=1,
                           marks={0.1: "0.1", 1: "1", 5: "5", 10: "10", 20: "20"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "300px", "display": "inline-block", "marginRight": "16px",
                       "verticalAlign": "top"}),
            html.Div([
                html.Label("Cooling"),
                dcc.Dropdown(id="mat-cooling", options=[
                    {"label": f"{v[0]} (h={v[1]})", "value": k}
                    for k, v in COOLING_PRESETS.items()
                ], value="heatsink", clearable=False),
            ], style={"width": "280px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Materials"),
                dcc.Dropdown(
                    id="mat-materials",
                    options=_material_options(),
                    value=["silicon", "diamond", "silicon_carbide", "gallium_arsenide", "gallium_nitride"],
                    multi=True,
                ),
            ], style={"width": "500px", "display": "inline-block"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(dcc.Graph(id="mat-chart", style={"height": "500px"})),
        html.Div(id="mat-detail", style={"marginTop": "12px"}),
    ])


@callback(
    Output("mat-chart", "figure"),
    Output("mat-detail", "children"),
    Input("mat-node", "value"),
    Input("mat-freq", "value"),
    Input("mat-cooling", "value"),
    Input("mat-materials", "value"),
)
def update_material(node, freq_ghz, cooling_key, materials):
    if not materials:
        return go.Figure(), "Select at least one material."
    h_conv = COOLING_PRESETS[cooling_key][1]
    opt = ThermalOptimizer(tech_node_nm=node, frequency_Hz=freq_ghz * 1e9)
    ranking = opt.material_ranking(h_conv=h_conv, materials=materials)

    names = [r["material_name"] for r in ranking]
    densities = [r["max_density"] for r in ranking]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=densities,
        marker_color=COLORS[:len(names)],
        text=[f"{d:.1e}" for d in densities],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>"
                      "Max density: %{y:.2e} gates/elem<br>"
                      "<extra></extra>",
    ))
    fig.update_layout(
        title=f"Max Gate Density by Substrate ({node} nm, {freq_ghz} GHz, "
              f"{COOLING_PRESETS[cooling_key][0]})",
        yaxis_title="Max Gate Density (gates/element)",
        yaxis_type="log",
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    if len(ranking) >= 2:
        ratio = ranking[0]["max_density"] / max(ranking[-1]["max_density"], 1)
        detail = html.P(
            f"\U0001f3c6 {ranking[0]['material_name']} sustains {ratio:.0f}\u00d7 higher "
            f"density than {ranking[-1]['material_name']} under these conditions.",
            style={"fontWeight": "bold", "color": "#2196F3"},
        )
    else:
        detail = ""
    return fig, detail
