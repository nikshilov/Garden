"""Global pytest configuration to ensure project modules are discoverable.
Adds the `backend` directory to `sys.path` so that `import garden_graph` works
regardless of the current working directory.
"""
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
