"""万能格式转换器 - 命令行工具（供脚本 / AI Agent 调用）。

用法示例:
  python convert_cli.py 图片.png --to pdf
  python convert_cli.py *.docx --to pdf --out D:\输出 --quality high
  python convert_cli.py 加密前.pdf --to encrypt --password 123456
  python convert_cli.py 表格.csv --to xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import registry  # noqa: E402
from core.utils import ConvertError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="万能格式转换器 CLI")
    parser.add_argument("files", nargs="+", help="要转换的文件（可多个）")
    parser.add_argument("--to", required=True, help="目标格式，如 pdf / png / docx / split / encrypt")
    parser.add_argument("--out", default="", help="输出文件夹（默认保存到原文件夹）")
    parser.add_argument("--quality", default="max", choices=["max", "high", "normal"],
                        help="输出品质档位（默认 max）")
    parser.add_argument("--password", default="", help="PDF 加密/解密密码")
    parser.add_argument("--split-pages", type=int, default=1, help="PDF 拆分时每 N 页一个文件")
    parser.add_argument("--overwrite", action="store_true", help="覆盖同名文件")
    args = parser.parse_args()

    files = [Path(f) for f in args.files]
    from core.registry import QUALITY_PRESETS
    options = dict(QUALITY_PRESETS.get(args.quality, QUALITY_PRESETS["max"]))
    options.update({"overwrite": args.overwrite,
                    "pdf_password": args.password,
                    "split_pages": args.split_pages})
    out_dir = Path(args.out) if args.out else None

    ok = bad = 0
    for f in files:
        if not f.is_file():
            print(f"✗ {f}：文件不存在")
            bad += 1
            continue
        try:
            res = registry.convert_file(f, args.to.lower(), out_dir, options)
            for o in res.outputs:
                print(f"✓ {f.name} → {o}")
            ok += 1
        except ConvertError as e:
            print(f"✗ {f.name}：{e}")
            bad += 1
        except Exception as e:
            print(f"✗ {f.name}：内部错误 {e}")
            bad += 1
    print(f"完成：成功 {ok}，失败 {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
