@echo off
setlocal enabledelayedexpansion
title Industrial Edge AI Quality Control ^& Modbus Gateway

echo ========================================================
echo  Industrial Edge AI Quality Control ^& Modbus Gateway
echo ========================================================
echo.

:: Navigate to script directory
cd /d "%~dp0"

:: Check if dependencies are already installed
python -c "import fastapi, uvicorn, numpy, PIL, cv2" 2>nul
if !errorlevel! equ 0 goto start_app

echo [INFO] First-time setup: Installing dependencies from requirements.txt...
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

:start_app
echo [INFO] Launching Industrial QC Gateway ^& HMI Web Server...
echo [INFO] Live SCADA Dashboard: http://localhost:8000
echo [INFO] Modbus TCP Server:    localhost:5020
echo.
echo [INFO] Starting browser...
start http://localhost:8000
echo.
python main.py

if !errorlevel! neq 0 (
    echo.
    echo [INFO] Application exited.
    pause
)
