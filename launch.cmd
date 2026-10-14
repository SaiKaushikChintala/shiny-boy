@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" goto run

echo First start: setting up. This takes a minute, once.
set PYTHON=
py -3.13 -c "import tkinter" >nul 2>&1 && set PYTHON=py -3.13
if not defined PYTHON (
    python -c "import sys, tkinter; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1 && set PYTHON=python
)
if not defined PYTHON (
    echo.
    echo Python 3.13 with Tk was not found. Install Python 3.13 from https://www.python.org/downloads/ and start again.
    pause
    exit /b 1
)
%PYTHON% -m venv .venv || goto failed
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto failed

:run
start "" "%~dp0.venv\Scripts\pythonw.exe" -m shiny %*
exit /b 0

:failed
echo.
echo Setting up did not work (see above).
rmdir /s /q .venv >nul 2>&1
pause
exit /b 1
