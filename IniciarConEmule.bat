@echo off
setlocal
cd /d "%~dp0"
call "Iniciar.bat"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m noporforemule.launch_emule
if errorlevel 1 pause
