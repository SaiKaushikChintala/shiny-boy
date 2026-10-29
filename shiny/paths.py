import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
BUNDLE = Path(getattr(sys, "_MEIPASS", ROOT))
DATA_DIRECTORY = BUNDLE / "data"
ASSETS_DIRECTORY = BUNDLE / "assets"
ROMS_DIRECTORY = ROOT / "roms"
SAVES_DIRECTORY = ROOT / "saves"
STATES_DIRECTORY = ROOT / "states"
SCREENSHOTS_DIRECTORY = ROOT / "screenshots"
SETTINGS_PATH = ROOT / "settings.json"
