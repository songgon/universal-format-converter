"""GUI 冒烟测试：离屏实例化新界面（侧边栏 + 分类页），验证路由与真实转换。

运行:  python tests/gui_smoke_test.py   （脚本自行设置离屏模式）
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)

    # 离屏测试时屏蔽模态弹窗（会阻塞无人值守的测试）
    QMessageBox.warning = staticmethod(lambda *a, **k: print("[msgbox]", a[1] if len(a) > 1 else ""))
    QMessageBox.information = staticmethod(lambda *a, **k: print("[msgbox]", a[1] if len(a) > 1 else ""))

    from gui.main_window import MainWindow

    win = MainWindow()
    win.show()

    tmp = Path(tempfile.mkdtemp(prefix="conv_gui_test_"))
    from PIL import Image
    img = tmp / "测试图片.png"
    Image.new("RGB", (120, 80), (30, 144, 255)).save(img)
    txt = tmp / "说明.txt"
    txt.write_text("界面冒烟测试\n\n第一段。\n\n第二段。", encoding="utf-8")
    csvf = tmp / "表格.csv"
    csvf.write_text("名称,数量\n甲,1\n乙,2", encoding="utf-8")

    ok = True

    # 1) 拖拽路由：混合文件应自动分类到各自页面
    win.route_paths([img, txt, csvf])
    counts = {k: win.pages[k].table.rowCount() for k in ("images", "documents", "data")}
    if counts != {"images": 1, "documents": 1, "data": 1}:
        print(f"✗ 拖拽路由结果异常: {counts}")
        ok = False
    else:
        print("✓ 拖拽自动路由：图片/文档/数据 各归各页")

    # 2) 分类页真实转换（走界面线程）
    cases = [("images", img, "pdf"), ("documents", txt, "docx"), ("data", csvf, "xlsx")]
    for key, src, target in cases:
        page = win.pages[key]
        page._clear_files()
        page.add_paths([src])
        assert page.table.rowCount() == 1
        idx = next((i for i in range(page.combo_target.count())
                    if page.combo_target.itemData(i) == target), None)
        if idx is None:
            print(f"✗ [{key}] 下拉框缺少目标 {target}")
            ok = False
            continue
        page.combo_target.setCurrentIndex(idx)
        out_dir = tmp / f"out_{key}"
        out_dir.mkdir(exist_ok=True)
        page.rb_custom_dir.setChecked(True)
        page.edit_dir.setCurrentText(str(out_dir))
        page.chk_overwrite.setChecked(True)
        page.start_convert()
        page._worker.wait(60000)
        app.processEvents()
        status = page.table.item(0, 2).text()
        if "完成" not in status:
            print(f"✗ [{key}] {src.name} → {target}: 状态={status}\n{page.log.toPlainText()[-400:]}")
            ok = False
        else:
            print(f"✓ [{key}] {src.name} → {target}")

    # 3) 侧边栏折叠（等动画播完）
    import time
    win.sidebar.toggle()
    deadline = time.time() + 1.5
    while time.time() < deadline and win.sidebar.width() > 120:
        app.processEvents()
        time.sleep(0.02)
    if win.sidebar.width() > 120:
        print(f"✗ 侧边栏折叠后宽度异常: {win.sidebar.width()}")
        ok = False
    else:
        print(f"✓ 侧边栏可折叠（宽度 {win.sidebar.width()}px）")
    win.sidebar.toggle()

    # 4) 错误类型文件被分类页拒绝
    page = win.pages["images"]
    page._clear_files()
    n = page.add_paths([txt])
    if n != 0:
        print("✗ 图片页接受了文本文件")
        ok = False
    else:
        print("✓ 分类过滤：图片页拒绝非图片文件")

    app.processEvents()
    # 清理测试期间写入的操作记忆，避免污染真实使用偏好
    from PySide6.QtCore import QSettings
    QSettings("UniversalConverter", "FormatConverter").clear()
    print("GUI 冒烟测试", "通过" if ok else "失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
