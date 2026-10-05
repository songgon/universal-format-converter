import sys

sys.path.insert(0, r"D:\智谱\格式转换器")
sys.stdout.reconfigure(encoding="utf-8")
import os  # noqa: E402

os.chdir(r"D:\智谱\格式转换器")
from PySide6.QtCore import QSettings  # noqa: E402

s = QSettings("UniversalConverter", "FormatConverter")
s.clear()
print("操作记忆已重置")
