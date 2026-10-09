@echo off
rem MoodleClicky launcher: first run sets up a private Python environment, then starts the buddy.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
    echo Setting up MoodleClicky for the first time...
    py -3 -m venv .venv || python -m venv .venv || (echo Install Python 3.11+ from python.org first. & pause & exit /b 1)
    .venv\Scripts\python -m pip install --upgrade pip >nul
    .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
start "" .venv\Scripts\pythonw.exe -m moodleclicky
