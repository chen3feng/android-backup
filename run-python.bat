@echo off
setlocal enabledelayedexpansion

set PYTHON=which

call %~dp0check-env.bat
if errorlevel 1 (
    exit /b 1
)

echo PYTHON=%PYTHON%
REM === 1. Ensure virtualenv is installed ===
%PYTHON% -m virtualenv --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] virtualenv not found, installing...
    %PYTHON% -m pip install --upgrade pip
    %PYTHON% -m pip install virtualenv
)

REM === 2. Create .venv if missing ===
if not exist ".venv" (
    echo [INFO] Creating virtual environment in .venv ...
    %PYTHON% -m virtualenv .venv
)

REM === 3. Activate it ===
call .venv\Scripts\activate.bat

REM === 4. Install requirements ===
if exist requirements.txt (
    echo [INFO] Installing dependencies from requirements.txt ...
    pip install -r requirements.txt
)

REM === 5. Run target Python file (first argument) ===
if "%~1"=="" (
    echo Usage: %~nx0 your_script.py
    exit /b 1
)

echo [INFO] Running %~1 ...
python "%~1" %*

endlocal
