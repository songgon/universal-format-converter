@echo off
rem 集成右键菜单：选中文件后 右键 → 发送到 → 万能格式转换器
chcp 65001 >nul
cd /d "%~dp0"
set "PROJECT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT%tools\add_sendto.ps1" -Project "%PROJECT%"
if %errorlevel%==0 (
  echo.
  echo ✓ 集成成功！以后右键任意文件 → 发送到 → 万能格式转换器，即可直接转换。
) else (
  echo ✗ 集成失败
)
pause
