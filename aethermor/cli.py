"""Aethermor command-line interface."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="aethermor",
        description="Aethermor — chip thermal analysis toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # aethermor dashboard
    dash_p = sub.add_parser("dashboard", help="Launch interactive explorer UI")
    dash_p.add_argument(
        "--port", type=int, default=8050, help="Port (default: 8050)"
    )
    dash_p.add_argument(
        "--debug", action="store_true", help="Enable Dash debug mode"
    )

    # aethermor validate
    sub.add_parser("validate", help="Run the full validation suite (133 checks)")

    # aethermor version
    sub.add_parser("version", help="Print version and exit")

    args = parser.parse_args()

    if args.command == "dashboard":
        _run_dashboard(args)
    elif args.command == "validate":
        _run_validate()
    elif args.command == "version":
        from aethermor import __version__
        print(f"aethermor {__version__}")
    else:
        parser.print_help()
        sys.exit(1)


def _run_dashboard(args):
    try:
        import dash  # noqa: F401
    except ImportError:
        print("Dashboard requires Dash and Plotly.")
        print("Install with:  pip install aethermor[dashboard]")
        sys.exit(1)

    from aethermor.app.main import run
    run(debug=args.debug, port=args.port)


def _run_validate():
    from aethermor.validation.validate_all import main as validate_main
    validate_main()


if __name__ == "__main__":
    main()
