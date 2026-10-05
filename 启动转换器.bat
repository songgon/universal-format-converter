@echo off
rem 万能格式转换器 - 双击启动
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo 未找到 Python 虚拟环境，请先运行 install.bat
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py
