import json
import os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scarcity_aethermor import ScarcityAethermorSim

HW_LOG = 'data/synthetic_hardware_log.csv'

# Lazy-loaded hardware log (loaded on first use, not on import)
_hw_df = None

def _get_hw_df():
    global _hw_df
    if _hw_df is None:
        _hw_df = pd.read_csv(HW_LOG, parse_dates=['timestamp'])
        _hw_df['net_power'] = _hw_df['harvester_power_W'] - _hw_df['core_power_W']
    return _hw_df

def run_sim(params, sim_steps, cycle_length):
    base_harvest, compute_cost, repro_cost, ambient_input, sleep_thresh, wake_thresh, decay = params
    sim = ScarcityAethermorSim(
        grid_size=30,
        steps=sim_steps,
        base_harvest=base_harvest,
        compute_cost=compute_cost,
        reproduction_cost_factor=repro_cost,
        base_ambient_input=ambient_input,
        decay_factor=decay,
        cycle_length=cycle_length,
        sleep_threshold=sleep_thresh,
        wake_threshold=wake_thresh
    )
    sim_df = sim.run(visualize=False)
    return sim_df['net'].values

def objective(x):
    hw_df = _get_hw_df()
    sim_net = run_sim(x, sim_steps=len(hw_df), cycle_length=24)
    hw_net = hw_df['net_power'].values
    n = min(len(sim_net), len(hw_net))
    return float(np.mean((sim_net[:n] - hw_net[:n])**2))

def main():
    init_params = np.array([1.0, 0.232, 0.271, 0.891, 1.60, 2.62, 0.015])
    bounds = [(0.5,1.5),(0.05,0.5),(0.1,1.0),(0.1,1.5),(0.5,5.0),(0.5,5.0),(0.001,0.1)]
    res = minimize(objective, init_params, bounds=bounds, method='L-BFGS-B', options={'maxiter':50})
    opt_params = res.x
    param_names = ['base_harvest','compute_cost','repro_cost','ambient_input','sleep_thresh','wake_thresh','decay_factor']
    opt_dict = dict(zip(param_names, opt_params.tolist()))
    out_path = os.getenv("AETHERMOR_CALIBRATED_OUT", "calibrated_params.json")
    try:
        with open(out_path, 'w') as f:
            json.dump(opt_dict, f, indent=2)
        print(f'Calibration complete. Saved to {out_path}')
    except PermissionError:
        if os.path.isfile(out_path):
            print(f'Calibration complete. Existing file retained: {out_path}')
        else:
            raise

if __name__ == '__main__':
    main()
