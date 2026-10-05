"""万能格式转换器 - 程序入口。

支持启动参数：python main.py 文件1 [文件2 | 文件夹 ...]
（右键“发送到 → 格式转换器”即以此方式传入文件）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def collect_paths(args: list[str]) -> list[Path]:
    """把命令行参数展开为文件列表（文件夹递归收集受支持的文件）。"""
    from core import registry

    out: list[Path] = []
    seen: set[Path] = set()
    for a in args:
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower().lstrip(".") in registry.all_input_extensions():
                    rp = f.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        out.append(rp)
        elif p.is_file():
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(rp)
    return out


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    from core import appdata
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("万能格式转换器")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    icon_file = appdata.icon_path()
    if icon_file:
        app.setWindowIcon(QIcon(str(icon_file)))

    # 启动画面：瞬间出现，掩盖模块加载时间
    splash = None
    if icon_file:
        pm = QIcon(str(icon_file)).pixmap(132, 132)
        splash = QSplashScreen(pm)
        splash.showMessage("正在启动…", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        splash.show()
        app.processEvents()

    win = MainWindow()
    win.show()
    if splash:
        splash.finish(win)

    # 命令行传入的文件/文件夹（含“发送到”右键菜单）
    paths = collect_paths(sys.argv[1:])
    if paths:
        win.route_paths(paths)

    # 单实例：再次启动时把参数转发给已运行的实例并唤醒它
    from gui.single_instance import SingleInstance
    SingleInstance(app, win, collect_paths).listen(sys.argv)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
