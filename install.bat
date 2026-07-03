@echo off
title GameOptimizerPro v2.1 - Installer
color 0B
echo.
echo  ==========================================
echo    GameOptimizerPro v2.1 - Installing Dependencies
echo  ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (echo [ERROR] Python not found & pause & exit /b 1)
for /f "tokens=*" %%i in ('python --version') do echo  Python: %%i
echo.

echo [1/2] pip upgrade...
python -m pip install --upgrade pip -q

echo [2/2] Installing dependencies from requirements.txt...
pip install -r "%~dp0requirements.txt" -q

echo.
echo  ==========================================
echo   Done! Optional CUDA stress test:
echo     pip install cupy-cuda12x
echo  ==========================================
echo.
echo  Before first run - Afterburner setup:
echo    Settings ^> General:
echo      [x] Unlock voltage control ^> Standard MSI
echo      [x] Unlock voltage monitoring
echo    Settings ^> Monitoring ^> GPU voltage: [x]
echo    Profile slot 2-5: unlock the padlock icon
echo.
echo  Start with: GameOptimizerPro.bat
echo.
pause
