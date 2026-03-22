#!/usr/bin/env python3
"""
Aethermor Interactive Explorer

Launch with:
    python app.py

Then open http://127.0.0.1:8050 in your browser.

Provides a live, interactive UI for exploring thermodynamic computing
design spaces — tweak parameters and see results instantly.
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import dash
    from dash import dcc, html, Input, Output, State, callback, dash_table
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    print("The interactive UI requires Dash and Plotly.")
    print("Install them with:")
    print()
    print("    pip install dash plotly")
    print()
    sys.exit(1)

import numpy as np
from physics.constants import k_B, landauer_limit
from physics.materials import MATERIAL_DB, get_material, registry as material_registry, Material, validate_material
from physics.energy_models import CMOSGateEnergy, AdiabaticGateEnergy, ReversibleGateEnergy, paradigm_registry
from physics.cooling import CoolingStack, THERMAL_LAYERS, cooling_registry
from physics.chip_floorplan import ChipFloorplan
from analysis.thermal_optimizer import ThermalOptimizer
from analysis.tech_roadmap import TechnologyRoadmap


# ── Helpers ──────────────────────────────────────────────────────────────

def _all_materials():
    """Dynamic material list (built-in + custom)."""
    return sorted(material_registry.list_all().keys())

def _material_labels():
    all_mats = material_registry.list_all()
    return {k: all_mats[k].name for k in sorted(all_mats.keys())}

def _material_options():
    labels = _material_labels()
    return [{"label": labels[k], "value": k} for k in sorted(labels.keys())]

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


def fmt_exp(v):
    """Format a number in engineering-style scientific notation."""
    if v == 0:
        return "0"
    exp = int(np.floor(np.log10(abs(v))))
    mantissa = v / 10**exp
    return f"{mantissa:.1f}×10^{exp}"


# ── App ──────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Aethermor Explorer",
    suppress_callback_exceptions=True,
)

# ── Layout ───────────────────────────────────────────────────────────────

HEADER = html.Div([
    html.H1("Aethermor Explorer", style={"margin": "0"}),
    html.P(
        "Interactive thermal design space exploration for thermodynamic computing.",
        style={"margin": "4px 0 0 0", "color": "#666", "fontSize": "14px"},
    ),
], style={"padding": "16px 24px", "borderBottom": "2px solid #2196F3",
          "background": "#fafafa"})

TABS = dcc.Tabs(id="tabs", value="tab-material", children=[
    dcc.Tab(label="Material Ranking", value="tab-material"),
    dcc.Tab(label="Cooling Analysis", value="tab-cooling"),
    dcc.Tab(label="Paradigm Comparison", value="tab-paradigm"),
    dcc.Tab(label="Technology Roadmap", value="tab-roadmap"),
    dcc.Tab(label="SoC Thermal Map", value="tab-soc"),
    dcc.Tab(label="\u2795 Custom Material", value="tab-custom"),
], style={"margin": "0 24px"})

app.layout = html.Div([
    HEADER,
    TABS,
    html.Div(id="tab-content", style={"padding": "24px"}),
], style={"fontFamily": "Segoe UI, Roboto, sans-serif", "maxWidth": "1200px",
          "margin": "0 auto"})


# ── Tab Layouts ──────────────────────────────────────────────────────────

def material_tab():
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


def cooling_tab():
    return html.Div([
        html.H3("How much cooling do you need?"),
        html.P("Shows temperature vs. cooling coefficient for a given "
               "material and gate density. See where diminishing returns "
               "kick in — the conduction floor.",
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


def paradigm_tab():
    return html.Div([
        html.H3("CMOS vs. Adiabatic vs. Reversible — Which wins?"),
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


def roadmap_tab():
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
                    {"label": "Landauer gap (×)", "value": "gap"},
                ], value="energy", inline=True),
            ], style={"display": "inline-block", "verticalAlign": "top"}),
        ], style={"marginBottom": "20px"}),
        dcc.Loading(dcc.Graph(id="road-chart", style={"height": "500px"})),
    ])


def soc_tab():
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

def custom_material_tab():
    """Tab for defining and registering custom materials at runtime."""
    # Show existing custom materials
    custom_mats = material_registry.list_custom()
    existing_rows = []
    for key, mat in custom_mats.items():
        existing_rows.append({
            "Key": key,
            "Name": mat.name,
            "k (W/m·K)": f"{mat.thermal_conductivity:.1f}",
            "c_p (J/kg·K)": f"{mat.specific_heat:.0f}",
            "ρ (kg/m³)": f"{mat.density:.0f}",
            "E_gap (eV)": f"{mat.bandgap_eV:.2f}",
        })

    _input_style = {"width": "100%", "padding": "6px", "borderRadius": "4px",
                     "border": "1px solid #ccc"}
    _label_style = {"fontWeight": "bold", "marginTop": "8px", "display": "block",
                     "fontSize": "13px"}

    return html.Div([
        html.H3("Define a Custom Material"),
        html.P(
            "Enter the thermal and electrical properties of any substrate "
            "you want to test. Once registered, your material will appear "
            "in every tab's material dropdown — ranked alongside the built-ins.",
            style={"color": "#555", "marginBottom": "16px"},
        ),
        html.Div([
            # Left column: inputs
            html.Div([
                html.Label("Registry Key (lowercase, no spaces)", style=_label_style),
                dcc.Input(id="cust-key", type="text", placeholder="e.g. boron_nitride",
                          style=_input_style),

                html.Label("Display Name", style=_label_style),
                dcc.Input(id="cust-name", type="text",
                          placeholder="e.g. Hexagonal Boron Nitride (h-BN)",
                          style=_input_style),

                html.Label("Thermal Conductivity k (W/(m·K))", style=_label_style),
                dcc.Input(id="cust-k", type="number", placeholder="600.0",
                          style=_input_style),

                html.Label("Specific Heat c_p (J/(kg·K))", style=_label_style),
                dcc.Input(id="cust-cp", type="number", placeholder="800.0",
                          style=_input_style),

                html.Label("Density ρ (kg/m³)", style=_label_style),
                dcc.Input(id="cust-rho", type="number", placeholder="2100.0",
                          style=_input_style),

                html.Label("Electrical Resistivity (Ω·m)", style=_label_style),
                dcc.Input(id="cust-rho-e", type="number", placeholder="1e15",
                          style=_input_style),

                html.Label("Max Operating Temperature (K)", style=_label_style),
                dcc.Input(id="cust-tmax", type="number", placeholder="1273.15",
                          style=_input_style),

                html.Label("Bandgap (eV) — 0 for metals", style=_label_style),
                dcc.Input(id="cust-gap", type="number", placeholder="6.0",
                          value=0.0, style=_input_style),

                html.Label("Notes (optional)", style=_label_style),
                dcc.Input(id="cust-notes", type="text",
                          placeholder="Source, context, or caveats",
                          style=_input_style),

                html.Br(),
                html.Button("Register Material", id="cust-register",
                            n_clicks=0,
                            style={"marginTop": "12px", "padding": "10px 24px",
                                   "backgroundColor": "#2196F3", "color": "white",
                                   "border": "none", "borderRadius": "4px",
                                   "cursor": "pointer", "fontSize": "14px",
                                   "fontWeight": "bold"}),

                html.Div(id="cust-status", style={"marginTop": "12px"}),
            ], style={"width": "420px", "display": "inline-block",
                       "verticalAlign": "top", "marginRight": "40px"}),

            # Right column: registered custom materials + reference
            html.Div([
                html.H4("Your Custom Materials", style={"marginTop": "0"}),
                html.Div(id="cust-table",
                         children=_render_custom_table(existing_rows)),
                html.Hr(),
                html.H4("Built-in Reference Values"),
                html.P("Use these as a sanity check for your custom material:",
                       style={"color": "#666", "fontSize": "13px"}),
                _render_builtin_reference(),
            ], style={"width": "600px", "display": "inline-block",
                       "verticalAlign": "top"}),
        ]),
    ])


def _render_custom_table(rows):
    """Render the custom materials table, or a placeholder if empty."""
    if not rows:
        return html.P("No custom materials registered yet.",
                       style={"color": "#999", "fontStyle": "italic"})
    return dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in rows[0].keys()],
        data=rows,
        style_cell={"textAlign": "left", "padding": "6px 10px",
                     "fontSize": "13px"},
        style_header={"backgroundColor": "#e3f2fd", "fontWeight": "bold"},
    )


def _render_builtin_reference():
    """Reference table of built-in material properties."""
    all_mats = material_registry.list_builtins()
    rows = []
    for key in sorted(all_mats.keys()):
        m = all_mats[key]
        rows.append({
            "Key": key,
            "k (W/m·K)": f"{m.thermal_conductivity:.0f}",
            "c_p": f"{m.specific_heat:.0f}",
            "ρ": f"{m.density:.0f}",
            "E_gap": f"{m.bandgap_eV:.2f}",
            "T_max (K)": f"{m.max_operating_temp:.0f}",
        })
    return dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in rows[0].keys()],
        data=rows,
        style_cell={"textAlign": "left", "padding": "4px 8px",
                     "fontSize": "12px"},
        style_header={"backgroundColor": "#f5f5f5", "fontWeight": "bold"},
    )

# ── Tab Router ───────────────────────────────────────────────────────────

@callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    if tab == "tab-material":
        return material_tab()
    elif tab == "tab-cooling":
        return cooling_tab()
    elif tab == "tab-paradigm":
        return paradigm_tab()
    elif tab == "tab-roadmap":
        return roadmap_tab()
    elif tab == "tab-soc":
        return soc_tab()
    elif tab == "tab-custom":
        return custom_material_tab()
    return html.P("Select a tab.")


# ── Callbacks ────────────────────────────────────────────────────────────

# ---- Material Ranking ----

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
    powers = [r["power_density_W_cm2"] for r in ranking]
    temps = [r["T_max_K"] for r in ranking]

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
            f"🏆 {ranking[0]['material_name']} sustains {ratio:.0f}× higher "
            f"density than {ranking[-1]['material_name']} under these conditions.",
            style={"fontWeight": "bold", "color": "#2196F3"},
        )
    else:
        detail = ""
    return fig, detail


# ---- Cooling Analysis ----

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
    # Material limit line
    fig.add_hline(y=mat.max_operating_temp, line_dash="dash",
                  line_color="red", annotation_text=f"Thermal limit ({mat.max_operating_temp:.0f} K)")
    # Ambient line
    fig.add_hline(y=300, line_dash="dot", line_color="gray",
                  annotation_text="Ambient (300 K)")

    # Shade safe zone
    fig.add_hrect(y0=250, y1=mat.max_operating_temp,
                  fillcolor="green", opacity=0.05, line_width=0)

    fig.update_layout(
        title=f"Temperature vs. Cooling — {mat.name}, {density:.0e} gates/elem, "
              f"{node} nm @ {freq_ghz} GHz",
        xaxis_title="Cooling Coefficient h (W/m²·K)",
        yaxis_title="Peak Temperature (K)",
        xaxis_type="log",
        yaxis_range=[250, max(max(t_list) * 1.05, mat.max_operating_temp + 100)],
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    # Find min cooling
    req = opt.find_min_cooling(mat_key, gate_density=density)
    if req["min_h_conv"] == float('inf'):
        detail = html.P(
            f"⚠️ Impossible: conduction floor already exceeds thermal limit. "
            f"Need a higher-k material or lower density.",
            style={"color": "red", "fontWeight": "bold"},
        )
    else:
        detail = html.P(
            f"✅ Minimum cooling: h = {req['min_h_conv']:.0f} W/(m²·K) → "
            f"{req['cooling_category']}. "
            f"Conduction floor: {req['conduction_floor_K']:.0f} K.",
            style={"color": "#2e7d32", "fontWeight": "bold"},
        )
    return fig, detail


# ---- Paradigm Comparison ----

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

    # Find crossover
    try:
        f_cross = adiab_model.crossover_frequency(cmos_model)
        fig.add_vline(x=f_cross, line_dash="dot", line_color="#888",
                      annotation_text=f"Crossover: {f_cross:.1e} Hz")
        cross_text = (
            f"⚡ Adiabatic beats CMOS below {f_cross:.1e} Hz "
            f"({f_cross/1e6:.0f} MHz) at {node} nm, {T} K."
        )
    except Exception:
        cross_text = "No crossover found in this range."

    fig.update_layout(
        title=f"Energy per Gate Switch — {node} nm at {T} K",
        xaxis_title="Frequency (Hz)",
        yaxis_title="Energy per Switch (J)",
        xaxis_type="log",
        yaxis_type="log",
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    detail = html.P(cross_text, style={"fontWeight": "bold", "color": "#1565c0"})
    return fig, detail


# ---- Technology Roadmap ----

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
                      annotation_text="Landauer limit (1×)")
        fig.update_layout(yaxis_title="Landauer Gap (×)")
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


# ---- SoC Thermal Map ----

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
    actions = [b["recommended_action"] for b in headroom]
    densities = [b["gate_density"] for b in headroom]
    density_hr = [b["density_headroom_factor"] for b in headroom]

    mat = get_material(mat_key)
    t_limit = mat.max_operating_temp

    # Color by status
    colors = []
    for h_k, bn in zip(headrooms, bottlenecks):
        if h_k < 10:
            colors.append("#e53935")   # critical
        elif h_k < 50:
            colors.append("#ff9800")   # warning
        elif bn:
            colors.append("#ffc107")   # bottleneck
        else:
            colors.append("#43a047")   # safe

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
        title=f"Per-Block Temperature — {mat.name}, "
              f"{COOLING_PRESETS[cooling_key][0]}, {freq_ghz} GHz",
        yaxis_title="Peak Temperature (K)",
        yaxis_range=[250, max(max(temps) * 1.08, t_limit + 50)],
        template="plotly_white",
        margin=dict(t=60, b=40),
    )

    # Detail table
    table_data = []
    for i, b in enumerate(headroom):
        table_data.append({
            "Block": b["name"],
            "Paradigm": b["paradigm"].upper(),
            "Density": f"{b['gate_density']:.1e}",
            "T_max (K)": f"{b['T_max_K']:.1f}",
            "Headroom (K)": f"{b['thermal_headroom_K']:.1f}",
            "Density Headroom": f"{b['density_headroom_factor']:.1f}×",
            "Bottleneck": "🔥 YES" if b["is_bottleneck"] else "",
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


# ---- Custom Material Registration ----

@callback(
    Output("cust-status", "children"),
    Output("cust-table", "children"),
    Input("cust-register", "n_clicks"),
    State("cust-key", "value"),
    State("cust-name", "value"),
    State("cust-k", "value"),
    State("cust-cp", "value"),
    State("cust-rho", "value"),
    State("cust-rho-e", "value"),
    State("cust-tmax", "value"),
    State("cust-gap", "value"),
    State("cust-notes", "value"),
    prevent_initial_call=True,
)
def register_custom_material(n_clicks, key, name, k, cp, rho, rho_e,
                              tmax, gap, notes):
    """Register a user-defined material at runtime."""
    if not key or not name:
        return (html.P("Please fill in at least the key and name.",
                        style={"color": "red"}), dash.no_update)

    # Check all numeric fields
    missing = []
    for label, val in [("k", k), ("c_p", cp), ("ρ", rho),
                        ("ρ_e", rho_e), ("T_max", tmax)]:
        if val is None:
            missing.append(label)
    if missing:
        return (html.P(f"Missing required numeric fields: {', '.join(missing)}",
                        style={"color": "red"}), dash.no_update)

    try:
        mat = Material(
            name=name,
            thermal_conductivity=float(k),
            specific_heat=float(cp),
            density=float(rho),
            electrical_resistivity=float(rho_e),
            max_operating_temp=float(tmax),
            bandgap_eV=float(gap or 0.0),
            notes=notes or "",
        )
        material_registry.register(key, mat)

        # Rebuild custom table
        custom_mats = material_registry.list_custom()
        rows = []
        for ck, cm in custom_mats.items():
            rows.append({
                "Key": ck,
                "Name": cm.name,
                "k (W/m·K)": f"{cm.thermal_conductivity:.1f}",
                "c_p (J/kg·K)": f"{cm.specific_heat:.0f}",
                "ρ (kg/m³)": f"{cm.density:.0f}",
                "E_gap (eV)": f"{cm.bandgap_eV:.2f}",
            })

        status = html.P(
            f"✅ Registered '{key}' — now available in all tabs!  "
            f"(α = {mat.thermal_diffusivity:.2e} m²/s)",
            style={"color": "#2e7d32", "fontWeight": "bold"},
        )
        return status, _render_custom_table(rows)

    except (ValueError, KeyError) as e:
        return (html.P(f"❌ {e}", style={"color": "red", "fontWeight": "bold"}),
                dash.no_update)


# ── Run ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("  Aethermor Explorer")
    print("  Open your browser to http://127.0.0.1:8050")
    print()
    app.run(debug=False, port=8050)
