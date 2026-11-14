@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
rem CPU and DirectML wheels share the same import package; avoid mixed files.
".venv\Scripts\python.exe" -m pip uninstall -y onnxruntime onnxruntime-directml
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo 检测依赖已安装，可关闭本窗口并启动软件。
pause
exit /b 0
:failed
echo 安装失败，请检查 Python、网络及上方错误信息。
pause
exit /b 1
