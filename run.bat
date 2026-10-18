@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Nạp biến môi trường từ file .env (nếu có, ví dụ GEMINI_API_KEY=...)
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

REM Ưu tiên dùng Python trong .venv nếu có, ngược lại dùng Python hệ thống
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting AI Subtitle Studio...
"%PYTHON_EXE%" main.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] App exited with error code %ERRORLEVEL%.
    pause
)
