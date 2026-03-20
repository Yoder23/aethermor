# tests/conftest.py

import os
import sys

# Add the project root (the directory containing aethermor_full_simulation_v2.py)
# to the front of sys.path so tests can import project modules.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
