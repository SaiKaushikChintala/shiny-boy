import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if sys.version_info[:2] != (3, 13):
        raise SystemExit("Run this with Python 3.13: the emulator part of Shiny Boy is built for it.")
    separator = ";"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "ShinyBoy",
        "--icon", str(ROOT / "assets" / "logo.ico"),
        "--paths", str(ROOT),
        "--add-data", f"{ROOT / 'data'}{separator}data",
        "--add-data", f"{ROOT / 'assets'}{separator}assets",
        "--collect-submodules", "shiny",
        "--collect-submodules", "mgba",
        "--collect-all", "sounddevice",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "shiny" / "__main__.py"),
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    (ROOT / "dist" / "ShinyBoy" / "roms").mkdir(exist_ok=True)
    print("built:", ROOT / "dist" / "ShinyBoy" / "ShinyBoy.exe")


if __name__ == "__main__":
    main()
