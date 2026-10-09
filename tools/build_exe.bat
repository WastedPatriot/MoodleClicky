@echo off
rem Optional: build a single MoodleClicky.exe with PyInstaller (output in dist\).
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe call run.bat
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name MoodleClicky --hidden-import pystray._win32 --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 --hidden-import keyring.backends.Windows moodleclicky\__main__.py
