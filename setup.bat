@echo off
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install pywin32 keyring
echo.
echo Setup done. Now run run.bat
pause
