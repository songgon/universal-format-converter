"""PDF 工具集：拆分 / 合并 / 加密 / 解密（借鉴 FlyingMouse Format）。"""
from __future__ import annotations

import threading
from pathlib import Path

from .utils import ConvertError

_LOCK = threading.Lock()  # PyMuPDF 文档操作统一串行，稳妥


def split_pdf(src: Path, out_dir: Path, per_page: int = 1,
              overwrite: bool = False) -> list[Path]:
    """把 PDF 按页拆分为多个 PDF（默认每页一个），返回输出文件列表。"""
    import pymupdf

    per_page = max(1, int(per_page))
    outputs: list[Path] = []
    with _LOCK:
        with pymupdf.open(src) as doc:
            n = doc.page_count
            for start in range(0, n, per_page):
                part_no = start // per_page + 1
                tag = f"p{start + 1}" if per_page == 1 else f"part{part_no}"
                dst = _unique_out(src, out_dir, tag, overwrite)
                with pymupdf.open() as new:
                    new.insert_pdf(doc, from_page=start,
                                   to_page=min(start + per_page, n) - 1)
                    new.save(str(dst), deflate=True)
                outputs.append(dst)
    if not outputs:
        raise ConvertError("PDF 没有可拆分的页面")
    return outputs


def merge_pdfs(paths: list[Path], dst: Path) -> None:
    """多个 PDF 按顺序合并为一个。"""
    import pymupdf

    if len(paths) < 2:
        raise ConvertError("合并 PDF 至少需要两个文件")
    with _LOCK:
        with pymupdf.open() as out:
            for p in paths:
                with pymupdf.open(p) as doc:
                    out.insert_pdf(doc)
            out.save(str(dst), deflate=True)


def encrypt_pdf(src: Path, dst: Path, user_pw: str,
                owner_pw: str | None = None) -> None:
    """加密 PDF（打开需要密码）。"""
    import pymupdf

    if not user_pw:
        raise ConvertError("请输入要设置的打开密码")
    with _LOCK:
        with pymupdf.open(src) as doc:
            if doc.needs_pass:
                raise ConvertError("该 PDF 本身已加密，请先解密")
            doc.save(str(dst), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     user_pw=user_pw, owner_pw=owner_pw or user_pw)


def decrypt_pdf(src: Path, dst: Path, password: str = "") -> None:
    """去除 PDF 的打开密码；未加密的文件原样复制（幂等）。"""
    import pymupdf

    with _LOCK:
        with pymupdf.open(src) as doc:
            if doc.needs_pass:
                if not doc.authenticate(password or ""):
                    raise ConvertError("密码错误，无法解密")
                doc.save(str(dst))
            else:
                doc.save(str(dst))  # 未加密：幂等输出


def _unique_out(src: Path, out_dir: Path, tag: str, overwrite: bool) -> Path:
    """拆分输出的命名（复用 safe_output_path 的占位与防覆盖逻辑）。"""
    from .utils import safe_output_path
    return safe_output_path(src, out_dir, "pdf", overwrite, tag=tag)
