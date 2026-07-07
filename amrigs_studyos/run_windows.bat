@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Ambiente virtual nao encontrado. Executando instalacao...
  call install_windows.bat
)
start "AMRIGS StudyOS" .venv\Scripts\pythonw.exe run.py
