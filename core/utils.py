"""通用工具：错误类型、编码探测、输出路径处理。"""
from __future__ import annotations

import threading
from pathlib import Path

# 并行转换时多线程会同时计算输出路径，需互斥
_path_lock = threading.Lock()


class ConvertError(Exception):
    """转换失败，message 面向最终用户。"""


class ConvertCancelled(ConvertError):
    """用户主动取消。"""


def read_text_smart(path: Path) -> str:
    """按 BOM / utf-8 / gbk / utf-16 顺序尝试解码文本文件。"""
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ConvertError("无法识别该文本文件的编码")


def safe_output_path(src: Path, out_dir: Path | None, target: str,
                     overwrite: bool = False, tag: str = "") -> Path:
    """为目标文件生成路径；并行转换时通过原子占位保证同名不冲突，
    且覆盖模式下绝不允许路径等于源文件本身。
    注意：占位会先创建空文件，若后续转换失败可能留下空的目标文件。"""
    with _path_lock:
        out_dir = Path(out_dir) if out_dir else src.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = src.stem + (f"_{tag}" if tag else "")

        def _unique(start: int = 2) -> Path:
            n = start
            while True:
                candidate = out_dir / f"{stem}.{target}" if n == 1 else out_dir / f"{stem} ({n}).{target}"
                try:
                    candidate.open("x").close()  # 原子占位：并行时其他线程拿不到这个名字
                    return candidate
                except FileExistsError:
                    n += 1

        candidate = out_dir / f"{stem}.{target}"
        if not overwrite:
            try:
                candidate.open("x").close()
                return candidate
            except FileExistsError:
                return _unique(2)
        try:
            same_as_src = candidate.resolve() == src.resolve()
        except OSError:
            same_as_src = candidate == src
        return _unique(2) if same_as_src else candidate


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))
