@echo off
REM ===========================================================================
REM OpenCode Go proxy - debug launcher (shows live output, stays open).
REM Portable: resolves everything relative to this script's own folder.
REM ===========================================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title OpenCode Go Proxy (debug)

set "PY="
if exist "%~dp0python.txt" (
    set /p PY=<"%~dp0python.txt"
)

if not defined PY set "PY=py"
where %PY% >nul 2>nul
if errorlevel 1 set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    if /i "%PY%"=="python" (
        echo [!] No Python found on PATH and python.txt is missing.
        echo     Run install.ps1 first, or install Python 3.9+ and retry.
        echo.
        pause
        exit /b 1
    )
)

echo Using Python: %PY%
echo Proxy dir    : %~dp0
echo Log file     : %~dp0proxy.log
echo.
echo Press Ctrl+C to stop.
echo.

"%PY%" "%~dp0proxy.py"
echo.
echo [proxy exited]
pause
