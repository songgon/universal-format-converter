"""图片转换模块：Pillow 互转、SVG 栅格化、多图合并 PDF。"""
from __future__ import annotations

import io
import os
import shutil
import sys
import threading
from pathlib import Path

from .utils import ConvertError, safe_output_path

try:
    from PIL import Image
except ImportError as e:  # pragma: no cover
    raise ConvertError("缺少 Pillow 依赖") from e

try:  # HEIC（iPhone 照片）支持，可选
    import pillow_heif
    pillow_heif.register_heif_opener()
    HAS_HEIF = True
except ImportError:
    HAS_HEIF = False

# svglib / reportlab 体积大、导入慢（合计约 1 秒），而多数用户根本不转 SVG。
# 若在模块顶层导入，会拖慢每一次启动，因此改为按需加载（见 _svg_module）。
_SVG_MOD = None
_SVG_CHECKED = False
_SVG_LOCK = threading.Lock()

_SVG_FONTS_READY = False
_SVG_FONTS_LOCK = threading.Lock()


def _svg_available() -> bool:
    """探测 SVG 依赖是否存在，**不加载模块、且只探测一次**。

    can_convert() 在程序启动路径上被调用（构建可用格式列表），因此：
    1. 不能真正 import，否则白省那 1 秒；
    2. 结果必须缓存 —— frozen 环境下 find_spec 单次开销可观，
       而这里会被反复调用（每种目标格式 × svg 源格式）。
    打包版一定带了 svglib/reportlab，直接放行，连探测都省掉。
    """
    global _SVG_MOD, _SVG_CHECKED
    if _SVG_CHECKED:
        return _SVG_MOD is not False
    if getattr(sys, "frozen", False):
        _SVG_CHECKED = True
        return True
    import importlib.util
    try:
        ok = (importlib.util.find_spec("svglib") is not None
              and importlib.util.find_spec("reportlab") is not None)
    except (ImportError, ValueError):
        ok = False
    _SVG_CHECKED = True
    if not ok:
        _SVG_MOD = False
    return ok


def _svg_module():
    """按需加载 SVG 依赖，返回 (svg2rlg, renderPM)；不可用返回 False。"""
    global _SVG_MOD
    if _SVG_MOD is None:
        with _SVG_LOCK:
            if _SVG_MOD is None:
                try:
                    from svglib.svglib import svg2rlg
                    from reportlab.graphics import renderPM
                    _SVG_MOD = (svg2rlg, renderPM)
                except ImportError:
                    _SVG_MOD = False
    return _SVG_MOD


def _ensure_svg_fonts() -> None:
    """reportlab 渲染 SVG 文字需要字体文件；把 Windows 系统字体注册到
    SVG 常用的字体名下，否则 FreeType 报 'cannot open resource'。
    惰性执行并加锁，避免并行转换时的注册竞态。"""
    global _SVG_FONTS_READY
    with _SVG_FONTS_LOCK:
        if _SVG_FONTS_READY:
            return
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            candidates = {
                "Helvetica": "arial.ttf", "Arial": "arial.ttf",
                "Helvetica-Bold": "arialbd.ttf", "Arial-Bold": "arialbd.ttf",
                "Times-Roman": "times.ttf", "Times-Bold": "timesbd.ttf",
                "Courier": "consola.ttf", "Courier-New": "consola.ttf",
                "SimSun": "simsun.ttc", "宋体": "simsun.ttc",
            }
            for name, fname in candidates.items():
                fpath = win_fonts / fname
                if fpath.exists():
                    try:
                        pdfmetrics.registerFont(TTFont(name, str(fpath)))
                    except Exception:
                        pass
        except Exception:
            pass
        _SVG_FONTS_READY = True


INPUT_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff", "ico", "svg", "heic", "heif"}
TARGETS = [
    ("png", "PNG 图片"), ("jpg", "JPG 图片"), ("webp", "WebP 图片"),
    ("bmp", "BMP 图片"), ("gif", "GIF 图片"), ("tif", "TIFF 图片"),
    ("ico", "ICO 图标"), ("pdf", "PDF 文档（图片合成）"),
]

# JPEG/BMP/ICO 不支持透明通道，铺白底


def can_convert(src_ext: str, dst_ext: str) -> bool:
    if src_ext == "svg" and not _svg_available():
        return False
    if src_ext in ("heic", "heif") and not HAS_HEIF:
        return False
    return src_ext in INPUT_EXTS and dst_ext in {t for t, _ in TARGETS}


def convert(src: Path, target: str, out_dir: Path | None, options: dict) -> list[Path]:
    if target == "pdf":
        dst = safe_output_path(src, out_dir, "pdf", options.get("overwrite", False))
        images_to_pdf([src], dst)
        return [dst]

    dst = safe_output_path(src, out_dir, target, options.get("overwrite", False))
    quality = int(options.get("quality", 92))

    if src_ext := src.suffix.lower().lstrip("."):
        if src_ext == "svg":
            img = _svg_to_pillow(src)
        else:
            img = Image.open(src)
    else:  # pragma: no cover
        raise ConvertError("无法识别的图片文件")

    # 动图 GIF -> GIF 直接复制，避免丢帧
    if src_ext == "gif" and target == "gif":
        shutil.copyfile(src, dst)
        return [dst]

    fmt = {"jpg": "JPEG", "jpeg": "JPEG", "tif": "TIFF", "tiff": "TIFF"}.get(target, target.upper())
    if fmt in ("JPEG", "BMP") or (fmt == "ICO"):
        if img.mode in ("RGBA", "LA", "P", "PA"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA")

    save_kwargs: dict = {}
    if fmt == "JPEG":
        save_kwargs = {"quality": quality, "optimize": True}
    elif fmt == "WEBP":
        save_kwargs = {"quality": quality}
    elif fmt == "ICO":
        save_kwargs = {"sizes": [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]}

    try:
        img.save(dst, format=fmt, **save_kwargs)
    except OSError:
        # JPEG/TIFF 对大尺寸等的兼容兜底：先转 RGB 再存
        img.convert("RGB").save(dst, format=fmt, **save_kwargs)
    return [dst]


def _svg_to_pillow(src: Path) -> Image.Image:
    mod = _svg_module()  # 真正需要转 SVG 时才加载 svglib / reportlab
    if mod is False:
        raise ConvertError("SVG 支持未安装（需要 svglib / reportlab）")
    svg2rlg, renderPM = mod
    try:
        _ensure_svg_fonts()
        drawing = svg2rlg(str(src))
        if drawing is None:
            raise ValueError("svglib 解析结果为空")
        png_bytes = renderPM.drawToString(drawing, fmt="PNG", dpi=144)
        return Image.open(io.BytesIO(png_bytes))
    except ConvertError:
        raise
    except Exception as e:
        raise ConvertError(f"SVG 解析失败：{e}") from e


def images_to_pdf(paths: list[Path], dst: Path) -> None:
    """多张图片按顺序合成为一个 PDF，每页一张、页面尺寸等于图片尺寸。

    MuPDF 的 insert_image 只认 PNG/JPEG 等常见格式（不认 WebP/ICO/HEIC），
    因此除 PNG/JPEG/SVG 直接处理外，其余格式先经 Pillow 转成 PNG 字节流。
    """
    try:
        import pymupdf
    except ImportError as e:
        raise ConvertError("缺少 PyMuPDF 依赖") from e

    doc = pymupdf.open()
    for p in paths:
        ext = p.suffix.lower().lstrip(".")
        if ext == "svg":
            img = _svg_to_pillow(p)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
        elif ext in ("png", "jpg", "jpeg"):
            data = p.read_bytes()
        else:
            try:
                with Image.open(p) as im:
                    buf = io.BytesIO()
                    im.save(buf, format="PNG")
                    data = buf.getvalue()
            except Exception as e:
                raise ConvertError(f"无法读取图片 {p.name}：{e}") from e
        try:
            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
        except Exception as e:
            raise ConvertError(f"无法读取图片 {p.name}：{e}") from e
        page = doc.new_page(width=w, height=h)
        page.insert_image(pymupdf.Rect(0, 0, w, h), stream=data)
    doc.save(str(dst), deflate=True)
    doc.close()
