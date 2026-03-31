"""SoC Thermal Map tab — layout and callback."""

from dash import dcc, html, Input, Output, callback, dash_table
import plotly.graph_objects as go

from aethermor.physics.materials import get_material
from aethermor.physics.chip_floorplan import ChipFloorplan
from aethermor.analysis.thermal_optimizer import ThermalOptimizer
from aethermor.app import COOLING_PRESETS, _material_options


def layout():
    return html.Div([
        html.H3("SoC Thermal Map: Where is the bottleneck?"),
        html.P("Thermal headroom per block on a heterogeneous SoC. "
               "Adjust cooling and frequency to find the configuration "
               "where every block stays under its thermal limit.",
               style={"color": "#555", "marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.Label("Cooling"),
                dcc.Dropdown(id="soc-cooling", options=[
                    {"label": f"{v[0]} (h={v[1]})", "value": k}
                    for k, v in COOLING_PRESETS.items()
                ], value="heatsink", clearable=False),
            ], style={"width": "280px", "display": "inline-block", "marginRight": "16px"}),
            html.Div([
                html.Label("Frequency (GHz)"),
                dcc.Slider(id="soc-freq", min=0.1, max=10, step=0.1, value=1,
                           marks={0.1: "0.1", 1: "1", 3: "3", 5: "5", 10: "10"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "300px", "display": "inline-block", "marginRight": "16px",
                       "verticalAlign": "top"}),
            html.Div([
                html.Label("Substrate"),
                dcc.Dropdown(id="soc-mat", options=_material_options(),
                             value="silicon", clearable=False),
            ], style={"width": "220px", "display": "inline-block"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(html.Div([
            dcc.Graph(id="soc-chart", style={"height": "420px"}),
            html.Div(id="soc-table", style={"marginTop": "8px"}),
        ])),
    ])


@callback(
    Output("soc-chart", "figure"),
    Output("soc-table", "children"),
    Input("soc-cooling", "value"),
    Input("soc-freq", "value"),
    Input("soc-mat", "value"),
)
def update_soc(cooling_key, freq_ghz, mat_key):
    h_conv = COOLING_PRESETS[cooling_key][1]
    freq = freq_ghz * 1e9

    soc = ChipFloorplan.modern_soc()
    soc.material = mat_key
    opt = ThermalOptimizer(tech_node_nm=7, frequency_Hz=freq,
                           element_size_m=soc.element_size_m)

    headroom = opt.thermal_headroom_map(soc, frequency_Hz=freq, h_conv=h_conv)

    names = [b["name"] for b in headroom]
    temps = [b["T_max_K"] for b in headroom]
    headrooms = [b["thermal_headroom_K"] for b in headroom]
    bottlenecks = [b["is_bottleneck"] for b in headroom]

    mat = get_material(mat_key)
    t_limit = mat.max_operating_temp

    colors = []
    for h_k, bn in zip(headrooms, bottlenecks):
        if h_k < 10:
            colors.append("#e53935")
        elif h_k < 50:
            colors.append("#ff9800")
        elif bn:
            colors.append("#ffc107")
        else:
            colors.append("#43a047")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=temps,
        marker_color=colors,
        text=[f"{t:.0f} K" for t in temps],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>"
                      "T_max: %{y:.1f} K<br>"
                      "<extra></extra>",
    ))
    fig.add_hline(y=t_limit, line_dash="dash", line_color="red",
                  annotation_text=f"Thermal limit ({t_limit:.0f} K)")
    fig.add_hline(y=300, line_dash="dot", line_color="gray",
                  annotation_text="Ambient")

    fig.update_layout(
        title=f"Per-Block Temperature \u2014 {mat.name}, "
              f"{COOLING_PRESETS[cooling_key][0]}, {freq_ghz} GHz",
        yaxis_title="Peak Temperature (K)",
        yaxis_range=[250, max(max(temps) * 1.08, t_limit + 50)],
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    table_data = []
    for b in headroom:
        table_data.append({
            "Block": b["name"],
            "Paradigm": b["paradigm"].upper(),
            "Density": f"{b['gate_density']:.1e}",
            "T_max (K)": f"{b['T_max_K']:.1f}",
            "Headroom (K)": f"{b['thermal_headroom_K']:.1f}",
            "Density Headroom": f"{b['density_headroom_factor']:.1f}\u00d7",
            "Bottleneck": "\U0001f525 YES" if b["is_bottleneck"] else "",
            "Action": b["recommended_action"],
        })

    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in table_data[0].keys()],
        data=table_data,
        style_cell={"textAlign": "left", "padding": "6px 10px",
                     "fontSize": "13px", "fontFamily": "Segoe UI, sans-serif"},
        style_header={"backgroundColor": "#f5f5f5", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"filter_query": '{Bottleneck} contains "YES"'},
             "backgroundColor": "#ffebee"},
        ],
    )

    return fig, table
