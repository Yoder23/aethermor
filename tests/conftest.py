# tests/conftest.py

import os
import sys

# Add the project root so tests can import project packages
# (physics/, analysis/, simulation/, validation/, etc.).
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
