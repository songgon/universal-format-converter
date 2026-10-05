@echo off
rem 重新安装依赖（换电脑或环境损坏时使用）
cd /d "%~dp0"
where uv >nul 2>nul
if %errorlevel%==0 (
  uv venv .venv
  uv pip install --python .venv\Scripts\python.exe -r requirements.txt
) else (
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo.
echo 依赖安装完成，双击“启动转换器.bat”即可使用。
pause
