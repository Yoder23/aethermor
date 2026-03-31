"""Aethermor Interactive Explorer — main entry point.

Launch with:
    aethermor dashboard
    # or: python -m aethermor.app.main
"""

import dash
from dash import dcc, html, Input, Output, callback

# Import tab modules — this registers their callbacks with Dash
from aethermor.app.tabs import materials, cooling, paradigm, roadmap, soc, custom_material  # noqa: F401

app = dash.Dash(
    __name__,
    title="Aethermor Explorer",
    suppress_callback_exceptions=True,
)

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


@callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    if tab == "tab-material":
        return materials.layout()
    elif tab == "tab-cooling":
        return cooling.layout()
    elif tab == "tab-paradigm":
        return paradigm.layout()
    elif tab == "tab-roadmap":
        return roadmap.layout()
    elif tab == "tab-soc":
        return soc.layout()
    elif tab == "tab-custom":
        return custom_material.layout()
    return html.P("Select a tab.")


def run(debug=False, port=8050):
    """Launch the dashboard server."""
    print()
    print("  Aethermor Explorer")
    print(f"  Open your browser to http://127.0.0.1:{port}")
    print()
    app.run(debug=debug, port=port)


if __name__ == "__main__":
    run()
