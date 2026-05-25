@echo off
:: GameOptimizerPro v2.0 — Launcher
:: Verwendet VBScript für komplett unsichtbaren Start (kein CMD, kein PowerShell Fenster)
cd /d "%~dp0"

:: Erstelle temporäres VBScript das Python unsichtbar als Admin startet
set VBSCRIPT=%TEMP%\gop_launch_%RANDOM%.vbs
echo Set oShell = CreateObject("Shell.Application") > "%VBSCRIPT%"
echo oShell.ShellExecute "python", Chr(34) ^& "%~dp0GameOptimizerPro.py" ^& Chr(34), "%~dp0", "runas", 0 >> "%VBSCRIPT%"
echo WScript.Sleep 500 >> "%VBSCRIPT%"

:: Starte VBScript (wscript = kein Fenster)
wscript //nologo "%VBSCRIPT%"
:: VBScript löscht sich nach kurzer Wartezeit selbst
ping -n 2 127.0.0.1 >nul
del "%VBSCRIPT%" 2>nul
