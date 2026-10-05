import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import win32cred  # noqa: E402

cred = win32cred.CredRead("GitHub - https://api.github.com/songgon", 1)  # CRED_TYPE_GENERIC
blob = cred.get("CredentialBlob") or b""
# Desktop 以 UTF-8 存储 ASCII token；先试 utf-8 并校验可打印性
tok = ""
for enc in ("utf-8", "utf-16-le"):
    try:
        text = blob.decode(enc)
    except UnicodeDecodeError:
        continue
    if text.isprintable() and text == text.strip():
        tok = text.strip()
        break
print("凭据长度:", len(tok))
print("token 非空:", bool(tok), "| 前缀:", tok[:4] + "***" if tok else "-")

# 把凭据写入临时文件供发布脚本使用（不打印）
from pathlib import Path
p = Path(r"D:\智谱\格式转换器\tests\.gh_token")
if p.exists():
    os.system(f"attrib -h {str(p)!s}")
    p.unlink(missing_ok=True)
p.write_text(tok, encoding="utf-8")
os_p = p.with_name(".gh_user")
os_p.write_text("songgon", encoding="utf-8")
import os
os.system("attrib +h " + str(p).replace("/", "\\"))
print("凭据已安全传递给发布脚本")
