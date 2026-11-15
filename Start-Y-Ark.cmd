@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
 echo Run Setup-Y-Ark.cmd first. See README.md for prerequisites.
 pause
 exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m creatorsave.app
