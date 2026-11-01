@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

py -3 --version >nul 2>nul
if %errorlevel%==0 (
    py -3 app.py
    goto :end
)

python --version >nul 2>nul
if %errorlevel%==0 (
    python app.py
    goto :end
)

echo Python не найден. Установите Python (3.9+) с сайта https://www.python.org/downloads/
pause

:end
