@echo off
rem 带控制台窗口的调试启动，用于排查问题
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py
pause
