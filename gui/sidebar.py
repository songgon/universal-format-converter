"""左侧导航栏：可折叠（汉堡按钮 + 宽度动画），图标+文字，选中高亮。"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

EXPANDED_W = 210
COLLAPSED_W = 68


class Sidebar(QFrame):
    pageSelected = Signal(int)

    def __init__(self, items: list[tuple[str, str]], footer_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(EXPANDED_W)
        self._expanded = True
        self._items = items

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 14)
        root.setSpacing(6)

        # ---- 头部：Logo + 汉堡按钮 ----
        head = QHBoxLayout()
        head.setSpacing(6)
        self.lbl_logo = QLabel("🔄")
        self.lbl_logo.setStyleSheet("font-size: 17pt;")
        self.lbl_app = QLabel("万能转换器")
        self.lbl_app.setObjectName("AppTitle")
        self.btn_burger = QPushButton("☰")
        self.btn_burger.setObjectName("BurgerButton")
        self.btn_burger.setCursor(self.cursor())
        self.btn_burger.setFixedSize(38, 38)
        self.btn_burger.clicked.connect(self.toggle)
        head.addWidget(self.lbl_logo)
        head.addWidget(self.lbl_app)
        head.addStretch(1)
        head.addWidget(self.btn_burger)
        root.addLayout(head)
        root.addSpacing(12)

        # ---- 导航按钮 ----
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for i, (icon, label) in enumerate(items):
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName("NavButton")
            btn.setCursor(self.cursor())
            btn.setCheckable(True)
            btn.setFixedHeight(42)
            self._group.addButton(btn, i)
            self._buttons.append(btn)
            root.addWidget(btn)
        self._group.idClicked.connect(self.pageSelected.emit)
        if self._buttons:
            self._buttons[0].setChecked(True)

        root.addStretch(1)

        # ---- 底部状态 ----
        self.lbl_footer = QLabel(footer_text)
        self.lbl_footer.setObjectName("SidebarFooter")
        self.lbl_footer.setWordWrap(True)
        root.addWidget(self.lbl_footer)

        self._anim = QParallelAnimationGroup(self)
        for prop in (b"maximumWidth", b"minimumWidth"):
            a = QPropertyAnimation(self, prop, self)
            a.setDuration(160)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.addAnimation(a)

    # ------------------------------------------------------------

    def toggle(self):
        self._expanded = not self._expanded
        target = EXPANDED_W if self._expanded else COLLAPSED_W
        self._anim.stop()
        for i in range(self._anim.animationCount()):
            a = self._anim.animationAt(i)
            a.setStartValue(self.width())
            a.setEndValue(target)
        self._anim.start()
        self._refresh_texts()

    def set_footer(self, text: str):
        self.lbl_footer.setText(text)

    def _refresh_texts(self):
        for btn, (icon, label) in zip(self._buttons, self._items):
            btn.setText(icon if not self._expanded else f"{icon}  {label}")
        self.lbl_logo.setVisible(self._expanded)
        self.lbl_app.setVisible(self._expanded)
        self.lbl_footer.setVisible(self._expanded)
        if not self._expanded:
            for btn in self._buttons:
                btn.setToolTip(btn.text())
        else:
            for btn in self._buttons:
                btn.setToolTip("")
