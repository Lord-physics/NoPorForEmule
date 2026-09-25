@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  py -3.14 -m venv .venv
  if errorlevel 1 (
    echo Se necesita Python 3.14 para instalar este programa.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import nudenet, cv2" >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo No se pudieron instalar las dependencias. Comprueba la conexion y vuelve a intentarlo.
    pause
    exit /b 1
  )
)
start "" ".venv\Scripts\pythonw.exe" -m noporforemule.app
