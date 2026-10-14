@echo off
rem Build a single-file Windows exe: dist\FestivalReceipt.exe
rem Replace app.ico with your own icon if you like (same file name).
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller pywin32 keyring
if errorlevel 1 goto fail
pyinstaller --noconfirm --clean --onefile --noconsole --name FestivalReceipt --icon app.ico ^
  --add-data "menu.sample.csv;." --add-data "app.ico;." ^
  --hidden-import win32print --hidden-import keyring.backends.Windows ^
  receipt.py
if errorlevel 1 goto fail
echo.
echo Done: dist\FestivalReceipt.exe
echo Next (optional): open installer.iss in Inno Setup and press Compile.
pause
exit /b 0
:fail
echo.
echo Build FAILED. See messages above.
pause
exit /b 1
