"""Technology Roadmap tab — layout and callback."""

from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

from aethermor.analysis.tech_roadmap import TechnologyRoadmap
from aethermor.app import NODE_OPTIONS


def layout():
    return html.Div([
        html.H3("Technology Roadmap: How does scaling change the game?"),
        html.P("Energy per gate, Landauer gap, and paradigm crossover "
               "from 130 nm down to 1.4 nm.",
               style={"color": "#555", "marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.Label("Frequency (GHz)"),
                dcc.Slider(id="road-freq", min=0.1, max=20, step=0.1, value=1,
                           marks={0.1: "0.1", 1: "1", 5: "5", 10: "10", 20: "20"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "400px", "display": "inline-block", "marginRight": "24px",
                       "verticalAlign": "top"}),
            html.Div([
                html.Label("Y-axis"),
                dcc.RadioItems(id="road-metric", options=[
                    {"label": "Energy per gate (J)", "value": "energy"},
                    {"label": "Landauer gap (\u00d7)", "value": "gap"},
                ], value="energy", inline=True),
            ], style={"display": "inline-block", "verticalAlign": "top"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(dcc.Graph(id="road-chart", style={"height": "500px"})),
    ])


@callback(
    Output("road-chart", "figure"),
    Input("road-freq", "value"),
    Input("road-metric", "value"),
)
def update_roadmap(freq_ghz, metric):
    freq = freq_ghz * 1e9
    roadmap = TechnologyRoadmap()
    data = roadmap.energy_roadmap(frequency_Hz=freq)

    nodes = [d["node_nm"] for d in data]

    fig = go.Figure()
    if metric == "energy":
        fig.add_trace(go.Scatter(x=nodes, y=[d["E_cmos_J"] for d in data],
                                 name="CMOS", line=dict(width=2, color="#e53935")))
        fig.add_trace(go.Scatter(x=nodes, y=[d["E_adiabatic_J"] for d in data],
                                 name="Adiabatic", line=dict(width=2, color="#1e88e5")))
        fig.add_trace(go.Scatter(x=nodes, y=[d["E_reversible_J"] for d in data],
                                 name="Reversible", line=dict(width=2, color="#43a047")))
        fig.add_trace(go.Scatter(x=nodes, y=[d["E_landauer_J"] for d in data],
                                 name="Landauer limit", line=dict(dash="dash", color="orange")))
        fig.update_layout(yaxis_title="Energy per Gate Switch (J)")
        title = f"Energy Scaling by Node @ {freq_ghz} GHz"
    else:
        fig.add_trace(go.Scatter(x=nodes, y=[d["gap_cmos"] for d in data],
                                 name="CMOS gap", line=dict(width=2, color="#e53935")))
        fig.add_trace(go.Scatter(x=nodes, y=[d["gap_adiabatic"] for d in data],
                                 name="Adiabatic gap", line=dict(width=2, color="#1e88e5")))
        fig.add_trace(go.Scatter(x=nodes, y=[d["gap_reversible"] for d in data],
                                 name="Reversible gap", line=dict(width=2, color="#43a047")))
        fig.add_hline(y=1, line_dash="dash", line_color="orange",
                      annotation_text="Landauer limit (1\u00d7)")
        fig.update_layout(yaxis_title="Landauer Gap (\u00d7)")
        title = f"Distance from Landauer Limit by Node @ {freq_ghz} GHz"

    fig.update_layout(
        title=title,
        xaxis_title="Technology Node (nm)",
        xaxis_type="log",
        yaxis_type="log",
        xaxis=dict(autorange="reversed"),
        template="plotly_white",
        margin=dict(t=60, b=40),
    )
    return fig
