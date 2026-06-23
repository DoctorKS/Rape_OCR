@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Python virtual environment not found: .venv\Scripts\pythonw.exe
    echo Create the environment and install app dependencies first.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m rape_ocr.main --data-entry-gui
