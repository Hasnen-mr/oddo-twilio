@echo off
REM ==============================================================================
REM  MCP Claude Integration for Odoo - Windows Installer Launcher
REM  Double-clicking this file executes the PowerShell installer (install_windows.ps1)
REM ==============================================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
if %errorlevel% neq 0 (
    echo.
    echo Installation ended with errors.
)
echo.
pause
