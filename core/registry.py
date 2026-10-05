"""转换注册表：类别识别、目标格式汇总、按源文件派发到各模块。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import data_formats, documents, images, media
from .utils import ConvertError, safe_output_path

CATEGORY_LABELS = {"images": "图片", "documents": "文档", "data": "数据", "media": "音视频"}

# 输出品质预设：界面只让用户选档位，具体参数由这里统一决定
QUALITY_PRESETS = {
    "max": {"label": "最高品质（文件较大）", "quality": 100, "dpi": 300, "media_level": "max"},
    "high": {"label": "高品质（推荐）", "quality": 95, "dpi": 220, "media_level": "normal"},
    "normal": {"label": "标准（文件更小）", "quality": 88, "dpi": 150, "media_level": "normal"},
}

_EXT_CATEGORY: dict[str, str] = {}
for _e in images.INPUT_EXTS:
    _EXT_CATEGORY[_e] = "images"
for _e in documents.INPUT_EXTS:
    _EXT_CATEGORY[_e] = "documents"
for _e in data_formats.INPUT_EXTS:
    _EXT_CATEGORY[_e] = "data"
for _e in media.AUDIO_INPUTS | media.VIDEO_INPUTS:
    _EXT_CATEGORY[_e] = "media"

_MODULES = [("images", images), ("documents", documents), ("data", data_formats), ("media", media)]


@dataclass
class ConvertResult:
    outputs: list[Path] = field(default_factory=list)
    note: str = ""


def detect_category(path: Path) -> str | None:
    return _EXT_CATEGORY.get(path.suffix.lower().lstrip("."))


def category_of_supported(path: Path) -> str | None:
    """文件类别；音视频还需 ffmpeg 可用。"""
    cat = detect_category(path)
    if cat == "media" and not media.is_available():
        return None
    return cat


def _category_exts(cat: str) -> set[str]:
    return {e for e, c in _EXT_CATEGORY.items() if c == cat}


def targets_for_categories(cats: set[str]) -> list[tuple[str, str]]:
    """汇总若干类别可用的目标格式（去重，保持模块顺序）。"""
    exts: set[str] = set()
    for c in cats:
        exts |= _category_exts(c)
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, mod in _MODULES:
        for ext, label in mod.TARGETS:
            if ext in seen:
                continue
            if any(mod.can_convert(src, ext) for src in exts):
                seen.add(ext)
                result.append((ext, label))
    return result


def _module_for(src_ext: str, dst_ext: str):
    for _, mod in _MODULES:
        if mod.can_convert(src_ext, dst_ext):
            return mod
    return None


def all_input_extensions() -> set[str]:
    return set(_EXT_CATEGORY.keys())


def convert_file(src: Path, target: str, out_dir: Path | None = None,
                 options: dict | None = None) -> ConvertResult:
    """转换单个文件；失败抛 ConvertError，成功返回输出文件列表。"""
    options = options or {}
    src_ext = src.suffix.lower().lstrip(".")
    if not src.exists():
        raise ConvertError("文件不存在")
    mod = _module_for(src_ext, target)
    if mod is None:
        raise ConvertError(f"不支持 {src_ext.upper()} → {target.upper()} 的组合")
    outputs = mod.convert(src, target, out_dir, options)
    return ConvertResult(outputs=outputs)


def convert_images_to_single_pdf(paths: list[Path], out_dir: Path,
                                 options: dict | None = None) -> ConvertResult:
    """多张图片合并为一个 PDF（GUI“合并”选项）。"""
    options = options or {}
    dst_dir = Path(out_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    stem = paths[0].stem + "_合并" if len(paths) > 1 else paths[0].stem
    dst = dst_dir / f"{stem}.pdf"
    if not options.get("overwrite", False):
        n = 2
        while dst.exists():
            dst = dst_dir / f"{stem} ({n}).pdf"
            n += 1
    images.images_to_pdf(paths, dst)
    return ConvertResult(outputs=[dst], note="已合并为单个 PDF")


def convert_pdfs_to_merged(paths: list[Path], out_dir: Path,
                           options: dict | None = None) -> ConvertResult:
    """多个 PDF 合并为一个（GUI“合并”选项）。"""
    from . import pdftools
    options = options or {}
    dst_dir = Path(out_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    stem = paths[0].stem + "_合并" if len(paths) > 1 else paths[0].stem
    dst = dst_dir / f"{stem}.pdf"
    if not options.get("overwrite", False):
        n = 2
        while dst.exists():
            dst = dst_dir / f"{stem} ({n}).pdf"
            n += 1
    pdftools.merge_pdfs(paths, dst)
    return ConvertResult(outputs=[dst], note=f"已合并 {len(paths)} 个 PDF")


def extract_zip_for_conversion(zip_path: Path, dest_dir: Path,
                               max_total_bytes: int = 1024 ** 3) -> list[Path]:
    """解压 zip 中受支持的可转换文件到 dest_dir（防路径穿越，限总解压 1GB）。"""
    import zipfile
    supported = all_input_extensions()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if name.endswith("/") or "\\" in name:
                continue
            stem_name = Path(name).name  # 只取文件名，防路径穿越
            ext = Path(stem_name).suffix.lower().lstrip(".")
            if ext not in supported:
                continue
            total += info.file_size
            if total > max_total_bytes:
                break
            data = z.read(name)
            out = dest_dir / stem_name
            n = 2
            while out.exists():
                out = dest_dir / f"{Path(stem_name).stem} ({n}).{ext}"
                n += 1
            out.write_bytes(data)
            outputs.append(out)
    return outputs
