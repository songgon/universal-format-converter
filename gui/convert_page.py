"""分类转换页面：每个类别（或“全部”）一张页，含拖拽区、文件列表、选项与日志。"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core import media, registry
from core.utils import ConvertError
from gui.theme import STATUS_COLORS, STATUS_TEXT
from gui.worker import ConvertWorker

CATEGORY_META: dict[str, tuple[str, str, str]] = {
    # key: (图标, 标题, 副标题)
    "all": ("🏠", "全部文件", "任意格式混合添加，自动识别类型并派发转换"),
    "images": ("🖼️", "图片转换", "PNG / JPG / WebP / GIF / TIFF / ICO / SVG / HEIC · 可合并为 PDF"),
    "documents": ("📄", "文档转换", "TXT / Markdown / HTML / Word / PDF / RTF 互通 · PDF 可转图片"),
    "data": ("📊", "数据转换", "CSV / Excel / JSON / YAML / XML / TOML · 可导出表格报告"),
    "media": ("🎵", "音视频转换", "MP3 / WAV / FLAC / M4A / MP4 / MKV / MOV / GIF · 基于 ffmpeg"),
}
PAGE_ORDER = ["all", "images", "documents", "data", "media"]


def make_card(parent_layout) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    parent_layout.addWidget(card)
    return card, lay


class DropZone(QFrame):
    """拖拽区域：也支持点击选择文件。"""

    filesDropped = Signal(list)

    _HOVER_STYLE = ("border: 2px solid #2f6bff; background: #eef4ff;"
                    "border-radius: 12px;")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(112)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(4)
        big = QLabel("📥  拖拽文件到这里")
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setStyleSheet("font-size:14pt; color:#2b6cb0; font-weight:600;")
        small = QLabel("或点击选择文件 · 支持批量")
        small.setAlignment(Qt.AlignmentFlag.AlignCenter)
        small.setStyleSheet("color:#7b8494; font-size:9.5pt;")
        lay.addWidget(big)
        lay.addWidget(small)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._HOVER_STYLE)  # 悬浮高亮反馈

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)

    def mousePressEvent(self, event):
        self._pick()

    def _pick(self):
        exts = " ".join(f"*.{e}" for e in sorted(registry.all_input_extensions()))
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要转换的文件", "", f"支持的文件 ({exts});;所有文件 (*.*)")
        if files:
            self.filesDropped.emit([Path(f) for f in files])


class ConvertPage(QWidget):
    """一个分类的完整转换页。allowed_cats=None 表示接收全部类别。"""

    wordDetected = Signal(bool)  # 后台线程检测微软 Word 安装结果
    loDetected = Signal(bool)    # 后台线程检测 LibreOffice 安装结果
    batchDone = Signal(int, int, str)  # 一批转换结束（成功数, 失败数, 汇总）

    def __init__(self, key: str, allowed_cats: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("PageRoot")
        self.key = key
        self.allowed_cats = allowed_cats
        self._files: list[Path] = []
        self._worker: ConvertWorker | None = None
        self._failed_rows: list[int] = []
        self.chk_word: QCheckBox | None = None
        self.chk_lo: QCheckBox | None = None
        self.chk_pdfmerge: QCheckBox | None = None
        self.combo_vcodec: QComboBox | None = None
        self._row_outputs: dict[int, str] = {}
        self._settings = QSettings("UniversalConverter", "FormatConverter")
        self.wordDetected.connect(self._on_word_detected)
        self.loDetected.connect(self._on_lo_detected)

        _icon, title, subtitle = CATEGORY_META[key]
        # 内容放在滚动容器里：窗口高度不足时可上下滚动，控件永不被压缩变形
        content = QWidget()
        content.setObjectName("PageRoot")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        head = QVBoxLayout()
        head.setSpacing(2)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("PageTitle")
        lbl_sub = QLabel(subtitle)
        lbl_sub.setObjectName("PageSub")
        head.addWidget(lbl_title)
        head.addWidget(lbl_sub)
        root.addLayout(head)

        # ffmpeg 未就绪时的提示横幅（仅音视频页可能出现）
        if key == "media" and not media.is_available():
            banner = QFrame()
            banner.setObjectName("Banner")
            bl = QHBoxLayout(banner)
            bl.setContentsMargins(14, 10, 14, 10)
            lbl = QLabel("⚠️ 未检测到 ffmpeg，音视频转换暂不可用。将 ffmpeg.exe 放入程序目录 "
                         "tools/ffmpeg/bin/ 或加入 PATH 后重启程序即可。")
            lbl.setWordWrap(True)
            bl.addWidget(lbl)
            root.addWidget(banner)

        # ---- 拖拽区 ----
        self.dropzone = DropZone()
        self.dropzone.filesDropped.connect(self.add_paths)
        root.addWidget(self.dropzone)

        # ---- 文件列表卡片 ----
        list_card, list_lay = make_card(root)
        bar = QHBoxLayout()
        lbl_card_title = QLabel("文件列表")
        lbl_card_title.setObjectName("CardTitle")
        bar.addWidget(lbl_card_title)
        bar.addStretch(1)
        self.lbl_count = QLabel("已添加 0 个文件")
        self.lbl_count.setObjectName("HintLabel")
        bar.addWidget(self.lbl_count)
        btn_up = QPushButton("↑")
        btn_up.setObjectName("IconBtn")
        btn_up.setToolTip("上移（影响合并 PDF 的页序）")
        btn_up.clicked.connect(lambda: self._move_selected(-1))
        btn_down = QPushButton("↓")
        btn_down.setObjectName("IconBtn")
        btn_down.setToolTip("下移（影响合并 PDF 的页序）")
        btn_down.clicked.connect(lambda: self._move_selected(1))
        bar.addWidget(btn_up)
        bar.addWidget(btn_down)
        btn_remove = QPushButton("移除选中")
        btn_remove.clicked.connect(self._remove_selected)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear_files)
        bar.addWidget(btn_remove)
        bar.addWidget(btn_clear)
        list_lay.addLayout(bar)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件", "类型", "状态"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(170)
        self.table.cellDoubleClicked.connect(self._open_row_output)
        list_lay.addWidget(self.table)

        # ---- 选项卡片 ----
        opt_card, opt_lay = make_card(root)
        lbl_opt = QLabel("转换设置")
        lbl_opt.setObjectName("CardTitle")
        opt_lay.addWidget(lbl_opt)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("转换为"), 0, 0)
        self.combo_target = QComboBox()
        self.combo_target.setMinimumWidth(170)
        grid.addWidget(self.combo_target, 0, 1, 1, 2)

        grid.addWidget(QLabel("输出品质"), 0, 3)
        self.combo_quality = QComboBox()
        for _key in ("max", "high", "normal"):
            _preset = registry.QUALITY_PRESETS[_key]
            self.combo_quality.addItem(_preset["label"], _key)
        self.combo_quality.setCurrentIndex(0)  # 默认最高品质
        self.combo_quality.setMinimumWidth(170)
        grid.addWidget(self.combo_quality, 0, 4, 1, 2)

        # 第二行：视频编码（音视频页）+ 覆盖同名 + 图片合并
        if key in ("media", "all"):
            grid.addWidget(QLabel("视频编码"), 1, 0)
            self.combo_vcodec = QComboBox()
            self.combo_vcodec.addItem("H.264（兼容最好）", "h264")
            self.combo_vcodec.addItem("H.265（体积更小约30%）", "h265")
            self.combo_vcodec.setCurrentIndex(
                int(self._settings.value(f"vcodec/{key}", 0)))
            self.combo_vcodec.currentIndexChanged.connect(
                lambda _: self._settings.setValue(f"vcodec/{key}", self.combo_vcodec.currentIndex()))
            grid.addWidget(self.combo_vcodec, 1, 1, 1, 2)
        else:
            self.combo_vcodec = None

        self.chk_overwrite = QCheckBox("覆盖同名文件")
        grid.addWidget(self.chk_overwrite, 1, 3, 1, 2)

        if key == "images":
            self.chk_merge = QCheckBox("合并为单个 PDF")
            grid.addWidget(self.chk_merge, 1, 5, 1, 2)
        else:
            self.chk_merge = None

        # 第三行：输出位置
        grid.addWidget(QLabel("保存到"), 2, 0)
        self.rb_same_dir = QRadioButton("原文件夹")
        self.rb_same_dir.setChecked(True)
        self.rb_custom_dir = QRadioButton("指定目录")
        grid.addWidget(self.rb_same_dir, 2, 1)
        grid.addWidget(self.rb_custom_dir, 2, 2)

        self.edit_dir = QComboBox()
        self.edit_dir.setEditable(True)
        self.edit_dir.setEnabled(False)
        self.edit_dir.setMinimumWidth(160)
        self.rb_same_dir.toggled.connect(lambda on: self.edit_dir.setEnabled(self.rb_custom_dir.isChecked()))
        grid.addWidget(self.edit_dir, 2, 3, 1, 2)
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._browse_dir)
        grid.addWidget(btn_browse, 2, 5)

        # 第四行：引擎与合并选项（预建后隐藏，检测到再显示，避免运行时改布局挤压列宽）
        row = 3
        if key == "documents":
            self.chk_pdfmerge = QCheckBox("多个 PDF 合并为一个（源全为 PDF 时生效）")
            grid.addWidget(self.chk_pdfmerge, row, 0, 1, 4)
        if key in ("documents", "all"):
            self.chk_word = QCheckBox("用微软 Word 转 PDF（版式最保真，速度较慢）")
            self.chk_word.setToolTip("调用本机微软 Word 导出 PDF，版式与 Word 完全一致。\n"
                                     "仅支持微软 Word；WPS 的兼容接口是收费功能，不会使用。")
            self.chk_word.setVisible(False)
            grid.addWidget(self.chk_word, row, 4 if key == "documents" else 0, 1, 4)
            self.chk_lo = QCheckBox("PDF 高保真引擎：LibreOffice（推荐，已检测到）")
            self.chk_lo.setChecked(True)
            self.chk_lo.setToolTip("Word/WPS/PPT 转 PDF 优先走 LibreOffice，"
                                   "排版保真且完全免费；关闭后改用内置轻量引擎。")
            self.chk_lo.setVisible(False)
            grid.addWidget(self.chk_lo, row + 1, 0, 1, 6)
        opt_lay.addLayout(grid)

        # ---- 操作行 ----
        action = QHBoxLayout()
        action.setSpacing(10)
        self.btn_convert = QPushButton("🚀  开始转换")
        self.btn_convert.setObjectName("ConvertBtn")
        self.btn_convert.setCursor(self.cursor())
        self.btn_convert.clicked.connect(self.start_convert)
        action.addWidget(self.btn_convert)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_convert)
        action.addWidget(self.btn_cancel)

        self.btn_open = QPushButton("📂 打开输出文件夹")
        self.btn_open.clicked.connect(self._open_out_dir)
        action.addWidget(self.btn_open)

        self.btn_retry = QPushButton("🔁 重试失败项")
        self.btn_retry.setVisible(False)
        self.btn_retry.clicked.connect(self._retry_failed)
        action.addWidget(self.btn_retry)
        action.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)  # 无任务时隐藏，避免显示误导性的 0/100
        action.addWidget(self.progress)
        self.lbl_elapsed = QLabel("")
        self.lbl_elapsed.setObjectName("Elapsed")
        action.addWidget(self.lbl_elapsed)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        opt_lay.addLayout(action)

        # ---- 日志 ----
        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("转换日志…")
        self.log.setMaximumHeight(120)
        root.addWidget(self.log)

        # 滚动容器包装（见 __init__ 开头注释）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._refresh_targets()

        # 操作记忆：恢复上次的输出目录 / 品质 / 目标格式（借鉴 FlyingMouse）
        saved_dir = self._settings.value(f"outdir/{key}", "")
        if saved_dir:
            self.edit_dir.setCurrentText(saved_dir)
        self.combo_quality.setCurrentIndex(int(self._settings.value(f"quality/{key}", 0)))
        self._saved_target = self._settings.value(f"target/{key}", "")
        if self._saved_target:
            idx = self.combo_target.findData(self._saved_target)
            if idx >= 0:
                self.combo_target.setCurrentIndex(idx)

        # 后台检测本机是否安装 Word / LibreOffice
        if key in ("documents", "all"):
            threading.Thread(target=self._detect_word, daemon=True).start()

    def _detect_word(self):
        from core.documents import libreoffice_path, word_available
        try:
            self.wordDetected.emit(word_available())
        except Exception:
            self.wordDetected.emit(False)
        try:
            self.loDetected.emit(libreoffice_path() is not None)
        except Exception:
            self.loDetected.emit(False)

    def _on_word_detected(self, has_word: bool):
        if has_word and self.chk_word is not None:
            self.chk_word.setVisible(True)

    def _on_lo_detected(self, has_lo: bool):
        if has_lo and self.chk_lo is not None:
            self.chk_lo.setVisible(True)

    # ------------------------------------------------ 文件管理

    def add_paths(self, paths: list[Path]) -> int:
        """添加文件/文件夹（自动过滤不属于本页类别的）；返回实际添加数。"""
        added = 0
        expanded: list[Path] = []
        for p in paths:
            if p.is_dir():
                # 文件夹递归导入受支持的文件
                for f in sorted(p.rglob("*")):
                    if f.is_file() and f.suffix.lower().lstrip(".") in registry.all_input_extensions():
                        expanded.append(f)
            else:
                expanded.append(p)
        for p in expanded:
            if not p.is_file():
                continue
            if p.suffix.lower() == ".zip":
                # ZIP 批处理：解出受支持的文件一起加入（借鉴 FlyingMouse）
                dest = p.parent / (p.stem + "_解压")
                try:
                    extracted = registry.extract_zip_for_conversion(p, dest)
                except Exception as e:
                    self.log.appendPlainText(f"✗ 无法读取压缩包 {p.name}：{e}")
                    continue
                if extracted:
                    added += self.add_paths(extracted)
                    self.log.appendPlainText(f"已从 {p.name} 解出 {len(extracted)} 个可转换文件。")
                else:
                    self.log.appendPlainText(f"— {p.name} 中没有受支持的文件")
                continue
            if p in self._files:
                continue
            cat = registry.detect_category(p)
            if self.allowed_cats is not None and cat not in self.allowed_cats:
                self.log.appendPlainText(f"— 已忽略 {p.name}（不属于本分类）")
                continue
            self._files.append(p)
            added += 1
        if added:
            self._refresh_table()
            self._refresh_targets()
            self.log.appendPlainText(f"已添加 {added} 个文件。")
        return added

    def _move_selected(self, delta: int):
        """上移/下移选中文件（调整合并 PDF 的页序）。"""
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            return
        n = len(self._files)
        if (delta < 0 and rows[0] == 0) or (delta > 0 and rows[-1] == n - 1):
            return
        files = self._files[:]
        for r in (rows if delta < 0 else reversed(rows)):
            files[r], files[r + delta] = files[r + delta], files[r]
        self._files = files
        self._refresh_table()
        self.table.clearSelection()
        for r in rows:
            self.table.selectRow(r + delta)

    def _remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            del self._files[r]
        self._refresh_table()
        self._refresh_targets()

    def _clear_files(self):
        self._files.clear()
        self._refresh_table()
        self._refresh_targets()

    def _refresh_table(self):
        self.table.setRowCount(len(self._files))
        for i, p in enumerate(self._files):
            item_file = QTableWidgetItem(p.name)
            item_file.setData(Qt.ItemDataRole.ToolTipRole, str(p))
            cat = registry.category_of_supported(p)
            if cat:
                cat_label = registry.CATEGORY_LABELS.get(cat, cat)
            elif registry.detect_category(p) == "media":
                cat_label = "音视频（缺 ffmpeg）"
            else:
                cat_label = "未知类型"
            self.table.setItem(i, 0, item_file)
            self.table.setItem(i, 1, QTableWidgetItem(cat_label))
            self.table.setItem(i, 2, QTableWidgetItem(STATUS_TEXT["wait"]))
        self.lbl_count.setText(f"已添加 {len(self._files)} 个文件")

    def _refresh_targets(self):
        cats = set()
        for p in self._files:
            cat = registry.category_of_supported(p)
            if cat:
                cats.add(cat)
        if self.allowed_cats is not None:
            cats &= set(self.allowed_cats)
        self.combo_target.clear()
        if not cats:
            self.combo_target.addItem("（请先添加文件）", "")
            return
        for ext, label in registry.targets_for_categories(cats):
            self.combo_target.addItem(label, ext)
        # 套用记忆的目标格式（添加文件刷新列表后仍保持）
        saved = getattr(self, "_saved_target", "")
        if saved:
            idx = self.combo_target.findData(saved)
            if idx >= 0:
                self.combo_target.setCurrentIndex(idx)

    # ------------------------------------------------ 转换

    def start_convert(self, rows: list[tuple[int, Path]] | None = None):
        if not self._files:
            QMessageBox.information(self, "提示", "请先添加要转换的文件。")
            return
        target = self.combo_target.currentData()
        if not target:
            QMessageBox.information(self, "提示", "请选择目标格式。")
            return
        if self._worker and self._worker.isRunning():
            return

        out_dir = None
        if self.rb_custom_dir.isChecked():
            out_dir = Path(self.edit_dir.currentText().strip() or ".")
        preset = registry.QUALITY_PRESETS[self.combo_quality.currentData() or "max"]
        options = {
            "quality": preset["quality"],
            "dpi": preset["dpi"],
            "media_level": preset["media_level"],
            "overwrite": self.chk_overwrite.isChecked(),
            "use_word": bool(self.chk_word and self.chk_word.isChecked()),
            "use_lo": bool(self.chk_lo and self.chk_lo.isChecked()),
            "vcodec": (self.combo_vcodec.currentData() if self.combo_vcodec else "h264"),
        }

        # PDF 加密/解密需要密码（借鉴 FlyingMouse 的 PDF 工具）
        if target in ("encrypt", "decrypt"):
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(
                self, "PDF 加密" if target == "encrypt" else "PDF 解密",
                "请输入要设置的打开密码：" if target == "encrypt" else "请输入现有密码（无则留空）：",
                QLineEdit.Password)
            if not ok:
                return
            options["pdf_password"] = text

        rows_spec = rows if rows is not None else [(i, p) for i, p in enumerate(self._files)]
        if not rows_spec:
            return
        merge, merge_kind = False, "images"
        if self.chk_merge and self.chk_merge.isChecked() and target == "pdf":
            merge, merge_kind = True, "images"
        if (self.chk_pdfmerge and self.chk_pdfmerge.isChecked() and target == "pdf"
                and all(p.suffix.lower() == ".pdf" for _, p in rows_spec)):
            merge, merge_kind = True, "pdfs"

        # 操作记忆：保存本次选择
        self._settings.setValue(f"outdir/{self.key}",
                                self.edit_dir.currentText().strip())
        self._settings.setValue(f"quality/{self.key}",
                                self.combo_quality.currentIndex())
        self._settings.setValue(f"target/{self.key}", target)
        self._saved_target = target

        self._failed_rows.clear()
        self.btn_retry.setVisible(False)
        self._set_busy(True)
        for i, _ in rows_spec:
            self._set_status(i, "wait", "")
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.progress.setMaximum(1 if merge else len(rows_spec))
        self._convert_t0 = time.time()
        self.lbl_elapsed.setText("已耗时 0 秒")
        self._elapsed_timer.start(1000)
        self.log.appendPlainText(f"—— 开始转换 {len(rows_spec)} 个文件 → {target.upper()} ——")

        self._worker = ConvertWorker(rows_spec, target, out_dir, options, merge_pdf=merge,
                                     merge_kind=merge_kind)
        self._worker.row_started.connect(self._on_row_started)
        self._worker.row_done.connect(self._on_row_done)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _retry_failed(self):
        rows = [(i, self._files[i]) for i in dict.fromkeys(self._failed_rows)
                if i < len(self._files)]
        self._failed_rows.clear()
        if rows:
            self.start_convert(rows)

    def cancel_convert(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log.appendPlainText("…已请求取消（当前文件可能仍会完成）")

    def _set_busy(self, busy: bool):
        self.btn_convert.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self.btn_retry.setVisible(self.btn_retry.isVisible() and not busy)
        self.table.setEnabled(not busy)
        self.combo_target.setEnabled(not busy)
        self.combo_quality.setEnabled(not busy)
        self.dropzone.setEnabled(not busy)
        if self.chk_word is not None:
            self.chk_word.setEnabled(not busy)
        if self.chk_lo is not None:
            self.chk_lo.setEnabled(not busy)

    def _set_status(self, row: int, key: str, message: str):
        item = QTableWidgetItem(STATUS_TEXT.get(key, key))
        color = STATUS_COLORS.get(key)
        if color:
            item.setForeground(QColor(color))
        if key in ("fail", "skip") and message:
            item.setData(Qt.ItemDataRole.ToolTipRole, message)
        self.table.setItem(row, 2, item)

    def _open_row_output(self, row: int, _col: int = 0):
        """双击已完成的行，直接打开转换结果。"""
        out = self._row_outputs.get(row)
        if out and Path(out).exists():
            try:
                os.startfile(out)  # noqa: S606
            except OSError as e:
                QMessageBox.warning(self, "无法打开", str(e))

    def _on_row_started(self, row: int):
        self._set_status(row, "run", "")

    def _on_row_done(self, row: int, status: str, message: str, outputs: list):
        self._set_status(row, status, message)
        if status == "ok" and outputs:
            self._row_outputs[row] = outputs[0]
        elif status == "ok":
            self._row_outputs.pop(row, None)
        if status in ("fail", "skip"):
            self._failed_rows.append(row)
        name = self._files[row].name if row < len(self._files) else "?"
        if status == "ok":
            self.log.appendPlainText(f"✓ {name} → {message}")
        elif status == "fail":
            self.log.appendPlainText(f"✗ {name}：{message}")
        else:
            self.log.appendPlainText(f"— {name}：{message}")

    def _tick_elapsed(self):
        secs = int(time.time() - self._convert_t0)
        self.lbl_elapsed.setText(f"已耗时 {secs // 60}分{secs % 60:02d}秒" if secs >= 60
                                 else f"已耗时 {secs} 秒")

    def _on_all_done(self, ok: int, bad: int, summary: str):
        self._set_busy(False)
        self._elapsed_timer.stop()
        secs = int(time.time() - self._convert_t0)
        self.lbl_elapsed.setText(f"总耗时 {secs // 60}分{secs % 60:02d}秒" if secs >= 60
                                 else f"总耗时 {secs} 秒")
        self.progress.setValue(self.progress.maximum())
        self.log.appendPlainText(f"—— 转换结束：{summary} ——")
        if summary:
            self.log.appendPlainText(summary)
        if bad > 0:
            self.btn_retry.setVisible(True)
            QMessageBox.warning(self, "部分转换失败",
                                f"成功 {ok} 个，失败/跳过 {bad} 个。\n"
                                f"可点击「重试失败项」仅重试失败的文件，详情见底部日志。")
        elif ok > 0:
            self.btn_retry.setVisible(False)
            self.log.appendPlainText("✓ 全部转换成功。输出文件已保存到目标文件夹。")
        self.batchDone.emit(ok, bad, summary)

    # ------------------------------------------------ 其他

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if d:
            self.edit_dir.setCurrentText(d)
            self.rb_custom_dir.setChecked(True)

    def _open_out_dir(self):
        if self.rb_custom_dir.isChecked() and self.edit_dir.currentText().strip():
            target_dir = self.edit_dir.currentText().strip()
        elif self._files:
            target_dir = str(self._files[0].parent)
        else:
            target_dir = str(Path.home())
        try:
            os.startfile(target_dir)  # noqa: S606
        except OSError as e:
            QMessageBox.warning(self, "无法打开", str(e))
