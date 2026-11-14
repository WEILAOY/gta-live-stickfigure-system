@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)
where pythonw.exe >nul 2>nul
if errorlevel 1 (
    echo 未找到 Python。请安装包含 Tkinter 的 Python 3.11 或更高版本。
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0main.py"
