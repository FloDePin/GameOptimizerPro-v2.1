@echo off
:: GameOptimizerPro v2.1 — Launcher
:: Startet die App komplett unsichtbar (kein CMD, kein Konsolenfenster) mit Admin-Rechten.
:: Nutzt pythonw.exe (fensterlose Python-Variante) statt python.exe.
cd /d "%~dp0"

:: Temporaeres VBScript erstellen
set "VBSCRIPT=%TEMP%\gop_launch_%RANDOM%.vbs"

:: pythonw bevorzugen (kein Konsolenfenster). Faellt auf python zurueck falls nicht gefunden.
echo Set oShell = CreateObject("WScript.Shell") > "%VBSCRIPT%"
echo Set oFS = CreateObject("Scripting.FileSystemObject") >> "%VBSCRIPT%"
echo pyExe = "pythonw.exe" >> "%VBSCRIPT%"
echo Set oShellApp = CreateObject("Shell.Application") >> "%VBSCRIPT%"
echo oShellApp.ShellExecute pyExe, Chr(34) ^& "%~dp0GameOptimizerPro.py" ^& Chr(34), "%~dp0", "runas", 0 >> "%VBSCRIPT%"
echo WScript.Sleep 500 >> "%VBSCRIPT%"

:: VBScript ueber wscript starten (erzeugt selbst kein Fenster)
wscript //nologo "%VBSCRIPT%"

:: VBScript nach kurzer Wartezeit aufraeumen
ping -n 2 127.0.0.1 >nul
del "%VBSCRIPT%" 2>nul
