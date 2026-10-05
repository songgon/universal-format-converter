"""主窗口外壳：无边框一体化标题栏 + 可折叠侧边栏 + 分类页面栈。

拖拽文件自动路由到对应分类页；支持明暗主题切换（记住选择）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
    QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from core import appdata, registry
from gui.convert_page import PAGE_ORDER, CATEGORY_META, ConvertPage
from gui.sidebar import Sidebar
from gui.theme import stylesheet

EDGE = 6  # 无边框窗口边缘热区（像素）


class TitleBar(QFrame):
    """无边框窗口的标题栏：拖动移动、双击最大化、最小化/最大化/关闭。"""

    minimizeClicked = Signal()
    maxClicked = Signal()
    closeClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 4, 6, 4)
        lay.setSpacing(4)
        logo = QLabel("🔄")
        logo.setStyleSheet("font-size: 13pt; background: transparent;")
        name = QLabel("万能格式转换器")
        name.setObjectName("TBTitle")
        lay.addWidget(logo)
        lay.addWidget(name)
        lay.addStretch(1)

        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setObjectName("TBButton")
        self.btn_theme.setToolTip("切换深色 / 浅色主题")
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("TBButton")
        self.btn_max = QPushButton("□")
        self.btn_max.setObjectName("TBButton")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("TBClose")
        for b in (self.btn_theme, self.btn_min, self.btn_max, self.btn_close):
            b.setCursor(self.cursor())
            lay.addWidget(b)
        self.btn_min.clicked.connect(self.minimizeClicked)
        self.btn_max.clicked.connect(self.maxClicked)
        self.btn_close.clicked.connect(self.closeClicked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.maxClicked.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("万能格式转换器")
        self.resize(1080, 740)
        self.setMinimumSize(920, 640)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        self._settings = QSettings("UniversalConverter", "FormatConverter")
        self._dark = self._settings.value("theme/dark", False, type=bool)
        self._resize_edge = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar = TitleBar()
        self.titlebar.minimizeClicked.connect(self.showMinimized)
        self.titlebar.maxClicked.connect(self._toggle_max)
        self.titlebar.closeClicked.connect(self.close)
        self.titlebar.btn_theme.clicked.connect(self._toggle_theme)
        outer.addWidget(self.titlebar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        outer.addWidget(body, 1)

        self.sidebar = Sidebar(
            [(CATEGORY_META[k][0], CATEGORY_META[k][1]) for k in PAGE_ORDER],
            footer_text=self._footer_text())
        self.sidebar.pageSelected.connect(self._on_nav)
        body_lay.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        body_lay.addWidget(self.stack, 1)

        self.pages: dict[str, ConvertPage] = {}
        cats_by_page = {
            "all": None,
            "images": {"images"},
            "documents": {"documents"},
            "data": {"data"},
            "media": {"media"},
        }
        for key in PAGE_ORDER:
            page = ConvertPage(key, allowed_cats=cats_by_page[key])
            self.pages[key] = page
            self.stack.addWidget(page)
        for page in self.pages.values():
            page.batchDone.connect(self._on_convert_done)
        self.sidebar.set_footer(self._footer_text())

        self.setStyleSheet(stylesheet(self._dark))
        self._apply_theme_button()
        self.installEventFilter(self)
        for w in self.findChildren(QWidget):
            w.setMouseTracking(True)

        # 窗口位置记忆
        geo = self._settings.value("win/geometry")
        if geo:
            self.restoreGeometry(geo)

        # 系统托盘 + 完成通知
        self._tray = None
        icon_file = appdata.icon_path()
        if icon_file:
            tray = QSystemTrayIcon(QIcon(str(icon_file)), self)
            menu = QMenu()
            act_show = menu.addAction("显示主窗口")
            act_show.triggered.connect(self._show_from_tray)
            menu.addSeparator()
            act_quit = menu.addAction("退出")
            act_quit.triggered.connect(self.close)
            tray.setContextMenu(menu)
            tray.setToolTip("万能格式转换器")
            tray.show()
            self._tray = tray

    # ------------------------------------------------------------ 托盘 / 统计

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_convert_done(self, ok: int, bad: int, summary: str):
        try:
            appdata.record_conversion(ok, bad, "")
        except Exception:
            pass
        self.sidebar.set_footer(self._footer_text())
        if self._tray and ok + bad > 0:
            icon = self._tray.icon()
            title = "转换完成" if bad == 0 else "转换结束（有失败项）"
            self._tray.showMessage(title, summary or f"成功 {ok}，失败 {bad}",
                                   icon, 3500)

    def closeEvent(self, event):
        self._settings.setValue("win/geometry", self.saveGeometry())
        super().closeEvent(event)

    # ------------------------------------------------------------ 主题

    def _toggle_theme(self):
        self._dark = not self._dark
        self._settings.setValue("theme/dark", self._dark)
        self.setStyleSheet(stylesheet(self._dark))
        self._apply_theme_button()

    def _apply_theme_button(self):
        self.titlebar.btn_theme.setText("☀️" if self._dark else "🌙")

    # ------------------------------------------------------------ 无边框缩放

    def eventFilter(self, obj, event):
        if obj is self and event.type() in (QEvent.Type.MouseButtonPress,
                                            QEvent.Type.MouseMove,
                                            QEvent.Type.MouseButtonRelease):
            if not self.isMaximized():
                edge = self._edge_at(event.position().toPoint())
                if event.type() == QEvent.Type.MouseMove and self._resize_edge:
                    return True
                if edge and event.type() == QEvent.Type.MouseButtonPress \
                        and event.buttons() & Qt.MouseButton.LeftButton:
                    self.windowHandle().startSystemResize(edge)
                    return True
                if event.type() == QEvent.Type.MouseMove:
                    self._update_cursor(edge)
            elif event.type() == QEvent.Type.MouseMove:
                self._update_cursor(None)
        return super().eventFilter(obj, event)

    def _edge_at(self, pos):
        r = self.rect()
        at_left = pos.x() <= EDGE
        at_right = pos.x() >= r.width() - EDGE
        at_top = pos.y() <= EDGE
        at_bottom = pos.y() >= r.height() - EDGE
        if at_top and at_left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if at_top and at_right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if at_bottom and at_left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if at_bottom and at_right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if at_left:
            return Qt.Edge.LeftEdge
        if at_right:
            return Qt.Edge.RightEdge
        if at_top:
            return Qt.Edge.TopEdge
        if at_bottom:
            return Qt.Edge.BottomEdge
        return None

    def _update_cursor(self, edge):
        cursors = {
            Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
            Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
            Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
            Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge: Qt.CursorShape.SizeFDiagCursor,
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge: Qt.CursorShape.SizeFDiagCursor,
            Qt.Edge.TopEdge | Qt.Edge.RightEdge: Qt.CursorShape.SizeBDiagCursor,
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge: Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ------------------------------------------------------------ 导航与路由

    def _on_nav(self, index: int):
        self.stack.setCurrentIndex(index)

    def page_for_category(self, cat: str | None) -> ConvertPage:
        if cat and cat in PAGE_ORDER:
            return self.pages[cat]
        return self.pages["all"]

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        self.route_paths(paths)

    def route_paths(self, paths: list[Path]):
        """把文件分派到匹配的分类页：本页能收就收，否则自动切到对应页面。"""
        by_page: dict[str, list[Path]] = {}
        for p in paths:
            if not p.is_file():
                continue
            cat = registry.detect_category(p)
            page_key = cat if (cat and cat in self.pages) else "all"
            by_page.setdefault(page_key, []).append(p)

        if not by_page:
            return
        current_key = PAGE_ORDER[self.stack.currentIndex()]
        if set(by_page) == {current_key}:
            self.pages[current_key].add_paths(by_page[current_key])
            return
        for key, plist in by_page.items():
            self.pages[key].add_paths(plist)
        focus = max(by_page, key=lambda k: len(by_page[k]))
        if focus != current_key:
            idx = PAGE_ORDER.index(focus)
            self.stack.setCurrentIndex(idx)
            self.sidebar._group.button(idx).setChecked(True)

    @staticmethod
    def _footer_text() -> str:
        from core import media
        from core.documents import libreoffice_path
        lo = " · LibreOffice 高保真" if libreoffice_path() else ""
        stats = appdata.summary_line()
        line2 = "并行转换 · v1.6" + (f" · {stats}" if stats else "")
        if media.is_available():
            ff = media.ffmpeg_path() or ""
            tag = "内置" if "tools" in ff else "系统"
            return f"引擎：ffmpeg{tag} ✓{lo}\n{line2}"
        return f"ffmpeg 未检测到 ✗（图片/文档/数据不受影响）{lo}\n{line2}"
