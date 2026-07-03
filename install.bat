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

echo [1/6] pip upgrade...
python -m pip install --upgrade pip -q

echo [2/6] nvidia-ml-py (GPU monitoring)...
pip install nvidia-ml-py -q

echo [3/6] pystray (system tray)...
pip install pystray -q

echo [4/6] Pillow (tray icon)...
pip install Pillow -q

echo [5/6] numpy (stress test)...
pip install numpy -q

echo [6/7] wmi (hardware detection)...
pip install wmi -q

echo [7/7] psutil (per-game process monitoring)...
pip install psutil -q

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
