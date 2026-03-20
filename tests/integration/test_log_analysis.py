import os
import uuid
import pandas as pd
import numpy as np
import subprocess
import sys

def test_log_analysis_script():
    csv_path = f"log_analysis_{uuid.uuid4().hex}.csv"
    df = pd.DataFrame({
        'timestamp': pd.date_range('2023-01-01', periods=10, freq='S'),
        'ambient_cycle': np.linspace(0,1,10),
        'temperature_C': np.linspace(20,25,10),
        'harvester_power_W': np.ones(10),
        'core_power_W': np.zeros(10),
        'interconnect_resistance_Ohm': np.linspace(100,50,10),
        'healed_event': [False]*9+[True]
    })
    df.to_csv(csv_path, index=False)
    subprocess.run([sys.executable,'aether_log_analysis.py',str(csv_path)], check=True)
    assert os.path.isfile('energy_flow.png')
    assert os.path.isfile('healing_events.png')
    assert os.path.isfile('ambient_conditions.png')
