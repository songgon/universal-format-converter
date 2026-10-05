import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
cfg = Path(os.environ["APPDATA"]) / "GitHub Desktop" / "config.json"
if not cfg.exists():
    print("NO_CONFIG：桌面版还没有登录账号")
    sys.exit(0)
d = json.loads(cfg.read_text(encoding="utf-8"))
users = d.get("users", [])
if not users:
    print("NO_USERS：桌面版已安装但未登录账号")
    sys.exit(0)
for u in users:
    print("用户名:", u.get("login"))
    print("邮箱:", (u.get("email") or "(未公开)")[:3] + "***")
    print("token 存在:", bool(u.get("token")))

# 桌面版自带 git 的位置
local = Path(os.environ["LOCALAPPDATA"]) / "GitHubDesktop"
gits = list(local.glob("app-*/resources/app/git/cmd/git.exe"))
print("桌面版 git:", gits[0] if gits else "未找到")
