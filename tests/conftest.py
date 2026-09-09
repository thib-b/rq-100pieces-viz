import sys
from pathlib import Path

# Make `helpers` importable from test modules regardless of pytest's import mode,
# and the repo root importable so `from engine import ...` works.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
