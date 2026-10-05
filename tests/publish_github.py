"""全自动发布：读桌面版凭据 → 准备干净的仓库 → API 建远程仓库 → git 推送。

token 只在内存中使用，绝不写入文件或打印。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\智谱\格式转换器")
GIT_CANDIDATES = list(
    (Path(os.environ["LOCALAPPDATA"]) / "GitHubDesktop").glob("app-*/resources/app/git/cmd/git.exe")
)


def log(msg):
    print(msg, flush=True)


# ---------------- 1) 读取登录凭据（来自 Windows 凭据管理器） ----------------
LOGIN = (ROOT / "tests" / ".gh_user").read_text("utf-8").strip()
TOKEN = (ROOT / "tests" / ".gh_token").read_text("utf-8").strip()
assert TOKEN, "未获取到 token"
log(f"✓ 账号: {LOGIN}")

git_exe = str(GIT_CANDIDATES[0]) if GIT_CANDIDATES else "git"
log(f"✓ git: {git_exe}")

# ---------------- 2) 仓库内容清理 ----------------
# 2a) .gitignore
(ROOT / ".gitignore").write_text(
    """.venv/
绿色版/
runtime_staging/
tools/ffmpeg/
tools/pandoc/
__pycache__/
*.pyc
*.bak
dist/
build/
*.spec
tests/render/
nul
""", encoding="utf-8")

# 2b) README 公开化：去掉本机绝对路径
readme = ROOT / "README.md"
md = readme.read_text(encoding="utf-8")
md = md.replace(r"D:\智谱\格式转换器", "项目文件夹").replace(r"D:\智谱", "项目文件夹")
readme.write_text(md, encoding="utf-8")
log("✓ README 已通用化")

# ---------------- 3) git 初始化与提交 ----------------
env = os.environ.copy()
env["GIT_CONFIG_GLOBAL"] = os.devnull  # 不污染全局配置


def git(*args, **kw):
    return subprocess.run([git_exe, *args], cwd=ROOT, capture_output=True,
                          text=True, errors="replace", env=env, **kw)


if not (ROOT / ".git").exists():
    r = git("init", "-b", "main")
    assert r.returncode == 0, r.stderr
git("config", "user.name", LOGIN)
git("config", "user.email", f"{LOGIN}@users.noreply.github.com")
git("add", "-A")
r = git("commit", "-m", "万能格式转换器 v1.6：多引擎格式转换（图片/文档/数据/音视频/PDF工具/EPUB）")
if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
    log("✗ commit 失败: " + (r.stderr or r.stdout)[:300])
    sys.exit(1)
log("✓ 本地提交完成")

# ---------------- 4) 创建远程仓库（私密） ----------------
REPO = "universal-format-converter"


def api(method, path, payload=None):
    req = urllib.request.Request(
        f"https://api.github.com{path}", method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
                 "User-Agent": LOGIN})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


code, data = api("GET", f"/repos/{LOGIN}/{REPO}")
if code == 200:
    log("✓ 远程仓库已存在，直接推送")
else:
    code, data = api("POST", "/user/repos",
                     {"name": REPO, "private": True,
                      "description": "本地离线的多引擎文件格式转换器：图片/文档/数据/音视频/PDF 工具/EPUB，内嵌 LibreOffice·Pandoc·FFmpeg 思路的多引擎协同"})
    if code not in (200, 201):
        log(f"✗ 建仓库失败 {code}: {data}")
        sys.exit(1)
    log(f"✓ 远程仓库已创建（私密）: {data['html_url']}")

# ---------------- 5) 推送 ----------------
b64 = base64.b64encode(f"{LOGIN}:{TOKEN}".encode()).decode()
r = git("-c", f"http.extraHeader=Authorization: Basic {b64}",
        "remote", "add", "origin", f"https://github.com/{LOGIN}/{REPO}.git")
r = git("remote", "set-url", "origin", f"https://github.com/{LOGIN}/{REPO}.git")
r = git("-c", f"http.extraHeader=Authorization: Basic {b64}",
        "push", "-u", "origin", "main")
if r.returncode != 0:
    log("✗ 推送失败: " + (r.stderr or r.stdout)[-500:])
    sys.exit(1)
log("✓ 推送成功！")
log(f"🎉 仓库地址: https://github.com/{LOGIN}/{REPO}")
