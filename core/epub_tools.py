"""EPUB 电子书：生成（EPUB 3）与读取。纯标准库 + BeautifulSoup，无额外依赖。"""
from __future__ import annotations

import re
import time
import uuid
import zipfile
from pathlib import Path

from .utils import ConvertError, html_escape

_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def build_epub(chapters: list[tuple[str, str]], dst: Path, book_title: str) -> None:
    """把章节列表打包为 EPUB 3。chapters: [(标题, 正文HTML)]，正文内允许 <p>/<h*>。"""
    if not chapters:
        raise ConvertError("没有可写入电子书的内容")
    book_id = str(uuid.uuid4())
    modified = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    manifest, spine, nav_lis, files = [], [], [], []
    for i, (title, body) in enumerate(chapters, 1):
        fname = f"chapter{i}.xhtml"
        xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN"><head>'
            f'<meta charset="utf-8"/><title>{html_escape(title)}</title></head>'
            f"<body><h2>{html_escape(title)}</h2>\n{body}\n</body></html>"
        )
        files.append((fname, xhtml))
        manifest.append(f'<item id="c{i}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
        nav_lis.append(f'<li><a href="{fname}">{html_escape(title)}</a></li>')

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="bookid" xml:lang="zh-CN">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>\n'
        f'<dc:title>{html_escape(book_title)}</dc:title>\n'
        '<dc:language>zh-CN</dc:language>\n'
        f'<meta property="dcterms:modified">{modified}</meta>\n'
        '</metadata>\n<manifest>\n'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
        + "\n".join(manifest) + "\n</manifest>\n<spine>\n" + "\n".join(spine) +
        "\n</spine>\n</package>"
    )
    nav = (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops"><head><meta charset="utf-8"/>'
        '<title>目录</title></head><body>'
        '<nav epub:type="toc" id="toc"><h2>目录</h2><ol>'
        + "\n".join(nav_lis) + "</ol></nav></body></html>"
    )

    try:
        with zipfile.ZipFile(dst, "w") as z:
            z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", _CONTAINER)
            z.writestr("OEBPS/content.opf", opf)
            z.writestr("OEBPS/nav.xhtml", nav)
            for fname, content in files:
                z.writestr(f"OEBPS/{fname}", content)
    except OSError as e:
        raise ConvertError(f"写入电子书失败：{e}") from e


def read_epub(src: Path) -> list[tuple[str, str]]:
    """读取 EPUB，返回 [(章节标题, 章节纯文本)]（按文件名自然排序）。"""
    try:
        z = zipfile.ZipFile(src)
    except (zipfile.BadZipFile, OSError) as e:
        raise ConvertError("不是有效的 EPUB 文件") from e
    chapters: list[tuple[str, str]] = []
    with z:
        names = [n for n in z.namelist()
                 if n.lower().endswith((".xhtml", ".html", ".htm"))
                 and "nav" not in Path(n).name.lower()]
        names.sort(key=lambda n: [int(t) if t.isdigit() else t
                                  for t in re.split(r"(\d+)", n)])
        if not names:
            raise ConvertError("EPUB 内没有可读取的章节")
        from bs4 import BeautifulSoup
        for n in names:
            soup = BeautifulSoup(z.read(n), "html.parser")
            text = soup.get_text("\n", strip=True)
            if not text:
                continue
            h = soup.find(["h1", "h2", "h3"])
            title = h.get_text(strip=True) if h else Path(n).stem
            chapters.append((title, text))
    if not chapters:
        raise ConvertError("EPUB 内没有可读取的文本内容")
    return chapters
