@echo off
setlocal
cd /d "%~dp0"
title Jade's AI Humanizer

rem -------------------------------------------------------------
rem Jade's AI Humanizer - Portable Launcher for Windows
rem -------------------------------------------------------------

rem If arguments are passed (e.g. humanize "text" or --help), run directly
if not "%~1"=="" (
    if exist "dist\humanizer.exe" (
        "dist\humanizer.exe" %*
        exit /b %ERRORLEVEL%
    )
    if exist ".venv\Scripts\python.exe" (
        ".venv\Scripts\python.exe" -m humanizer.cli %*
        exit /b %ERRORLEVEL%
    )
    python -m humanizer.cli %*
    exit /b %ERRORLEVEL%
)

rem If launched with no arguments, start local web GUI daemon
if exist "dist\humanizer.exe" (
    "dist\humanizer.exe"
    if %ERRORLEVEL% neq 0 pause
    exit /b %ERRORLEVEL%
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m humanizer.cli
    if %ERRORLEVEL% neq 0 pause
    exit /b %ERRORLEVEL%
)

python -m humanizer.cli
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Could not start Jade's AI Humanizer.
    echo Neither 'dist\humanizer.exe' nor Python virtual environment was found.
    echo Please run 'python packaging\build_exe.py' or create a virtual environment.
    echo.
    pause
)
