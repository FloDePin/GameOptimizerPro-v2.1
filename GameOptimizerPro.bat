@echo off
:: GameOptimizerPro v2.1 — Launcher
:: Findet den vollen Pfad zu pythonw.exe und startet die App komplett unsichtbar.
cd /d "%~dp0"

:: pythonw.exe finden. Erst PATH probieren, dann typische Speicherorte.
set "PYW="
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%i in ('where pythonw.exe') do (
        if not defined PYW set "PYW=%%i"
    )
)

:: Fallback: python.exe finden und pythonw daneben suchen
if not defined PYW (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        if not defined PYW (
            set "PYE=%%i"
            call set "PYDIR=%%PYE:python.exe=%%"
            if exist "!PYDIR!pythonw.exe" set "PYW=!PYDIR!pythonw.exe"
        )
    )
)

:: Letzter Fallback: Standardpfade fuer typische Python-Installationen
if not defined PYW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe"
    if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe"  set "PYW=%LOCALAPPDATA%\Python\pythoncore-3.14-64\pythonw.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
)

if not defined PYW (
    echo pythonw.exe nicht gefunden. Bitte Python neu installieren mit "Add to PATH".
    pause
    exit /b 1
)

:: VBScript mit vollem Pfad zu pythonw
set "VBSCRIPT=%TEMP%\gop_launch_%RANDOM%.vbs"
echo Set oShellApp = CreateObject("Shell.Application") > "%VBSCRIPT%"
echo oShellApp.ShellExecute "%PYW%", Chr(34) ^& "%~dp0GameOptimizerPro.py" ^& Chr(34), "%~dp0", "runas", 0 >> "%VBSCRIPT%"

wscript //nologo "%VBSCRIPT%"

ping -n 2 127.0.0.1 >nul
del "%VBSCRIPT%" 2>nul
