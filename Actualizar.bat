@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" actualizar.py
) else (
  py -3.14 actualizar.py
)
if errorlevel 1 echo La actualizacion no se ha completado.
pause
