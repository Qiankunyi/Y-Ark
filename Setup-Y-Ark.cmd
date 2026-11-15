@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 py -3 -m venv .venv
 if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
echo Y-Ark is ready. Open Start-Y-Ark.cmd.
echo FFmpeg, ffprobe and Deno must also be installed. See README.md.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.11 or newer and check your network.
pause
exit /b 1
