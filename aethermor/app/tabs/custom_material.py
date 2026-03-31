"""Custom Material tab — layout and callback."""

import dash
from dash import dcc, html, Input, Output, State, callback, dash_table

from aethermor.physics.materials import (
    Material, registry as material_registry,
)


def layout():
    custom_mats = material_registry.list_custom()
    existing_rows = []
    for key, mat in custom_mats.items():
        existing_rows.append({
            "Key": key,
            "Name": mat.name,
            "k (W/m\u00b7K)": f"{mat.thermal_conductivity:.1f}",
            "c_p (J/kg\u00b7K)": f"{mat.specific_heat:.0f}",
            "\u03c1 (kg/m\u00b3)": f"{mat.density:.0f}",
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
            "in every tab\u2019s material dropdown \u2014 ranked alongside the built-ins.",
            style={"color": "#555", "marginBottom": "16px"},
        ),
        html.Div([
            html.Div([
                html.Label("Registry Key (lowercase, no spaces)", style=_label_style),
                dcc.Input(id="cust-key", type="text", placeholder="e.g. boron_nitride",
                          style=_input_style),
                html.Label("Display Name", style=_label_style),
                dcc.Input(id="cust-name", type="text",
                          placeholder="e.g. Hexagonal Boron Nitride (h-BN)",
                          style=_input_style),
                html.Label("Thermal Conductivity k (W/(m\u00b7K))", style=_label_style),
                dcc.Input(id="cust-k", type="number", placeholder="600.0",
                          style=_input_style),
                html.Label("Specific Heat c_p (J/(kg\u00b7K))", style=_label_style),
                dcc.Input(id="cust-cp", type="number", placeholder="800.0",
                          style=_input_style),
                html.Label("Density \u03c1 (kg/m\u00b3)", style=_label_style),
                dcc.Input(id="cust-rho", type="number", placeholder="2100.0",
                          style=_input_style),
                html.Label("Electrical Resistivity (\u03a9\u00b7m)", style=_label_style),
                dcc.Input(id="cust-rho-e", type="number", placeholder="1e15",
                          style=_input_style),
                html.Label("Max Operating Temperature (K)", style=_label_style),
                dcc.Input(id="cust-tmax", type="number", placeholder="1273.15",
                          style=_input_style),
                html.Label("Bandgap (eV) \u2014 0 for metals", style=_label_style),
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
    all_mats = material_registry.list_builtins()
    rows = []
    for key in sorted(all_mats.keys()):
        m = all_mats[key]
        rows.append({
            "Key": key,
            "k (W/m\u00b7K)": f"{m.thermal_conductivity:.0f}",
            "c_p": f"{m.specific_heat:.0f}",
            "\u03c1": f"{m.density:.0f}",
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
    if not key or not name:
        return (html.P("Please fill in at least the key and name.",
                        style={"color": "red"}), dash.no_update)

    missing = []
    for label, val in [("k", k), ("c_p", cp), ("\u03c1", rho),
                        ("\u03c1_e", rho_e), ("T_max", tmax)]:
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

        custom_mats = material_registry.list_custom()
        rows = []
        for ck, cm in custom_mats.items():
            rows.append({
                "Key": ck,
                "Name": cm.name,
                "k (W/m\u00b7K)": f"{cm.thermal_conductivity:.1f}",
                "c_p (J/kg\u00b7K)": f"{cm.specific_heat:.0f}",
                "\u03c1 (kg/m\u00b3)": f"{cm.density:.0f}",
                "E_gap (eV)": f"{cm.bandgap_eV:.2f}",
            })

        status = html.P(
            f"\u2705 Registered '{key}' \u2014 now available in all tabs!  "
            f"(\u03b1 = {mat.thermal_diffusivity:.2e} m\u00b2/s)",
            style={"color": "#2e7d32", "fontWeight": "bold"},
        )
        return status, _render_custom_table(rows)

    except (ValueError, KeyError) as e:
        return (html.P(f"\u274c {e}", style={"color": "red", "fontWeight": "bold"}),
                dash.no_update)
