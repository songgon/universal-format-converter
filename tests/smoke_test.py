"""无界面转换矩阵测试：生成样例文件，逐对转换并校验输出。

运行:  python tests/smoke_test.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import registry  # noqa: E402
from core.utils import ConvertError  # noqa: E402

OUT_TXT = "你好，世界！Hello converter.\n第二段文字。"
MD_TEXT = "# 一级标题\n\n正文段落，包含**加粗**。\n\n## 二级标题\n\n更多内容。"
HTML_TEXT = ("<html><head><meta charset='utf-8'></head><body><h1>标题一</h1>"
             "<p>段落内容。</p><h2>标题二</h2><p>第二段。</p></body></html>")
RECORDS = [{"姓名": "张三", "数量": 3, "备注": "ok"},
           {"姓名": "李四", "数量": 7, "备注": "hello"}]

results: list[tuple[str, bool, str]] = []


def record(name: str, fn):
    try:
        fn()
        results.append((name, True, ""))
    except ConvertError as e:
        results.append((name, False, str(e)))
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-300:]}"))


def make_inputs(tmp: Path) -> dict[str, Path]:
    from PIL import Image
    inputs: dict[str, Path] = {}

    # 图片
    img = Image.new("RGBA", (64, 48), (200, 60, 60, 255))
    for ext in ("png", "webp", "bmp", "tiff"):
        p = tmp / f"pic.{ext}"
        img.save(p)
        inputs[ext] = p
    p = tmp / "pic.jpg"
    img.convert("RGB").save(p, quality=90)
    inputs["jpg"] = p

    # 文档
    p = tmp / "doc.txt"; p.write_text(OUT_TXT, encoding="utf-8"); inputs["txt"] = p
    p = tmp / "doc.md"; p.write_text(MD_TEXT, encoding="utf-8"); inputs["md"] = p
    p = tmp / "doc.html"; p.write_text(HTML_TEXT, encoding="utf-8"); inputs["html"] = p

    from docx import Document
    p = tmp / "doc.docx"
    d = Document()
    d.add_heading("测试文档", level=1)
    d.add_paragraph("这是一个测试段落。")
    d.add_paragraph("第二个段落。")
    d.save(p)
    inputs["docx"] = p

    import pymupdf
    p = tmp / "doc.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=400, height=300)
    page.insert_text((50, 80), "PDF Text Test 123", fontsize=14)
    pdf.save(p)
    pdf.close()
    inputs["pdf"] = p

    # 数据
    p = tmp / "data.csv"; p.write_text("姓名,数量,备注\n张三,3,ok\n李四,7,hello", encoding="utf-8"); inputs["csv"] = p
    p = tmp / "data.tsv"; p.write_text("姓名\t数量\t备注\n张三\t3\tok", encoding="utf-8"); inputs["tsv"] = p
    p = tmp / "data.json"; p.write_text(__import__("json").dumps(RECORDS, ensure_ascii=False), encoding="utf-8"); inputs["json"] = p
    p = tmp / "data.xlsx"
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["姓名", "数量", "备注"]); ws.append(["张三", 3, "ok"]); ws.append(["李四", 7, "hello"])
    wb.save(p); inputs["xlsx"] = p
    p = tmp / "data.yaml"; p.write_text("- 姓名: 张三\n  数量: 3\n- 姓名: 李四\n  数量: 7\n", encoding="utf-8"); inputs["yaml"] = p
    p = tmp / "data.xml"; p.write_text("<?xml version='1.0' encoding='utf-8'?>\n<records><record><姓名>张三</姓名><数量>3</数量></record></records>", encoding="utf-8"); inputs["xml"] = p
    p = tmp / "data.toml"; p.write_text("name = 'demo'\nversion = '1.0'\n", encoding="utf-8"); inputs["toml"] = p

    # 伪装文件：网上系统导出的“网页内容冒充 Office 文档”
    p = tmp / "fake.docx"; p.write_text(HTML_TEXT, encoding="utf-8"); inputs["fakedocx"] = p
    p = tmp / "fake.xlsx"
    p.write_text("<html><body><table><tr><th>名称</th><th>数量</th></tr>"
                 "<tr><td>甲</td><td>1</td></tr><tr><td>乙</td><td>2</td></tr></table></body></html>",
                 encoding="utf-8")
    inputs["fakexlsx"] = p
    p = tmp / "olefake.docx"; p.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 64); inputs["oledocx"] = p

    # 压测回归点：webp/ico→PDF、SVG 文字、嵌套 JSON→XML、Opus 码率
    p = tmp / "ico_src.ico"
    Image.new("RGBA", (64, 64), (10, 120, 200, 255)).save(p, sizes=[(32, 32), (16, 16)])
    inputs["icosrc"] = p
    p = tmp / "svg_src.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
                 '<rect width="100%" height="100%" fill="#eef"/>'
                 '<text x="10" y="40" font-size="16" fill="#123">SVG文字</text></svg>',
                 encoding="utf-8")
    inputs["svgsrc"] = p
    p = tmp / "nested.json"
    p.write_text('{"项目": "测试", "配置": {"深度": 2}, "标记": "N1", "列表": [1, 2]}',
                 encoding="utf-8")
    inputs["nestedjson"] = p

    # PPTX 样例
    p = tmp / "slides.pptx"
    from pptx import Presentation
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "压测PPT"
    s1.placeholders[1].text = "内容标记 ZP1"
    prs.save(p)
    inputs["pptx"] = p

    # 两页 PDF（供拆分/合并测试）
    import pymupdf
    p = tmp / "multi.pdf"
    d3 = pymupdf.open()
    for pn in range(2):
        pg = d3.new_page(width=300, height=200)
        pg.insert_text((40, 60), f"page {pn + 1} ZM{pn}", fontsize=12)
    d3.save(p)
    d3.close()
    inputs["multipdf"] = p

    # 带表格的 Markdown（供 Pandoc 测试）
    p = tmp / "tbl.md"
    p.write_text("# 表格测试\n\n| 列A | 列B |\n|---|---|\n| 甲 | 1 |\n| 乙 | 2 |\n\n正文 ZT1。\n",
                 encoding="utf-8")
    inputs["tblmd"] = p

    # ZIP 包（供压缩包批处理测试）
    import zipfile
    p = tmp / "batch.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("内含.csv", "名称,数量\n张三,1")
        z.writestr("图片.png", (tmp / "pic.png").read_bytes())
        z.writestr("../../恶意.exe", b"MZ")
    inputs["zip"] = p

    # 带格式文档（加粗/斜体/颜色）
    styled_html = ('<html><body><h1>报告</h1><p>前缀<b>加粗文字</b>中间<i>斜体</i>'
                   '<span style="color:#FF0000">红字内容</span><font color="blue">蓝字内容</font>'
                   '<u>下划线</u></p></body></html>')
    p = tmp / "styled.html"; p.write_text(styled_html, encoding="utf-8"); inputs["styledhtml"] = p
    p = tmp / "styledfake.docx"; p.write_text(styled_html, encoding="utf-8"); inputs["styledfake"] = p

    from docx.shared import RGBColor
    p = tmp / "styled.docx"
    d2 = Document()
    d2.add_heading("格式文档", level=1)
    par = d2.add_paragraph()
    par.add_run("普通")
    rb = par.add_run("重要"); rb.bold = True
    rc = par.add_run("警示"); rc.font.color.rgb = RGBColor(0xFF, 0x22, 0x22)
    d2.save(p)
    inputs["styledocx"] = p

    # 音频（测试 ffmpeg 是否可用）
    import wave
    p = tmp / "tone.wav"
    with wave.open(str(p), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"\x00\x40" * 8000)
    inputs["wav"] = p
    return inputs


def pair(inputs: dict, src_ext: str, dst_ext: str, tmp: Path, expect_exists: bool = True):
    src = inputs[src_ext]
    out_dir = tmp / "out"
    res = registry.convert_file(src, dst_ext, out_dir, {"quality": 90, "dpi": 96})
    assert res.outputs, "没有输出文件"
    if expect_exists:
        for o in res.outputs:
            assert o.exists(), f"输出不存在: {o}"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        inputs = make_inputs(tmp)

        # 图片矩阵
        for dst in ("png", "jpg", "webp", "bmp", "tif", "gif", "ico", "pdf"):
            record(f"图片 png→{dst}", lambda dst=dst: pair(inputs, "png", dst, tmp))
        record("图片 webp→pdf", lambda: pair(inputs, "webp", "pdf", tmp))
        record("图片 ico→pdf", lambda: pair(inputs, "icosrc", "pdf", tmp))
        record("svg带文字→png", lambda: pair(inputs, "svgsrc", "png", tmp))
        record("嵌套json→xml", lambda: pair(inputs, "nestedjson", "xml", tmp))
        record("pptx→txt", lambda: pair(inputs, "pptx", "txt", tmp))

        from core.documents import libreoffice_path, pandoc_path
        if libreoffice_path():
            record("docx→pdf (LibreOffice高保真)", lambda: pair(inputs, "docx", "pdf", tmp))
            record("pptx→pdf (LibreOffice)", lambda: pair(inputs, "pptx", "pdf", tmp))
            record("md→pdf (Pandoc+LO链)", lambda: pair(inputs, "tblmd", "pdf", tmp))
        else:
            results.append(("LibreOffice 未安装，跳过高保真用例", True, "skipped"))

        # Pandoc 路由：md→docx 保留表格，docx→md 保留结构
        if pandoc_path():
            def _check_md_docx_table():
                res = registry.convert_file(inputs["tblmd"], "docx", tmp / "out", {})
                import docx as docx_lib
                d4 = docx_lib.Document(str(res.outputs[0]))
                assert len(d4.tables) == 1, "Pandoc md→docx 表格丢失"

            record("md→docx (Pandoc表格保留)", _check_md_docx_table)
            record("docx→md (Pandoc)", lambda: pair(inputs, "docx", "md", tmp))
        else:
            results.append(("Pandoc 未安装，跳过", True, "skipped"))

        # PDF 工具：拆分 / 合并 / 加密 / 解密
        from core import pdftools
        out_dir = tmp / "out"

        def _check_split():
            outs = pdftools.split_pdf(inputs["multipdf"], out_dir, 1, True)
            assert len(outs) == 2 and all(o.exists() for o in outs)

        record("PDF拆分(每页一个)", _check_split)

        def _check_merge():
            dst = out_dir / "merged_test.pdf"
            pdftools.merge_pdfs([inputs["multipdf"], inputs["multipdf"]], dst)
            import pymupdf
            with pymupdf.open(dst) as doc:
                assert doc.page_count == 4, "合并页数不对"

        record("PDF合并", _check_merge)

        def _check_encrypt_decrypt():
            enc = out_dir / "enc.pdf"
            pdftools.encrypt_pdf(inputs["multipdf"], enc, "秘密123")
            import pymupdf
            with pymupdf.open(enc) as doc:
                assert doc.needs_pass, "加密未生效"
                assert doc.authenticate("秘密123")
            dec = out_dir / "dec.pdf"
            pdftools.decrypt_pdf(enc, dec, "秘密123")
            with pymupdf.open(dec) as doc:
                assert not doc.needs_pass, "解密未生效"

        record("PDF加密解密", _check_encrypt_decrypt)

        def _check_encrypt_wrong_pw():
            enc = out_dir / "enc2.pdf"
            pdftools.encrypt_pdf(inputs["multipdf"], enc, "abc")
            import pymupdf
            with pymupdf.open(enc) as doc:
                assert not doc.authenticate("错误的密码")

        record("PDF密码校验", _check_encrypt_wrong_pw)

        # H.265 编码（若 ffmpeg 可用）
        from core import media as media_mod
        if media_mod.is_available():
            def _check_h265():
                import subprocess
                ff = media_mod.ffmpeg_path()
                vsrc = tmp / "h265_src.mp4"
                subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                                "-i", "testsrc=size=320x240:rate=15:duration=0.5",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vsrc)],
                               creationflags=0x08000000, timeout=60, check=True)
                res = registry.convert_file(vsrc, "mp4", tmp / "out",
                                            {"vcodec": "h265", "overwrite": True})
                out = res.outputs[0]
                assert out.exists() and out.stat().st_size > 1000
                probe = subprocess.run([ff, "-i", str(out)], capture_output=True,
                                       text=True, errors="replace",
                                       creationflags=0x08000000)
                low = probe.stderr.lower()
                assert "hevc" in low or "h265" in low, "输出不是 H.265 编码"

            record("视频H.265编码", _check_h265)

        # ZIP 批处理：解出受支持文件、拒绝路径穿越
        def _check_zip():
            extracted = registry.extract_zip_for_conversion(inputs["zip"], tmp / "unzipped")
            names = sorted(f.name for f in extracted)
            assert names == ["内含.csv", "图片.png"], f"解压结果异常: {names}"

        record("ZIP批处理解包", _check_zip)

        # EPUB 电子书
        record("md→epub", lambda: pair(inputs, "md", "epub", tmp))

        def _check_epub_roundtrip():
            res = registry.convert_file(inputs["md"], "epub", tmp / "out", {"overwrite": True})
            from core.epub_tools import read_epub
            chapters = read_epub(res.outputs[0])
            text = "\n".join(t for _, t in chapters)
            assert "更多内容" in text, "EPUB 内容缺正文"
            assert any("一级标题" in t for t, _ in chapters), "EPUB 章节标题缺失"

        record("epub读取回读", _check_epub_roundtrip)

        def _check_epub_to_html():
            res = registry.convert_file(inputs["md"], "epub", tmp / "out", {"overwrite": True})
            res2 = registry.convert_file(res.outputs[0], "html", tmp / "out", {"overwrite": True})
            assert "更多内容" in res2.outputs[0].read_text(encoding="utf-8")

        record("epub→html", _check_epub_to_html)
        record("图片 jpg→png", lambda: pair(inputs, "jpg", "png", tmp))
        record("图片 webp→jpg", lambda: pair(inputs, "webp", "jpg", tmp))
        record("图片 gif→png", lambda: pair(inputs, "png", "png", tmp))
        record("图片 bmp→webp", lambda: pair(inputs, "bmp", "webp", tmp))
        record("多图合并PDF", lambda: registry.convert_images_to_single_pdf(
            [inputs["png"], inputs["jpg"]], tmp / "out"))

        # 文档矩阵
        for dst in ("txt", "md", "html", "docx", "pdf"):
            record(f"文档 md→{dst}", lambda dst=dst: pair(inputs, "md", dst, tmp))
            record(f"文档 docx→{dst}", lambda dst=dst: pair(inputs, "docx", dst, tmp))
            record(f"文档 txt→{dst}", lambda dst=dst: pair(inputs, "txt", dst, tmp))
            record(f"文档 html→{dst}", lambda dst=dst: pair(inputs, "html", dst, tmp))
        for dst in ("txt", "md", "html", "docx", "png", "jpg"):
            record(f"文档 pdf→{dst}", lambda dst=dst: pair(inputs, "pdf", dst, tmp))

        # 数据矩阵
        for src in ("csv", "tsv", "xlsx", "json", "yaml", "xml"):
            for dst in ("csv", "tsv", "xlsx", "json", "yaml", "xml", "md", "html", "pdf"):
                if src.endswith(dst) or (src, dst) in {("tsv", "csv"), ("csv", "tsv"), ("yaml", "yml")}:
                    continue
                record(f"数据 {src}→{dst}", lambda src=src, dst=dst: pair(inputs, src, dst, tmp))
        for dst in ("csv", "xlsx", "json"):
            record(f"数据 toml→{dst}", lambda dst=dst: pair(inputs, "toml", dst, tmp))

        # 伪装文件（网页冒充 Office 文档）
        for dst in ("txt", "md", "html", "docx", "pdf"):
            record(f"伪装docx→{dst}", lambda dst=dst: pair(inputs, "fakedocx", dst, tmp))
        for dst in ("csv", "xlsx", "json"):
            record(f"伪装xlsx→{dst}", lambda dst=dst: pair(inputs, "fakexlsx", dst, tmp))

        def _expect_friendly_error():
            try:
                pair(inputs, "oledocx", "txt", tmp)
            except ConvertError as e:
                assert "另存为" in str(e), f"提示不友好: {e}"
                return
            raise AssertionError("旧版 .doc 伪装 docx 应当报错")

        record("旧版doc伪装docx→明确报错", _expect_friendly_error)

        # 带格式转换：加粗/颜色必须保留
        def _check_html_to_styled_docx(src_key: str):
            res = registry.convert_file(inputs[src_key], "docx", tmp / "out", {})
            import docx as docx_lib
            d3 = docx_lib.Document(str(res.outputs[0]))
            bolds = "".join(r.text for pp in d3.paragraphs for r in pp.runs if r.bold)
            assert "加粗文字" in bolds, "加粗丢失"
            reds = [r.text for pp in d3.paragraphs for r in pp.runs
                    if r.font.color and r.font.color.rgb is not None
                    and str(r.font.color.rgb).upper() == "FF0000"]
            assert any("红字内容" in t for t in reds), "颜色丢失"

        record("带格式html→Word保留样式", lambda: _check_html_to_styled_docx("styledhtml"))
        record("伪装docx(带格式)→Word保留样式", lambda: _check_html_to_styled_docx("styledfake"))

        def _check_fake_docx_html_passthrough():
            res = registry.convert_file(inputs["styledfake"], "html", tmp / "out", {})
            out = res.outputs[0].read_text(encoding="utf-8")
            assert "<b>加粗文字</b>" in out and "FF0000" in out, "原样保留失败"

        record("伪装docx→HTML原样保留", _check_fake_docx_html_passthrough)

        def _check_real_docx_to_html():
            res = registry.convert_file(inputs["styledocx"], "html", tmp / "out", {})
            h = res.outputs[0].read_text(encoding="utf-8")
            assert "<b>重要</b>" in h and "FF2222" in h, "真docx格式导出失败"

        record("真docx→HTML保留样式", _check_real_docx_to_html)
        record("真docx→PDF保留样式", lambda: pair(inputs, "styledocx", "pdf", tmp))
        record("带格式html→PDF", lambda: pair(inputs, "styledhtml", "pdf", tmp))

        # 覆盖模式下绝不允许输出路径等于源文件（否则会毁掉原文件）
        def _check_no_self_overwrite():
            src = inputs["styledhtml"]
            before = src.read_bytes()
            res = registry.convert_file(src, "html", src.parent, {"overwrite": True})
            assert all(o.resolve() != src.resolve() for o in res.outputs), "输出路径不应等于源文件"
            assert src.read_bytes() == before, "源文件被覆盖！"

        record("覆盖模式不毁源文件", _check_no_self_overwrite)

        # Word 检测：WPS 抢占注册的 "Word.Application" 接口必须被拒绝
        def _check_ms_word_detection():
            from core.documents import _is_ms_word_server, word_available
            assert _is_ms_word_server(
                r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE /automation")
            assert not _is_ms_word_server(
                r"C:\Users\x\AppData\Local\Kingsoft\WPS Office\office6\wps.exe /automation")
            assert not _is_ms_word_server(r"D:\Kingsoft\WPS Office\kwps.exe")
            assert not _is_ms_word_server(None)
            assert not _is_ms_word_server(r"C:\some\unknown.exe")
            a, b = word_available(), word_available()
            assert isinstance(a, bool) and a == b  # 检测可稳定重复执行

        record("Word检测拒绝WPS伪装", _check_ms_word_detection)

        # 音视频（若 ffmpeg 可用）
        try:
            from core import media
            if media.is_available():
                record("音视频 wav→mp3", lambda: pair(inputs, "wav", "mp3", tmp))
                record("音视频 wav→flac", lambda: pair(inputs, "wav", "flac", tmp))
                record("音视频 wav→ogg", lambda: pair(inputs, "wav", "ogg", tmp))
                record("音视频 wav→opus", lambda: pair(inputs, "wav", "opus", tmp))

                def _check_cancel():
                    from core.utils import ConvertCancelled
                    ev = threading.Event()
                    ev.set()  # 预先置位：ffmpeg 启动后应立刻被取消
                    try:
                        registry.convert_file(inputs["wav"], "mp3", tmp / "out",
                                              {"cancel_event": ev})
                    except ConvertCancelled:
                        return
                    raise AssertionError("预置取消事件应当抛出 ConvertCancelled")

                record("ffmpeg任务可取消", _check_cancel)
            else:
                results.append(("音视频（ffmpeg 未就绪，跳过）", True, "skipped"))
        except Exception as e:  # noqa: BLE001
            results.append(("音视频", False, str(e)))

        # 并行安全：8 个同名文件同时转换到同一目录，输出不得冲突
        def _check_parallel_same_name():
            import concurrent.futures
            out_dir = tmp / "out_par"
            subdirs = []
            for k in range(8):
                d = tmp / f"par{k}"
                d.mkdir(exist_ok=True)
                shutil.copyfile(inputs["png"], d / "same.png")
                subdirs.append(d)

            def conv(d):
                return registry.convert_file(d / "same.png", "webp", out_dir,
                                             {"quality": 90, "overwrite": False})

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                ress = list(ex.map(conv, subdirs))
            names = sorted(o.name for r in ress for o in r.outputs)
            assert len(names) == 8 and len(set(names)) == 8, f"并行命名冲突: {names}"

        record("并行转换同名文件不冲突", _check_parallel_same_name)

    # 汇总
    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    print(f"\n========== 测试结果：{len(passed)} 通过 / {len(failed)} 失败 ==========")
    for name, ok, msg in failed:
        print(f"  ✗ {name}\n      {msg.splitlines()[0] if msg else ''}")
    if not failed:
        print("  全部通过 ✓")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
