"""微型启动器：双击 exe → 立即拉起内嵌 Python 运行时运行主程序。

独立打包为 万能格式转换器.exe（仅数 MB，不包含 PySide6，因此启动飞快）。
真正的应用本体在 runtime\\（内嵌 Python）+ main.py + core/gui + tools。
"""
from __future__ import annotations

import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def _find_pythonw(base: str) -> str | None:
    rt = os.path.join(base, "runtime")
    if not os.path.isdir(rt):
        return None
    for root, _dirs, files in os.walk(rt):
        if "pythonw.exe" in files:
            return os.path.join(root, "pythonw.exe")
    return None


def main() -> None:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)  # exe 所在目录
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    pyw = _find_pythonw(base)
    if not pyw:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "未找到内置运行时（runtime 文件夹）。\n请确保本 exe 与 runtime、main.py 在同一文件夹。",
            "万能格式转换器", 0x10)
        return

    main_py = os.path.join(base, "main.py")
    if not os.path.isfile(main_py):
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "缺少 main.py，程序文件不完整。", "万能格式转换器", 0x10)
        return

    subprocess.Popen([pyw, main_py] + sys.argv[1:],
                     cwd=base, creationflags=CREATE_NO_WINDOW, close_fds=True)


main()
