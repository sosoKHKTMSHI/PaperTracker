@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher nao encontrado. Instale Python 3.11 ou 3.12 e marque Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Falha na instalacao das dependencias.
  pause
  exit /b 1
)
echo.
echo Instalacao concluida. Execute run_windows.bat.
pause
