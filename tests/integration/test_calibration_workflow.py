import os
import uuid
import pandas as pd
import digital_twin_reparameterization as cal

def test_calibration_workflow(monkeypatch):
    csv_path = f"log_calibration_{uuid.uuid4().hex}.csv"
    df = pd.DataFrame({
        'timestamp': pd.date_range('2023-01-01', periods=10, freq='S'),
        'ambient_cycle': 0.0, 'temperature_C': 20.0,
        'harvester_power_W': [1]*10, 'core_power_W': [0.5]*10,
        'interconnect_resistance_Ohm': 100.0, 'healed_event': False
    })
    df.to_csv(csv_path, index=False)
    monkeypatch.setattr(cal, 'HW_LOG', str(csv_path))
    cal._hw_df = pd.read_csv(str(csv_path), parse_dates=['timestamp'])
    cal._hw_df['net_power'] = cal._hw_df['harvester_power_W'] - cal._hw_df['core_power_W']
    cal.main()
    assert os.path.isfile('calibrated_params.json')
