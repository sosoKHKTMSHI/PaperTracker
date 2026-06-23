@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -m pip install -r requirements.txt
    start "" pyw RastreadorArtigos.pyw
) else (
    python -m pip install -r requirements.txt
    start "" pythonw RastreadorArtigos.pyw
)
