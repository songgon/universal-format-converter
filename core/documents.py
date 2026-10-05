"""文档转换模块：TXT / Markdown / HTML / DOCX / PDF / RTF 互通。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

from .utils import ConvertError, read_text_smart, safe_output_path, html_escape

INPUT_EXTS = {"txt", "md", "markdown", "html", "htm", "docx", "doc", "pdf", "rtf",
              "pptx", "ppt", "epub"}

# 这些格式交给 LibreOffice 高保真转 PDF（Word/WPS/PPT 系排版复杂，内置引擎只做兜底）
_LO_INPUTS = {"docx", "doc", "rtf", "pptx", "ppt"}
TARGETS = [
    ("txt", "TXT 文本"), ("md", "Markdown 文档"), ("html", "HTML 网页"),
    ("docx", "Word 文档"), ("pdf", "PDF 文档"), ("epub", "EPUB 电子书"),
    ("png", "PNG 图片（仅 PDF 源）"), ("jpg", "JPG 图片（仅 PDF 源）"),
    ("split", "PDF 拆分（每页一个，仅 PDF 源）"),
    ("encrypt", "PDF 加密（仅 PDF 源）"),
    ("decrypt", "PDF 解密（仅 PDF 源）"),
]


def can_convert(src_ext: str, dst_ext: str) -> bool:
    if src_ext not in INPUT_EXTS:
        return False
    if src_ext == "epub":
        return dst_ext in ("txt", "md", "html", "docx")
    if src_ext == "pdf":
        return dst_ext in ("txt", "md", "html", "docx", "png", "jpg", "jpeg",
                           "split", "encrypt", "decrypt")
    if src_ext in ("pptx", "ppt"):
        if dst_ext in ("txt", "md", "html", "docx"):
            return src_ext == "pptx"  # 旧版 .ppt 提不了文本
        if dst_ext == "pdf":
            return libreoffice_path() is not None
        return False
    if dst_ext in ("png", "jpg", "jpeg", "split", "encrypt", "decrypt"):
        return False
    if dst_ext == "epub":
        return src_ext in ("txt", "md", "markdown", "html", "htm", "docx", "rtf")
    return dst_ext in ("txt", "md", "html", "docx", "pdf")


def convert(src: Path, target: str, out_dir: Path | None, options: dict) -> list[Path]:
    overwrite = options.get("overwrite", False)
    src_ext = src.suffix.lower().lstrip(".")

    # ---- PDF 工具目标（拆分/加密/解密，借鉴 FlyingMouse Format）----
    if src_ext == "pdf" and target in ("split", "encrypt", "decrypt"):
        from .pdftools import decrypt_pdf, encrypt_pdf, split_pdf
        if target == "split":
            outs = split_pdf(src, out_dir or src.parent,
                             int(options.get("split_pages", 1)), overwrite)
            return outs
        dst = safe_output_path(src, out_dir, "pdf", overwrite)
        if target == "encrypt":
            encrypt_pdf(src, dst, options.get("pdf_password", ""))
        else:
            decrypt_pdf(src, dst, options.get("pdf_password", ""))
        return [dst]

    if src_ext == "pdf":
        if target in ("png", "jpg", "jpeg"):
            return _pdf_to_images(src, target, out_dir, options)
        if target == "txt":
            return _pdf_to_text(src, out_dir, "txt", overwrite)
        if target == "md":
            return _pdf_to_text(src, out_dir, "md", overwrite)
        if target == "html":
            return _pdf_to_html(src, out_dir, overwrite)
        if target == "docx":
            return _pdf_to_docx(src, out_dir, overwrite)

    # ---- Pandoc 高保真路由：md→docx（表格/列表/代码保留）----
    if src_ext in ("md", "markdown") and target == "docx" and pandoc_path():
        dst = safe_output_path(src, out_dir, "docx", overwrite)
        try:
            produced = pandoc_convert(src, "docx", Path(tempfile.mkdtemp(prefix="pandoc_")))
            shutil.move(str(produced), dst)
            return [dst]
        except ConvertError:
            pass  # 降级为内置转换

    # ---- Pandoc + LibreOffice 链：md→docx→PDF，专业排版 ----
    if (src_ext in ("md", "markdown") and target == "pdf"
            and pandoc_path() and libreoffice_path()
            and options.get("use_lo", True)):
        try:
            tmpdir = Path(tempfile.mkdtemp(prefix="mdpdf_"))
            docx_tmp = pandoc_convert(src, "docx", tmpdir)
            dst = safe_output_path(src, out_dir, "pdf", overwrite)
            office_to_pdf(docx_tmp, dst)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return [dst]
        except ConvertError:
            pass  # 降级为内置引擎

    # ---- EPUB 读取：转文本类格式 ----
    if src_ext == "epub":
        if target == "epub":
            raise ConvertError("源文件已经是 EPUB 格式")
        from .epub_tools import read_epub
        blocks = []
        for ctitle, ctext in read_epub(src):
            blocks.append((1, ctitle))
            blocks.extend((0, ln.strip()) for ln in ctext.splitlines() if ln.strip())
    # ---- PPT / PPTX：PDF 走 LibreOffice，文本类走 python-pptx ----
    elif src_ext in ("pptx", "ppt"):
        if src_ext == "ppt":
            # 旧版 .ppt：经 LibreOffice 中继为 .pptx 后处理
            if not (libreoffice_path() and options.get("use_lo", True)):
                raise ConvertError("旧版 .ppt 需要 LibreOffice 引擎（未检测到或已关闭）；"
                                   "也可先在 PowerPoint/WPS 中另存为 .pptx")
            src = _office_relay(src, "pptx")
        if target == "pdf":
            if not libreoffice_path():
                raise ConvertError("PPT 转 PDF 需要 LibreOffice 高保真引擎（本机未检测到）。"
                                   "可安装 LibreOffice 后重试，或使用内置引擎的近似排版。")
            dst = safe_output_path(src, out_dir, "pdf", overwrite)
            office_to_pdf(src, dst)
            return [dst]
        blocks = _read_pptx(src)
    elif src_ext == "doc":
        # 旧版 .doc：经 LibreOffice 中继为 .docx 后复用全套 docx 管线
        if _sniff_kind(src) == "ole":
            if not (libreoffice_path() and options.get("use_lo", True)):
                raise ConvertError("旧版 .doc 需要 LibreOffice 引擎（未检测到或已关闭）；"
                                   "也可先在 Word/WPS 中另存为 .docx")
            return convert(_office_relay(src, "docx"), target, out_dir, options)
        blocks = [(0, p) for p in _split_paragraphs(read_text_smart(src))]
    elif src_ext == "docx":
        kind = _sniff_kind(src)
        if kind == "ole":
            raise ConvertError(
                "该文件实际是旧版 Word .doc 格式（扩展名与内容不符），无法直接读取。"
                "请用 Word/WPS 打开后「另存为 .docx」再转换。")
        if kind == "html":
            return _convert_html_content(src, read_text_smart(src), target, out_dir, overwrite)
        # 真正的 docx
        if target == "docx":
            # 同格式转换：原样复制，格式零损失
            dst = safe_output_path(src, out_dir, "docx", overwrite)
            shutil.copyfile(src, dst)
            return [dst]
        if target in ("pdf", "html"):
            dst = safe_output_path(src, out_dir, target, overwrite)
            if target == "pdf" and options.get("use_lo", True) and libreoffice_path():
                try:
                    office_to_pdf(src, dst)  # LibreOffice 高保真优先
                    return [dst]
                except ConvertError:
                    pass  # 引擎失败时降级为内置排版引擎
            body = _docx_runs_to_html(src)
            html = _wrap_html_doc(body, src.stem)
            if target == "pdf":
                html_to_pdf(html, dst)
            else:
                dst.write_text(html, encoding="utf-8")
            return [dst]
        # Pandoc 高保真：docx→md（标题/表格/列表结构保留）
        if target == "md" and pandoc_path():
            dst = safe_output_path(src, out_dir, "md", overwrite)
            try:
                produced = pandoc_convert(src, "markdown", Path(tempfile.mkdtemp(prefix="pandoc_")))
                shutil.move(str(produced), dst)
                return [dst]
            except ConvertError:
                pass  # 降级为内置转换
        blocks = _read_docx(src)
    elif src_ext in ("html", "htm"):
        return _convert_html_content(src, read_text_smart(src), target, out_dir, overwrite)
    elif src_ext == "rtf":
        blocks = [(0, line) for line in _rtf_to_text(src).splitlines()]
    elif src_ext in ("md", "markdown"):
        blocks = _read_markdown(read_text_smart(src))
    else:  # txt
        blocks = [(0, p) for p in _split_paragraphs(read_text_smart(src))]

    if target == "epub":
        # 电子书：标题/二级标题分章，无结构文本每 30 段一章
        from .epub_tools import build_epub
        dst = safe_output_path(src, out_dir, "epub", overwrite)
        build_epub(_blocks_to_chapters(blocks, src.stem), dst, src.stem)
        return [dst]

    if target == "txt":
        dst = safe_output_path(src, out_dir, "txt", overwrite)
        dst.write_text("\n\n".join(t for _, t in blocks if t.strip()), encoding="utf-8")
    elif target == "md":
        dst = safe_output_path(src, out_dir, "md", overwrite)
        lines = []
        for lvl, text in blocks:
            if not text.strip():
                continue
            prefix = "#" * min(lvl, 6) + " " if 1 <= lvl <= 6 else ""
            lines.append(prefix + text)
        dst.write_text("\n\n".join(lines), encoding="utf-8")
    elif target == "html":
        dst = safe_output_path(src, out_dir, "html", overwrite)
        dst.write_text(_blocks_to_html_doc(blocks, src.stem), encoding="utf-8")
    elif target == "docx":
        dst = safe_output_path(src, out_dir, "docx", overwrite)
        _write_docx(blocks, dst)
    elif target == "pdf":
        dst = safe_output_path(src, out_dir, "pdf", overwrite)
        if src_ext == "docx" and options.get("use_word") and word_available():
            _docx_to_pdf_word(src, dst)
        elif (src_ext in _LO_INPUTS and libreoffice_path()
              and options.get("use_lo", True)):
            office_to_pdf(src, dst)  # LibreOffice 高保真优先，失败再降级
        else:
            html = _blocks_to_html_doc(blocks, src.stem)
            html_to_pdf(html, dst)
    else:  # pragma: no cover
        raise ConvertError(f"文档模块不支持转换为 {target}")
    return [dst]


def _blocks_to_chapters(blocks: list[tuple[int, str]], title: str) -> list[tuple[str, str]]:
    """把段落块切成电子书章节：一/二级标题开新章；无结构文本每 30 段一章。

    注意：无标题时的默认章标题不能吞掉首个正文段。
    """
    chapters: list[tuple[str, list[str]]] = []
    cur_title: str | None = None
    cur: list[str] = []
    for lvl, text in blocks:
        if not text.strip():
            continue
        if 1 <= lvl <= 2:
            if cur_title is not None:
                chapters.append((cur_title, cur))
            cur_title = text.strip()[:60]
            cur = []
            continue
        if cur_title is None:
            cur_title = title  # 默认章标题；当前段落仍归入正文
        cur.append("<p>" + "<br>".join(html_escape(l) for l in text.split("\n")) + "</p>")
    if cur_title is None:
        cur_title = title
    chapters.append((cur_title, cur))
    chapters = [(t, p) for t, p in chapters if p]
    if len(chapters) <= 1:
        paras = chapters[0][1] if chapters else []
        if len(paras) > 30:
            chapters = [(f"{title} · 第{i + 1}节", paras[j:j + 30])
                        for i, j in enumerate(range(0, len(paras), 30))]
        elif chapters:
            chapters = [(title, paras)]
    return [(t, "\n".join(p)) for t, p in chapters]


def _convert_html_content(src: Path, raw_html: str, target: str,
                          out_dir: Path | None, overwrite: bool) -> list[Path]:
    """HTML 内容（真正的 .html/.htm 或伪装成 .docx 的网页）→ 各目标，尽量保留格式。"""
    if target == "html":
        # 内容本来就是 HTML：原样保存，格式零损失
        dst = safe_output_path(src, out_dir, "html", overwrite)
        shutil.copyfile(src, dst)
        return [dst]
    if target == "docx":
        dst = safe_output_path(src, out_dir, "docx", overwrite)
        _html_to_docx(raw_html, dst)
        return [dst]
    if target == "epub":
        from .epub_tools import build_epub
        dst = safe_output_path(src, out_dir, "epub", overwrite)
        build_epub(_blocks_to_chapters(_read_html(src), src.stem), dst, src.stem)
        return [dst]
    if target == "pdf":
        dst = safe_output_path(src, out_dir, "pdf", overwrite)
        try:
            html_to_pdf(raw_html, dst)  # 直接渲染原始 HTML，保留加粗/颜色
        except ConvertError:
            html_to_pdf(_blocks_to_html_doc(_read_html(src), src.stem), dst)
        return [dst]
    # txt / md：纯文本格式，提取文字
    blocks = _read_html(src)
    if target == "txt":
        dst = safe_output_path(src, out_dir, "txt", overwrite)
        dst.write_text("\n\n".join(t for _, t in blocks if t.strip()), encoding="utf-8")
        return [dst]
    if target == "md":
        dst = safe_output_path(src, out_dir, "md", overwrite)
        lines = []
        for lvl, text in blocks:
            if not text.strip():
                continue
            prefix = "#" * min(lvl, 6) + " " if 1 <= lvl <= 6 else ""
            lines.append(prefix + text)
        dst.write_text("\n\n".join(lines), encoding="utf-8")
        return [dst]
    raise ConvertError(f"文档模块不支持转换为 {target}")


# ---------------------------------------------------------------- PDF

def _pdf_to_text(src: Path, out_dir: Path | None, target: str, overwrite: bool) -> list[Path]:
    import pymupdf
    dst = safe_output_path(src, out_dir, target, overwrite)
    parts = []
    with pymupdf.open(src) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if target == "md" and len(doc) > 1:
                parts.append(f"## 第 {i + 1} 页\n\n{text}")
            else:
                parts.append(text)
    dst.write_text("\n\n".join(p for p in parts if p), encoding="utf-8")
    return [dst]


def _pdf_to_html(src: Path, out_dir: Path | None, overwrite: bool) -> list[Path]:
    import pymupdf
    dst = safe_output_path(src, out_dir, "html", overwrite)
    parts = []
    with pymupdf.open(src) as doc:
        for i, page in enumerate(doc):
            text = html_escape(page.get_text("text").strip())
            if len(doc) > 1:
                parts.append(f"<h2>第 {i + 1} 页</h2><p>{text}</p>")
            else:
                parts.append(f"<p>{text}</p>")
    dst.write_text(_wrap_html_doc("\n".join(parts), src.stem), encoding="utf-8")
    return [dst]


def _pdf_to_docx(src: Path, out_dir: Path | None, overwrite: bool) -> list[Path]:
    import pymupdf
    blocks = []
    with pymupdf.open(src) as doc:
        for i, page in enumerate(doc):
            for line in page.get_text("text").splitlines():
                if line.strip():
                    blocks.append((0, line.strip()))
    dst = safe_output_path(src, out_dir, "docx", overwrite)
    _write_docx(blocks, dst)
    return [dst]


def _pdf_to_images(src: Path, target: str, out_dir: Path | None, options: dict) -> list[Path]:
    import pymupdf
    if target == "jpeg":
        target = "jpg"
    dpi = int(options.get("dpi", 300))
    overwrite = options.get("overwrite", False)
    outputs = []
    with pymupdf.open(src) as doc:
        for i, page in enumerate(doc):
            tag = f"p{i + 1}" if len(doc) > 1 else ""
            dst = safe_output_path(src, out_dir, target, overwrite, tag=tag)
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            pix.save(str(dst))
            outputs.append(dst)
    return outputs


# ---------------------------------------------------------------- DOCX

def _sniff_kind(src: Path) -> str:
    """按文件头嗅探真实类型：zip(docx/xlsx 正确) / ole(旧版 .doc) / html / text。"""
    head = src.read_bytes()[:512]
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:4] == b"\xd0\xcf\x11\xe0":
        return "ole"
    low = head.lower().lstrip()
    if low.startswith((b"<html", b"<!doctype", b"<?xml", b"<table", b"<body")) or b"<html" in low:
        return "html"
    return "text"


def _read_docx(src: Path) -> list[tuple[int, str]]:
    """读取 docx；兼容“网页内容伪装成 .docx”的文件（网上系统导出常见）。"""
    kind = _sniff_kind(src)
    if kind == "ole":
        raise ConvertError(
            "该文件实际是旧版 Word .doc 格式（扩展名与内容不符），无法直接读取。"
            "请用 Word/WPS 打开后「另存为 .docx」再转换。")
    if kind == "html":
        return _read_html(src)
    if kind == "text":
        return [(0, p) for p in _split_paragraphs(read_text_smart(src))]
    try:
        import docx as docx_lib
    except ImportError as e:
        raise ConvertError("缺少 python-docx 依赖") from e
    blocks: list[tuple[int, str]] = []
    d = docx_lib.Document(str(src))
    style_map = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
                 "Heading 4": 4, "Heading 5": 5, "Heading 6": 6,
                 "标题 1": 1, "标题 2": 2, "标题 3": 3, "标题 4": 4}
    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        blocks.append((style_map.get(p.style.name, 0), text))
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            blocks.append((0, " | ".join(cells)))
        blocks.append((0, ""))
    return blocks


def _write_docx(blocks: list[tuple[int, str]], dst: Path) -> None:
    try:
        from docx import Document
    except ImportError as e:
        raise ConvertError("缺少 python-docx 依赖") from e
    doc = Document()
    for lvl, text in blocks:
        if not text.strip():
            continue
        if 1 <= lvl <= 6:
            doc.add_heading(text, level=lvl)
        else:
            doc.add_paragraph(text)
    if not any(t.strip() for _, t in blocks):
        doc.add_paragraph("")
    doc.save(str(dst))


# ---------------------------------------------------------------- LibreOffice 高保真引擎

_LO_LOCK = threading.Lock()  # LibreOffice 同一配置目录不允许并行实例


@lru_cache(maxsize=1)
def libreoffice_path() -> str | None:
    """探测本机 LibreOffice 的 soffice.exe（自带安装 / 项目内置 / 系统位置）。"""
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "LibreOffice" / "program" / "soffice.exe")
    candidates.append(Path("C:/Program Files/LibreOffice/program/soffice.exe"))
    candidates.append(Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"))
    # 打包为 exe 后：tools 位于 exe 同级目录
    candidates.append(Path(sys.executable).parent / "tools" / "libreoffice" / "program" / "soffice.exe")
    candidates.append(Path(__file__).resolve().parent.parent / "tools" / "libreoffice" / "program" / "soffice.exe")
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None


def office_to_pdf(src: Path, dst: Path) -> None:
    """LibreOffice 无头模式转 PDF（Word/WPS/PPT 系排版的保真方案）。"""
    soffice = libreoffice_path()
    if not soffice:
        raise ConvertError("未检测到 LibreOffice，无法使用高保真引擎")
    outdir = Path(tempfile.mkdtemp(prefix="lo_out_"))
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    cmd = [soffice, "--headless", "--norestore", "--invisible", "--nologo",
           f"-env:UserInstallation={profile.as_uri()}",
           "--convert-to", "pdf", "--outdir", str(outdir), str(src.resolve())]
    try:
        with _LO_LOCK:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                      creationflags=0x08000000, timeout=300)
            except subprocess.TimeoutExpired as e:
                raise ConvertError("LibreOffice 转换超时（5 分钟）") from e
        produced = outdir / (src.stem + ".pdf")
        if not produced.exists():
            tail = (proc.stderr or "").strip().splitlines()[-3:]
            raise ConvertError("LibreOffice 转换失败：" + ("；".join(tail) or "未知原因"))
        shutil.move(str(produced), str(dst))
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(outdir, ignore_errors=True)


# ---------------------------------------------------------------- Pandoc 引擎

@lru_cache(maxsize=1)
def pandoc_path() -> str | None:
    exe_dir = Path(sys.executable).parent
    for base in (exe_dir / "tools" / "pandoc",
                 Path(__file__).resolve().parent.parent / "tools" / "pandoc"):
        p = base / "pandoc.exe"
        if p.is_file():
            return str(p)
    return shutil.which("pandoc")


def pandoc_convert(src: Path, to_fmt: str, out_dir: Path, timeout: int = 180) -> Path:
    """Pandoc 格式转换（md↔docx 等，保留表格/列表/代码块），返回输出路径。"""
    exe = pandoc_path()
    if not exe:
        raise ConvertError("未找到 Pandoc")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = out_dir / (src.stem + "." + to_fmt)
    cmd = [exe, str(src.resolve()), "-o", str(produced.resolve()), "--standalone"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              creationflags=0x08000000, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ConvertError("Pandoc 转换超时") from e
    if proc.returncode != 0 or not produced.exists():
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise ConvertError("Pandoc 转换失败：" + ("；".join(tail) or "未知原因"))
    return produced


def _office_relay(src: Path, to_ext: str) -> Path:
    """用 LibreOffice 把旧格式（.doc/.ppt）转成对应开放格式的临时文件。"""
    soffice = libreoffice_path()
    if not soffice:
        raise ConvertError("需要 LibreOffice，但本机未检测到")
    outdir = Path(tempfile.mkdtemp(prefix="lo_relay_"))
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    cmd = [soffice, "--headless", "--norestore", "--invisible", "--nologo",
           f"-env:UserInstallation={profile.as_uri()}",
           "--convert-to", to_ext, "--outdir", str(outdir), str(src.resolve())]
    try:
        with _LO_LOCK:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                                      creationflags=0x08000000, timeout=300)
            except subprocess.TimeoutExpired as e:
                raise ConvertError("LibreOffice 转换超时") from e
        produced = outdir / (src.stem + "." + to_ext)
        if not produced.exists():
            tail = (proc.stderr or "").strip().splitlines()[-3:]
            raise ConvertError(f"LibreOffice 无法将 {src.name} 转为 {to_ext}："
                               + ("；".join(tail) or "未知原因"))
        return produced
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _read_pptx(src: Path) -> list[tuple[int, str]]:
    """PPTX → 逐页文本块（供 TXT/MD/HTML/DOCX 目标）。"""
    try:
        from pptx import Presentation
    except ImportError as e:
        raise ConvertError("缺少 python-pptx 依赖") from e
    blocks: list[tuple[int, str]] = []
    prs = Presentation(str(src))
    for i, slide in enumerate(prs.slides, 1):
        blocks.append((1, f"第 {i} 页"))
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                text = shape.text_frame.text.strip()
                if text:
                    blocks.append((0, text))
        if getattr(slide, "has_notes_slide", False):
            note = slide.notes_slide.notes_text_frame.text.strip()
            if note:
                blocks.append((0, "备注：" + note))
    return blocks or [(0, "")]


def _docx_runs_to_html(src: Path) -> str:
    """真 docx → 带 <b>/<i>/<u>/颜色的 HTML 正文（供 PDF/HTML 目标保留格式）。"""
    import docx as docx_lib
    d = docx_lib.Document(str(src))
    style_map = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3, "Heading 4": 4,
                 "Heading 5": 5, "Heading 6": 6,
                 "标题 1": 1, "标题 2": 2, "标题 3": 3, "标题 4": 4}
    parts: list[str] = []
    for p in d.paragraphs:
        if not p.runs and not p.text.strip():
            continue
        lvl = style_map.get(p.style.name)
        tag = f"h{lvl}" if lvl else "p"
        inner: list[str] = []
        for run in p.runs:
            text = html_escape(run.text)
            if not text:
                continue
            if run.bold:
                text = f"<b>{text}</b>"
            if run.italic:
                text = f"<i>{text}</i>"
            if run.underline:
                text = f"<u>{text}</u>"
            try:
                rgb = run.font.color.rgb
            except Exception:
                rgb = None
            if rgb is not None and str(rgb).upper() != "000000":
                text = f'<span style="color:#{rgb}">{text}</span>'
            inner.append(text)
        parts.append(f"<{tag}>{''.join(inner) or html_escape(p.text)}</{tag}>")
    for table in d.tables:
        rows = []
        for row in table.rows:
            cells = "".join(f"<td>{html_escape(c.text.strip())}</td>" for c in row.cells)
            rows.append(f"<tr>{cells}</tr>")
        if rows:
            parts.append('<table border="1" cellpadding="4" cellspacing="0" width="100%">'
                         + "".join(rows) + "</table>")
    return "\n".join(parts)


_NAMED_COLORS = {
    "red": "FF0000", "blue": "0000FF", "green": "008000", "black": "000000",
    "white": "FFFFFF", "orange": "FFA500", "purple": "800080", "gray": "808080",
    "grey": "808080", "yellow": "FFFF00", "brown": "A52A2A", "pink": "FFC0CB",
}


def _html_to_docx(html_text: str, dst: Path) -> None:
    """HTML → Word 文档，保留加粗/斜体/下划线/颜色/标题/列表/表格。"""
    from bs4 import BeautifulSoup, Comment, NavigableString, Tag
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
    except ImportError as e:
        raise ConvertError("缺少 python-docx 依赖") from e

    soup = BeautifulSoup(html_text, "html.parser")
    for t in soup(["script", "style", "meta", "link", "title", "head"]):
        t.decompose()
    body = soup.body or soup
    doc = Document()

    def _color_of(el):
        c = el.get("color")
        m = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", (el.get("style") or "").lower())
        if m:
            c = m.group(1)
        if not c:
            return None
        c = c.strip().strip("'\"")
        if c.lower() in _NAMED_COLORS:
            c = _NAMED_COLORS[c.lower()]
        if c.startswith("#"):
            c = c[1:]
        if re.fullmatch(r"[0-9a-fA-F]{6}", c or ""):
            return RGBColor.from_string(c.upper())
        m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", c or "")
        if m:
            return RGBColor(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return None

    _BLOCKISH = ("p", "div", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6")

    def _style_flags(el, kw):
        """从 style 属性补充加粗/斜体/下划线（Word 导出的 HTML 常用这种方式）。"""
        style = (el.get("style") or "").lower()
        if re.search(r"font-weight\s*:\s*(bold|[6-9]00)", style):
            kw["bold"] = True
        if "italic" in style:
            kw["italic"] = True
        if "underline" in style:
            kw["underline"] = True

    def _add_inline(par, node, *, bold=False, italic=False, underline=False,
                    color=None, size=None):
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                if not str(child):
                    continue
                run = par.add_run(str(child))
                if bold:
                    run.bold = True
                if italic:
                    run.italic = True
                if underline:
                    run.underline = True
                if color is not None:
                    run.font.color.rgb = color
                if size:
                    run.font.size = Pt(size)
                continue
            if not isinstance(child, Tag):
                continue
            name = (child.name or "").lower()
            if name == "br":
                par.add_run().add_break()
                continue
            kw = {"bold": bold, "italic": italic, "underline": underline,
                  "color": color if color is not None else _color_of(child),
                  "size": size}
            if name in ("b", "strong"):
                kw["bold"] = True
            elif name in ("i", "em"):
                kw["italic"] = True
            elif name == "u":
                kw["underline"] = True
            _style_flags(child, kw)
            m = re.search(r"font-size\s*:\s*(\d+)", child.get("style") or "")
            if m:
                kw["size"] = int(m.group(1))
            _add_inline(par, child, **kw)

    def _table_to_docx(el):
        rows = el.find_all("tr")
        if not rows:
            return
        grid = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                for tr in rows]
        ncols = max(len(r) for r in grid)
        table = doc.add_table(rows=len(grid), cols=ncols)
        table.style = "Table Grid"
        for i, r in enumerate(grid):
            for j, v in enumerate(r):
                table.cell(i, j).text = v

    def _walk(el):
        for child in el.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    doc.add_paragraph(text)
                continue
            if not isinstance(child, Tag):
                continue
            name = (child.name or "").lower()
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                par = doc.add_heading("", level=int(name[1]))
                _add_inline(par, child)
            elif name == "table":
                _table_to_docx(child)
            elif name in ("ul", "ol"):
                style = "List Bullet" if name == "ul" else "List Number"
                for li in child.find_all("li", recursive=False):
                    par = doc.add_paragraph(style=style)
                    _add_inline(par, li)
            elif name in ("br", "hr"):
                continue
            elif name in ("div", "section", "article", "center"):
                # 包含块级子元素则递归展开，否则整体成段
                if child.find(_BLOCKISH):
                    _walk(child)
                else:
                    par = doc.add_paragraph()
                    _add_inline(par, child)
            else:  # p / span / pre 等散块：整块成段，格式随内联标签保留
                par = doc.add_paragraph()
                _add_inline(par, child)

    try:
        _walk(body)
        doc.save(str(dst))
    except ConvertError:
        raise
    except Exception as e:
        raise ConvertError(f"生成 Word 文档失败：{e}") from e


def word_available() -> bool:
    """本机是否安装了**微软** Word（用于高保真 docx→PDF）。

    注意：国产 WPS 会把 "Word.Application" COM 接口抢占注册到自己身上，
    而其 PDF 导出是收费功能。因此这里必须验证接口背后的可执行文件
    确实是微软的 WINWORD.EXE，是 WPS 一律判定为“没有 Word”。
    """
    return _is_ms_word_server(_com_server_path("Word.Application"))


def _com_server_path(progid: str) -> str | None:
    """解析 COM ProgID 背后实际的可执行文件路径（只查注册表，不启动程序）。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID") as k:
            clsid = winreg.QueryValueEx(k, "")[0]
        for hive in (winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER,
                     winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, f"CLSID\\{clsid}\\LocalServer32") as k:
                    return winreg.QueryValueEx(k, "")[0]
            except OSError:
                continue
    except OSError:
        return None
    return None


def _is_ms_word_server(server: str | None) -> bool:
    if not server:
        return False
    s = server.lower()
    if "wps" in s or "kingsoft" in s or "kwps" in s:
        return False  # WPS 伪装的 Word.Application，坚决不用
    return "winword" in s  # 微软 Word 的主程序名


def _docx_to_pdf_word(src: Path, dst: Path) -> None:
    """通过本机安装的**微软** Word 导出 PDF（版式最准确）。

    双重保险：即使上层判断失误，这里也会再验证一次，WPS 一律拒绝。
    """
    if not word_available():
        raise ConvertError(
            "未检测到微软 Word（WPS 的兼容接口属于收费功能，已拒绝使用）；"
            "将改用内置引擎转换。")
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(src.resolve()))
        doc.SaveAs(str(dst.resolve()), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(False)
    finally:
        if word is not None:
            word.Quit()


# ---------------------------------------------------------------- Markdown / HTML / TXT

def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]


def _read_markdown(text: str) -> list[tuple[int, str]]:
    blocks = []
    for para in _split_paragraphs(text):
        lines = para.split("\n")
        first = lines[0].strip()
        lvl = 0
        if first.startswith("#"):
            lvl = len(first) - len(first.lstrip("#"))
            lines[0] = first.lstrip("#").strip()
        blocks.append((lvl, "\n".join(lines).strip()))
    return blocks


def _read_html(src: Path) -> list[tuple[int, str]]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(read_text_smart(src), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    blocks = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "br"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            blocks.append((int(el.name[1]), text))
        elif el.name == "li":
            blocks.append((0, "• " + text))
        else:
            blocks.append((0, text))
    if not blocks:
        blocks = [(0, soup.get_text("\n", strip=True))]
    return blocks


def _rtf_to_text(src: Path) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError:
        # 无 striprtf 时的粗略兜底
        raw = read_text_smart(src)
        return raw.replace("\\par", "\n")
    return rtf_to_text(read_text_smart(src))


def _blocks_to_html_doc(blocks: list[tuple[int, str]], title: str) -> str:
    parts = []
    for lvl, text in blocks:
        if not text.strip():
            continue
        if 1 <= lvl <= 6:
            parts.append(f"<h{lvl}>{html_escape(text)}</h{lvl}>")
        else:
            parts.append("<p>" + "<br>".join(html_escape(l) for l in text.split("\n")) + "</p>")
    return _wrap_html_doc("\n".join(parts), title)


def _wrap_html_doc(body: str, title: str) -> str:
    return ("<!DOCTYPE html>\n<html lang=\"zh\">\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>{html_escape(title)}</title>\n"
            "<style>body{font-family:'Microsoft YaHei',sans-serif;max-width:800px;"
            "margin:2em auto;line-height:1.7;padding:0 1em;color:#222}</style>\n"
            "</head>\n<body>\n" + body + "\n</body>\n</html>\n")


# ---------------------------------------------------------------- PDF 生成（PyMuPDF Story）

def html_to_pdf(html: str, dst: Path) -> None:
    """HTML -> PDF（自动分页）。中文由 MuPDF 内置字体渲染。"""
    try:
        import pymupdf
    except ImportError as e:
        raise ConvertError("缺少 PyMuPDF 依赖") from e
    if not hasattr(pymupdf, "Story"):
        raise ConvertError("PyMuPDF 版本过低，不支持 HTML 转 PDF")
    try:
        story = pymupdf.Story(html=html)
        writer = pymupdf.DocumentWriter(str(dst))
        mediabox = pymupdf.paper_rect("a4")
        where = mediabox + (43, 43, -43, -43)

        def rectfn(rect_num, filled):
            # 每页都是同样的 A4 版心；由 story.write 负责分页循环
            return mediabox, where, pymupdf.Identity

        try:
            story.write(writer, rectfn)
        except (TypeError, AttributeError):
            # 兼容旧版经典实现
            more = 1
            while more:
                more = story.place(where)
                story.draw(writer)
        close = getattr(story, "close", None)
        if callable(close):
            close()
        writer.close()
    except ConvertError:
        raise
    except Exception as e:
        raise ConvertError(f"生成 PDF 失败：{e}") from e
