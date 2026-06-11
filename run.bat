@echo off
rem NTE Auto Fishing - chay bot voi quyen Administrator
rem (phim gia lap can quyen admin moi toi duoc game HTGame.exe)
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% == 0 goto :run

echo Dang xin quyen Administrator...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:run
chcp 65001 >nul

rem --- tim python: PATH cua phien elevated co the thieu python cai theo user ---
if exist "C:\Users\Miu\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\Miu\AppData\Local\Programs\Python\Python311\python.exe" main.py
    goto :end
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py
    goto :end
)
where python >nul 2>&1
if %errorlevel% == 0 (
    python main.py
    goto :end
)
where py >nul 2>&1
if %errorlevel% == 0 (
    py -3 main.py
    goto :end
)
echo [LOI] Khong tim thay Python. Hay cai Python 3.11+ tu python.org
echo hoac sua duong dan python.exe trong file run.bat nay.

:end
echo.
pause
