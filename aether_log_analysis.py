import os
import sys

import matplotlib.pyplot as plt
import pandas as pd


def _safe_savefig(path):
    """
    Save figures while tolerating locked output files.
    """
    try:
        plt.savefig(path)
        return path
    except PermissionError:
        stem, ext = os.path.splitext(path)
        fallback = f"{stem}_new{ext}"
        try:
            plt.savefig(fallback)
            return fallback
        except OSError:
            return None


def analyze_log(log_file="data/synthetic_hardware_log.csv"):
    df = pd.read_csv(log_file, parse_dates=["timestamp"])
    df["net_power"] = df["harvester_power_W"] - df["core_power_W"]
    df["elapsed_s"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

    plt.figure(figsize=(10, 4))
    plt.plot(df["elapsed_s"], df["harvester_power_W"], label="Harvested Power (W)")
    plt.plot(df["elapsed_s"], df["core_power_W"], label="Core Power (W)")
    plt.plot(df["elapsed_s"], df["net_power"], label="Net Power (W)")
    plt.xlabel("Elapsed (s)")
    plt.ylabel("Power (W)")
    plt.title("Energy Flow Over Time")
    plt.legend()
    plt.tight_layout()
    energy_out = _safe_savefig("energy_flow.png")
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(df["elapsed_s"], df["interconnect_resistance_Ohm"], label="Resistance (Ohm)")
    healed = df[df["healed_event"] == True]
    if not healed.empty:
        plt.scatter(
            healed["elapsed_s"],
            healed["interconnect_resistance_Ohm"],
            label="Healing Event",
            s=20,
        )
    plt.xlabel("Elapsed (s)")
    plt.ylabel("Resistance (Ohm)")
    plt.title("Interconnect Health and Healing Events")
    plt.legend()
    plt.tight_layout()
    healing_out = _safe_savefig("healing_events.png")
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(df["elapsed_s"], df["ambient_cycle"], label="Ambient Cycle")
    plt.plot(df["elapsed_s"], df["temperature_C"], label="Temperature (C)")
    plt.xlabel("Elapsed (s)")
    plt.ylabel("Value")
    plt.title("Ambient Conditions")
    plt.legend()
    plt.tight_layout()
    ambient_out = _safe_savefig("ambient_conditions.png")
    plt.close()

    print(
        "Analysis complete. Generated files:",
        energy_out or "energy_flow.png (locked)",
        healing_out or "healing_events.png (locked)",
        ambient_out or "ambient_conditions.png (locked)",
    )


if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_hardware_log.csv"
    analyze_log(log_file)
