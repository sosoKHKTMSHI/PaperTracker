@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call install_windows.bat
call .venv\Scripts\activate.bat
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name AMRIGS_StudyOS --collect-all PySide6 run.py
if errorlevel 1 (
  echo Falha na geracao do executavel.
  pause
  exit /b 1
)
echo.
echo Executavel criado em dist\AMRIGS_StudyOS
pause
