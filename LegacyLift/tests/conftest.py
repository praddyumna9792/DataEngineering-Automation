"""
Pytest configuration for LegacyLift.
Ensures LegacyLift root directory is in sys.path.
"""
import sys
from pathlib import Path

LEGACYLIFT_ROOT = Path(__file__).resolve().parent.parent
if str(LEGACYLIFT_ROOT) not in sys.path:
    sys.path.insert(0, str(LEGACYLIFT_ROOT))
