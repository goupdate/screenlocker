@echo off
echo Installing pyinstaller...
pip install pyinstaller -q

echo Building screenlocker.exe...
pyinstaller --onefile --noconsole --name screenlocker screenlocker.py

echo.
echo Done: screenlocker.exe
echo Copy config.yaml next to it before running.
pause