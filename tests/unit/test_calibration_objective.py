import numpy as np
import pandas as pd
from simulation import digital_twin_reparameterization as cal

def test_calibration_objective_synthetic(monkeypatch):
    hw_net = np.linspace(1,10,10)
    df_hw = pd.DataFrame({'net_power': hw_net})
    monkeypatch.setattr(cal, '_hw_df', df_hw)
    def fake_run_sim(params, sim_steps, cycle_length): return hw_net + np.random.normal(0,0.01,len(hw_net))
    monkeypatch.setattr(cal, 'run_sim', fake_run_sim)
    err = cal.objective(np.ones(7))
    assert np.isfinite(err)
