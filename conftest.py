"""Global pytest configuration to ensure project modules are discoverable.
Adds the `prototype` directory to `sys.path` so that `import garden_graph` works
regardless of the current working directory.
"""
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parent
PROTOTYPE_DIR = ROOT_DIR / "prototype"
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))
