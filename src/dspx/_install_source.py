r"""安裝來源解析（PEP 610 `direct_url.json`）＋更新指令組裝。

version / init / self-update 三處共用：讀自身 dist（`dspx`）的 `direct_url.json`
（`importlib.metadata`）判斷安裝來源——
  - vcs_info（git 安裝）→ `{"kind": "git", "commit": <sha>, "url": <repo url>}`
  - dir_info（本地目錄安裝）→ `{"kind": "dir", "path": <解出的本地路徑>}`
  - 檔缺／不可解析（PyPI 常規安裝、舊 pip）→ None（呼叫端靜默省略、不猜、不 crash）
"""

from __future__ import annotations

import json
from urllib.parse import unquote, urlparse

# docspec 公開 repo（git 安裝的更新來源＋init 更新檢查比對對象）。
GIT_REPO = "DennisHuang890331/docspec"
GIT_REMOTE = "git+https://github.com/DennisHuang890331/docspec"


def _file_url_to_path(url: str) -> str:
    """把 dir_info 的 `file://` URL 還原成本地路徑（缺 scheme 時原樣回傳）。"""
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    if parsed.scheme != "file":
        return url
    path = unquote(parsed.path)
    # Windows：`file:///C:/x` → `/C:/x`，剝掉前導斜線。
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return path or url


def read_install_source(dist_name: str = "dspx") -> dict | None:
    """讀自身 dist 的 PEP 610 `direct_url.json`。任何缺失/解析失敗 → None（不拋、不猜）。"""
    try:
        from importlib.metadata import distribution
        raw = distribution(dist_name).read_text("direct_url.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    url = str(data.get("url", ""))
    vcs = data.get("vcs_info")
    if isinstance(vcs, dict) and vcs.get("commit_id"):
        return {"kind": "git", "commit": str(vcs["commit_id"]), "url": url}
    dir_info = data.get("dir_info")
    if isinstance(dir_info, dict):
        return {"kind": "dir", "path": _file_url_to_path(url)}
    return None


def git_reinstall_command() -> str:
    return f"uv tool install --from {GIT_REMOTE} docspec --reinstall --no-cache"


def update_command(source: dict | None) -> str:
    """依安裝來源回傳一行精確更新指令（git→git 重裝；dir/未知→uv tool upgrade）。"""
    if source and source.get("kind") == "git":
        return git_reinstall_command()
    return "uv tool upgrade docspec"


def update_argv(source: dict | None) -> list[str]:
    """update_command 的 argv 版（self-update --run 的 detached 子行程用）。"""
    if source and source.get("kind") == "git":
        return ["uv", "tool", "install", "--from", GIT_REMOTE, "docspec",
                "--reinstall", "--no-cache"]
    return ["uv", "tool", "upgrade", "docspec"]
