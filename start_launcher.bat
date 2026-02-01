@echo off
chcp 65001 >nul 2>&1
title AI Literature Screening - Launcher
cd /d "%~dp0"

REM ============================================
REM AI Literature Screening - Auto Deployment
REM ============================================

cls
echo.
echo    ============================================
echo    ^|                                          ^|
echo    ^|        AI Literature Screening v1.0.0    ^|
echo    ^|                                          ^|
echo    ^|   Smart Literature Screening Tool        ^|
echo    ^|                                          ^|
echo    ============================================
echo.

REM Set paths
set "PROJECT_DIR=%~dp0"
set "PYTHON_DIR=%PROJECT_DIR%python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "LIBS_DIR=%PROJECT_DIR%python_libs"
set "LAUNCHER_PY=%PROJECT_DIR%run_launcher.py"
set "LOG_FILE=%PROJECT_DIR%deploy.log"

REM Log start
echo [%date% %time%] Starting deployment >> "%LOG_FILE%"

REM Check run_launcher.py
if not exist "%LAUNCHER_PY%" (
    echo [ERROR] run_launcher.py not found!
    echo [%date% %time%] ERROR: run_launcher.py not found >> "%LOG_FILE%"
    pause
    exit /b 1
)

REM ============================================
REM Check project Python
REM ============================================
echo [INFO] Checking project environment...
echo [%date% %time%] Checking project Python... >> "%LOG_FILE%"

if exist "%PYTHON_EXE%" (
    echo [SUCCESS] Project Python found
    echo [%date% %time%] Project Python found >> "%LOG_FILE%"
    goto :START_LAUNCHER
) else (
    echo [ERROR] Project Python not found!
    echo [INFO] Please ensure the 'python' folder is included in the package.
    echo.
    pause
    exit /b 1
)

REM ============================================
REM Start launcher
REM ============================================
:START_LAUNCHER
echo.
echo [SUCCESS] Python environment ready!
echo [INFO] Starting launcher...
echo [%date% %time%] Starting launcher... >> "%LOG_FILE%"
echo.

REM Set PYTHONPATH to include project libraries
set "PYTHONPATH=%LIBS_DIR%\site-packages"

"%PYTHON_EXE%" "%LAUNCHER_PY%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Launcher failed with code %errorlevel%
    echo [INFO] Check deploy.log for details
    pause
)

exit /b 0
