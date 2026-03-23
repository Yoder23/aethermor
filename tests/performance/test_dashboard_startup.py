import subprocess, time, sys, os
import pytest

def test_dashboard_startup():
    # Skip if dash is not installed
    dash = pytest.importorskip("dash", reason="dash not installed")
    requests = pytest.importorskip("requests", reason="requests not installed")

    dashboard_path = 'aethermor_dashboard.py'
    if not os.path.isfile(dashboard_path):
        pytest.skip("aethermor_dashboard.py not present (see archive/extra_tools/)")

    # Requires an existing aethermor_sim_v2.pkl; run the sim quickly to generate
    subprocess.run([sys.executable, '-m', 'simulation.aethermor_full_simulation_v2'], check=True)
    proc = subprocess.Popen([sys.executable, dashboard_path])
    try:
        time.sleep(5)
        r = requests.get('http://127.0.0.1:8050/')
        assert r.status_code == 200
    finally:
        proc.terminate()
