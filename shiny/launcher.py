import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REQUIRED = (3, 13)
INSTALLER_URL = "https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe"
ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("PIL", "cffi", "sounddevice")
CHECK = "import sys, tkinter; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MB_YESNO, MB_ICONQUESTION, MB_ICONERROR, IDYES = 0x4, 0x20, 0x10, 6


def tell(text: str, title: str = "Shiny Boy", question: bool = False) -> bool:
    if sys.platform == "win32":
        flags = (MB_YESNO | MB_ICONQUESTION) if question else MB_ICONERROR
        return ctypes.windll.user32.MessageBoxW(None, text, title, flags) == IDYES
    print(text)
    return False


def needs_relaunch() -> bool:
    if getattr(sys, "frozen", False):
        return False
    if sys.version_info[:2] != REQUIRED:
        return True
    from importlib.util import find_spec

    return any(find_spec(name) is None for name in PACKAGES)


def _works(executable: str) -> bool:
    try:
        return subprocess.run([executable, "-c", CHECK], capture_output=True, timeout=60, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def candidates() -> list[str]:
    found: list[str] = []
    if sys.platform == "win32":
        try:
            answer = subprocess.run(["py", "-3.13", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
            if answer.returncode == 0 and answer.stdout.strip():
                found.append(answer.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
        local = os.environ.get("LOCALAPPDATA", "")
        for folder in (
            Path(local) / "Python" / "pythoncore-3.13-64",
            Path(local) / "Programs" / "Python" / "Python313",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python313",
        ):
            found.append(str(folder / "python.exe"))
    for name in ("python3.13", "python"):
        path = shutil.which(name)
        if path:
            found.append(path)
    unique = []
    for path in found:
        if path not in unique and Path(path).is_file():
            unique.append(path)
    return unique


def find_python() -> str | None:
    return next((path for path in candidates() if _works(path)), None)


def install_python() -> bool:
    if sys.platform != "win32":
        return False
    target = Path(tempfile.gettempdir()) / "python-3.13-installer.exe"
    try:
        urllib.request.urlretrieve(INSTALLER_URL, target)
        done = subprocess.run(
            [str(target), "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0", "Include_tcltk=1", "Include_pip=1", "Include_test=0", "Include_doc=0"],
            timeout=1800,
        )
        return done.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        target.unlink(missing_ok=True)


def ensure_packages(executable: str) -> bool:
    probe = subprocess.run([executable, "-c", "import PIL, cffi, sounddevice"], capture_output=True, creationflags=NO_WINDOW)
    if probe.returncode == 0:
        return True
    install = subprocess.run([executable, "-m", "pip", "install", "--quiet", "-r", str(ROOT / "requirements.txt")], capture_output=True, creationflags=NO_WINDOW)
    return install.returncode == 0


def relaunch() -> int:
    found = find_python()
    if found is None:
        version = ".".join(map(str, sys.version_info[:2]))
        wanted = tell(
            f"Shiny Boy needs Python 3.13 (this is Python {version}, which its emulator part does not support)." + chr(10) * 2 +
            "Install Python 3.13 for you now? It is downloaded from python.org (about 28 MB), installs for your user only and "
            "does not change the Python you already have.",
            question=True,
        )
        if not wanted or not install_python():
            if wanted:
                tell("Python 3.13 could not be installed. Install it by hand from https://www.python.org/downloads/ and start Shiny Boy again.")
            return 1
        found = find_python()
        if found is None:
            tell("Python 3.13 was installed but could not be found. Start Shiny Boy again, or restart the computer first.")
            return 1
    if not ensure_packages(found):
        tell("The packages Shiny Boy needs could not be installed (is the computer online?). Run:\n\n    py -3.13 -m pip install -r requirements.txt")
        return 1
    if sys.executable.lower().endswith("pythonw.exe"):
        windowless = Path(found).with_name("pythonw.exe")
        found = str(windowless) if windowless.is_file() else found
    return subprocess.run([found, "-m", "shiny", *sys.argv[1:]], cwd=ROOT).returncode
