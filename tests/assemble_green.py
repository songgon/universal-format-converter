"""组装绿色版（嵌入 Python 运行时方案，启动飞快）。"""
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(r"D:\智谱\格式转换器")
green = root / "绿色版"
runtime_name = "cpython-3.12.14-windows-x86_64-none"
rt_src = green / "runtime" / runtime_name

# 1) 先把已装好的运行时搬出来，避免重建时误删
staging = root / "runtime_staging"
if rt_src.exists():
    if staging.exists():
        shutil.rmtree(staging)
    shutil.move(str(rt_src), str(staging))
if green.exists():
    shutil.rmtree(green)
green.mkdir(parents=True)
rt_dst = green / "runtime"
rt_dst.mkdir()
shutil.move(str(staging), str(rt_dst / runtime_name))

# 2) 应用代码 + 引擎
for item in ("main.py", "convert_cli.py", "core", "gui", "assets"):
    src = root / item
    if src.is_dir():
        shutil.copytree(src, green / item,
                        ignore=shutil.ignore_patterns("__pycache__"))
    else:
        shutil.copy2(src, green / item)
(green / "tools").mkdir(exist_ok=True)
for d in ("ffmpeg", "pandoc"):
    shutil.copytree(root / "tools" / d, green / "tools" / d)

# 3) 启动器（双击即用）
(green / "启动转换器.bat").write_text(
    '@echo off\r\nstart "" "%~dp0runtime\\cpython-3.12.14-windows-x86_64-none\\pythonw.exe" '
    '"%~dp0main.py" %*\r\n', encoding="utf-8")

# 4) 双击 exe 外观：pythonw 副本 + 同目录 DLL + 路径文件
rt = rt_dst / runtime_name
shutil.copy2(rt / "pythonw.exe", green / "万能格式转换器.exe")
for dll in ("python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
    if (rt / dll).exists():
        shutil.copy2(rt / dll, green / dll)
(green / "python312._pth").write_text(
    "runtime\\Lib\n"
    "runtime\\Lib\\site-packages\n"
    ".\n"
    "import site\n", encoding="utf-8")

total = sum(f.stat().st_size for f in green.rglob("*") if f.is_file())
print(f"绿色版就绪: {green}  总大小 {total / 1048576:.0f} MB")
