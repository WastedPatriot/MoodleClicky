@echo off
rem Build MoodleClicky.exe (dist\MoodleClicky\) and run its self-test. Needs Python 3.11+ on PATH.
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_windows.ps1
pause
