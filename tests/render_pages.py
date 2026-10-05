"""离屏渲染各页面截图（开发自查用）：python tests/render_pages.py"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.information = staticmethod(lambda *a, **k: None)

    from gui.main_window import MainWindow

    win = MainWindow()
    win.resize(1060, 720)
    win.show()
    app.processEvents()

    tmp = Path(tempfile.mkdtemp(prefix="conv_render_"))
    from PIL import Image
    img = tmp / "测试图片.png"
    Image.new("RGB", (120, 80), (30, 144, 255)).save(img)
    txt = tmp / "说明.txt"
    txt.write_text("界面冒烟测试\n\n第一段。\n\n第二段。", encoding="utf-8")
    csvf = tmp / "表格.csv"
    csvf.write_text("名称,数量\n甲,1\n乙,2", encoding="utf-8")
    win.route_paths([img, txt, csvf])
    app.processEvents()

    out_dir = Path(__file__).parent / "render"
    out_dir.mkdir(exist_ok=True)

    for i, key in enumerate(["all", "images", "documents", "data", "media"]):
        win.stack.setCurrentIndex(i)
        app.processEvents()
        pix = win.grab()
        pix.save(str(out_dir / f"page_{key}.png"))
        print("saved", key)

    # 折叠状态
    win.stack.setCurrentIndex(0)
    win.sidebar.toggle()
    import time
    deadline = time.time() + 1.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    win.grab().save(str(out_dir / "page_collapsed.png"))
    print("saved collapsed")

    # 深色主题
    win.sidebar.toggle()
    if not win._dark:
        win._toggle_theme()
    for i, key in enumerate(["all", "documents", "media"]):
        win.stack.setCurrentIndex(i)
        app.processEvents()
        win.grab().save(str(out_dir / f"dark_{key}.png"))
        print("saved dark", key)
    win._toggle_theme()
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
