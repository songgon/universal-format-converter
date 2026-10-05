"""应用主题：明暗双主题、渐变强调色与全局样式表。"""

# ---------------- 调色板 ----------------

LIGHT = {
    "accent": "#2f6bff", "accent2": "#6d4aff", "accent_hover": "#2456d6",
    "accent_disabled": "#b9c9f5", "accent_soft": "#eaf0ff",
    "bg": "#f3f5fa", "card": "#ffffff", "border": "#e4e9f2",
    "text": "#182136", "sub": "#64708a", "muted": "#98a2b8",
    "sidebar": "#151b29", "sidebar2": "#10141f", "side_text": "#9aa5b8",
    "side_text_active": "#ffffff", "drop_bg": "#fafcff", "drop_border": "#bcc8de",
    "input_bg": "#ffffff", "input_border": "#d8dfea",
    "thead": "#f6f8fc", "row_alt": "#fafbfe", "sel_bg": "#e8f0fe",
    "progress_track": "#e4e9f2", "btn_bg": "#ffffff", "btn_border": "#d8dfea",
    "log_bg": "#fafcfe", "banner_bg": "#fff7e0", "banner_border": "#f0dca8",
    "banner_text": "#8a6d1f",
}

DARK = {
    "accent": "#4d82ff", "accent2": "#8b5cf6", "accent_hover": "#6b9bff",
    "accent_disabled": "#33415e", "accent_soft": "#1d2740",
    "bg": "#10141d", "card": "#1a2030", "border": "#28324a",
    "text": "#e7ebf4", "sub": "#9aa5bd", "muted": "#667089",
    "sidebar": "#0b0e16", "sidebar2": "#080a10", "side_text": "#7e8aa3",
    "side_text_active": "#ffffff", "drop_bg": "#141a28", "drop_border": "#3a4666",
    "input_bg": "#1f2637", "input_border": "#34405c",
    "thead": "#202839", "row_alt": "#1e2534", "sel_bg": "#24304d",
    "progress_track": "#232b3f", "btn_bg": "#232b40", "btn_border": "#39445f",
    "log_bg": "#141926", "banner_bg": "#2b2413", "banner_border": "#57491f",
    "banner_text": "#e5c26a",
}

STATUS_COLORS = {"ok": "#16a34a", "fail": "#dc2626", "skip": "#94a3b8"}
STATUS_TEXT = {"ok": "● 完成", "fail": "● 失败", "skip": "○ 跳过",
               "wait": "待转换", "run": "⟳ 转换中…"}


def build_stylesheet(t: dict) -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI";
    outline: none;
}}
QMainWindow, QWidget#PageRoot {{ background: {t['bg']}; }}

/* ================= 侧边栏 ================= */
QFrame#Sidebar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {t['sidebar']}, stop:1 {t['sidebar2']});
    border: none;
}}
QFrame#Sidebar QLabel {{ background: transparent; }}
QLabel#AppTitle {{ font-size: 13pt; font-weight: 600; color: #ffffff; }}
QLabel#SidebarFooter {{ color: {t['side_text']}; font-size: 8.5pt; }}
QPushButton#NavButton {{
    color: {t['side_text']}; background: transparent; border: none;
    text-align: left; padding: 11px 14px; border-radius: 10px; font-size: 10.5pt;
}}
QPushButton#NavButton:hover {{
    background: rgba(255, 255, 255, 0.07); color: #eef1f7;
}}
QPushButton#NavButton:checked {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent']}, stop:1 {t['accent2']});
    color: white; font-weight: 600;
}}
QPushButton#BurgerButton {{
    color: {t['side_text']}; background: transparent; border: none;
    border-radius: 8px; font-size: 14pt; padding: 6px 10px;
}}
QPushButton#BurgerButton:hover {{ background: rgba(255,255,255,0.08); color: white; }}
QPushButton#ThemeButton {{
    color: {t['side_text']}; background: rgba(255,255,255,0.05);
    border: none; border-radius: 8px; font-size: 10pt; padding: 7px;
}}
QPushButton#ThemeButton:hover {{ background: rgba(255,255,255,0.12); color: white; }}

/* ================= 标题栏 ================= */
QFrame#TitleBar {{
    background: {t['sidebar2']};
    border: none;
}}
QLabel#TBTitle {{ color: #cfd6e4; font-size: 9.5pt; }}
QPushButton#TBButton {{
    color: {t['side_text']}; background: transparent; border: none;
    border-radius: 7px; font-size: 11pt; padding: 4px 12px;
}}
QPushButton#TBButton:hover {{ background: rgba(255,255,255,0.12); color: white; }}
QPushButton#TBClose:hover {{ background: #e81123; color: white; }}

/* ================= 页面通用 ================= */
QLabel#PageTitle {{ font-size: 17pt; font-weight: 600; color: {t['text']}; background: transparent; }}
QLabel#PageSub {{ color: {t['sub']}; background: transparent; }}
QLabel#CardTitle {{ font-size: 10.5pt; font-weight: 600; color: {t['text']}; background: transparent; }}
QLabel#HintLabel {{ color: {t['sub']}; font-size: 9pt; background: transparent; }}
QLabel#Elapsed {{ color: {t['sub']}; font-size: 9pt; background: transparent; }}

QFrame#Card {{
    background: {t['card']}; border: 1px solid {t['border']}; border-radius: 14px;
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ================= 拖拽区 ================= */
QFrame#DropZone {{
    border: 2px dashed {t['drop_border']}; border-radius: 14px; background: {t['drop_bg']};
}}
QFrame#DropZone:hover {{ border-color: {t['accent']}; background: {t['accent_soft']}; }}
QFrame#DropZone QLabel {{ background: transparent; }}

/* ================= 表格 ================= */
QTableWidget {{
    background: transparent; border: none; border-radius: 10px;
    gridline-color: transparent; selection-background-color: {t['sel_bg']};
    selection-color: {t['text']}; alternate-background-color: {t['row_alt']};
}}
QTableWidget::item {{ padding: 6px 4px; border: none; }}
QHeaderView::section {{
    background: {t['thead']}; color: {t['sub']}; border: none;
    border-bottom: 1px solid {t['border']};
    padding: 9px 6px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {t['thead']}; border: none; }}

/* ================= 按钮 ================= */
QPushButton {{
    background: {t['btn_bg']}; color: {t['text']}; border: 1px solid {t['btn_border']};
    border-radius: 9px; padding: 7px 16px; font-size: 10pt;
}}
QPushButton:hover {{ border-color: {t['accent']}; color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['muted']}; border-color: {t['border']}; }}
QPushButton#ConvertBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent']}, stop:1 {t['accent2']});
    color: white; font-weight: 600; border: none;
    border-radius: 11px; padding: 12px 34px; font-size: 11.5pt;
}}
QPushButton#ConvertBtn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent_hover']}, stop:1 {t['accent2']});
}}
QPushButton#ConvertBtn:disabled {{ background: {t['accent_disabled']}; }}
QPushButton#CancelBtn {{
    background: transparent; color: #d64545; border: 1px solid #f3c8c8;
}}
QPushButton#CancelBtn:hover {{ border-color: #d64545; background: #fff5f5; }}
QPushButton#IconBtn {{
    background: transparent; border: 1px solid {t['btn_border']};
    border-radius: 8px; padding: 5px 11px; font-weight: 600;
}}

/* ================= 输入控件 ================= */
QComboBox {{
    background: {t['input_bg']}; border: 1px solid {t['input_border']}; border-radius: 9px;
    padding: 6px 12px; color: {t['text']}; font-size: 10pt;
}}
QComboBox:hover {{ border-color: {t['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {t['muted']}; margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {t['card']}; border: 1px solid {t['border']}; border-radius: 9px;
    selection-background-color: {t['sel_bg']}; selection-color: {t['text']};
    padding: 4px;
}}
QLineEdit {{
    background: {t['input_bg']}; border: 1px solid {t['input_border']}; border-radius: 9px;
    padding: 6px 10px; color: {t['text']};
}}
QLineEdit:focus {{ border-color: {t['accent']}; }}

QRadioButton {{ color: {t['text']}; background: transparent; spacing: 6px; }}
QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 9px;
    border: 2px solid {t['input_border']}; background: {t['input_bg']};
}}
QRadioButton::indicator:hover {{ border-color: {t['accent']}; }}
QRadioButton::indicator:checked {{ border: 5px solid {t['accent']}; background: {t['input_bg']}; }}

QCheckBox {{ color: {t['text']}; background: transparent; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 2px solid {t['input_border']}; background: {t['input_bg']};
}}
QCheckBox::indicator:hover {{ border-color: {t['accent']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}

/* ================= 进度条 / 日志 ================= */
QProgressBar {{
    background: {t['progress_track']}; border: none; border-radius: 7px;
    height: 14px; text-align: center; color: transparent; font-size: 8.5pt;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent']}, stop:1 {t['accent2']});
    border-radius: 7px;
}}

QPlainTextEdit#Log {{
    background: {t['log_bg']}; border: 1px solid {t['border']}; border-radius: 10px;
    color: {t['text']}; font-size: 9pt;
    selection-background-color: {t['sel_bg']};
}}

/* ================= 提示横幅 ================= */
QFrame#Banner {{
    background: {t['banner_bg']}; border: 1px solid {t['banner_border']}; border-radius: 10px;
}}
QFrame#Banner QLabel {{ color: {t['banner_text']}; background: transparent; }}

/* ================= 滚动条 ================= */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['input_border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['input_border']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def stylesheet(dark: bool) -> str:
    return build_stylesheet(DARK if dark else LIGHT)
