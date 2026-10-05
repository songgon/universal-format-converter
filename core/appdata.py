"""转换统计与托盘图标资源。

- stats.json 存于 %APPDATA%/UniversalConverter/，记录累计转换与成功率
- ensure_icon() 生成应用图标（assets/icon.ico，缺省时现场绘制）
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_DIR = Path(os.environ.get("APPDATA", Path.home())) / "UniversalConverter"
_STATS = _DIR / "stats.json"
_LOCK = threading.Lock()


def _load() -> dict:
    try:
        return json.loads(_STATS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"total": 0, "ok": 0, "fail": 0, "by_target": {}}


def record_conversion(ok_count: int, fail_count: int, target: str) -> dict:
    with _LOCK:
        d = _load()
        d["total"] = d.get("total", 0) + ok_count + fail_count
        d["ok"] = d.get("ok", 0) + ok_count
        d["fail"] = d.get("fail", 0) + fail_count
        by_t = d.setdefault("by_target", {})
        by_t[target] = by_t.get(target, 0) + ok_count + fail_count
        try:
            _DIR.mkdir(parents=True, exist_ok=True)
            _STATS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
        return d


def summary_line() -> str:
    d = _load()
    total = d.get("total", 0)
    if not total:
        return ""
    rate = d.get("ok", 0) * 100 // total
    return f"累计转换 {total} 次 · 成功率 {rate}%"


def icon_path() -> Path | None:
    """返回应用图标路径；不存在时现场绘制一次。"""
    here = Path(__file__).resolve().parent.parent
    for base in (Path(sys_executable_dir()), here):
        p = base / "assets" / "icon.ico"
        if p.is_file():
            return p
    try:
        return _draw_icon(here / "assets" / "icon.ico")
    except Exception:
        return None


def sys_executable_dir() -> str:
    import sys
    return Path(sys.executable).parent


def _draw_icon(dst: Path) -> Path | None:
    """现场绘制一枚渐变圆角 + 白色环形箭头的图标。"""
    from PIL import Image, ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 渐变圆角方块
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / size
        gd.line([(0, y), (size, y)],
                fill=(int(0x2F + (0x6D - 0x2F) * t),
                      int(0x6B + (0x4A - 0x6B) * t),
                      int(0xFF + (0xFF - 0xFF) * t), 255))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill=255)
    img.paste(grad, (0, 0), mask)
    # 白色环形箭头
    d = ImageDraw.Draw(img)
    cx, cy, r, w = size // 2, size // 2, 74, 26
    d.arc([cx - r, cy - r, cx + r, cy + r], start=30, end=300, fill="white", width=w)
    # 箭头三角
    import math
    ang = math.radians(30)
    tip = (cx + r * math.cos(ang), cy - r * math.sin(ang))
    d.polygon([tip,
               (tip[0] - 34, tip[1] - 6),
               (tip[0] - 10, tip[1] - 34)], fill="white")
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])
    return dst
