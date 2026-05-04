@echo off
:: Aquarium Science Monitor - Windows Setup Script
:: Run this as Administrator or in a regular terminal

echo ===================================
echo Aquarium Science Monitor Setup
echo ===================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found on PATH.
    echo.
    echo Please install Python 3.11+ first:
    echo   Option 1: https://www.python.org/downloads/
    echo   Option 2: winget install Python.Python.3.12
    echo   Option 3: Microsoft Store - search "Python 3.12"
    echo.
    echo After installing Python, re-run this script.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version

echo.
echo [*] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo [!] Installation failed. Check errors above.
    pause
    exit /b 1
)

echo.
echo [*] Setting up environment...
if not exist .env (
    copy .env.example .env
    echo [OK] Created .env from template. Please edit it and add your email.
) else (
    echo [OK] .env already exists.
)

echo.
echo ===================================
echo Setup complete!
echo ===================================
echo.
echo Next steps:
echo   1. Edit .env and set OPENALEX_EMAIL to your email address
echo   2. Run: streamlit run app.py
echo   3. Open: http://localhost:8501
echo.
pause
