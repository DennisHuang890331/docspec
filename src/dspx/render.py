"""render：把末節散文確定性組裝進 docs/<article>/_latest.md。

★薄引擎鐵律：引擎不寫一個字。散文由 draft（agent）盲渲染、直接寫進 _latest.md 各節；
render 只做確定性的事——讓章節骨架（標題/順序/層級）跟 outline 對齊，保留每節已寫散文，
並記下「有散文的節」的當下源 hash（staleness 用）。

章節邊界＝隱形標記 `<!-- dspx:section <id> -->`（讀者看不到；render 靠它定位每節）。
publish 凍結時會完全剝除這些標記。
"""

from __future__ import annotations

import hashlib
import re

from dspx.frontmatter import parse_frontmatter, render_frontmatter
from dspx.layout import Layout
from dspx.model import Leaf, ancestor_brief_fingerprint, decision_index, deps_fingerprint

MARKER_RE = re.compile(r"^<!--\s*dspx:section\s+(\S+)\s*-->\s*$")


def prose_hash(body: str) -> str:
    """一段散文本身的指紋（diff 偵測手改交付物用）。"""
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:16]


def section_marker(section: str) -> str:
    return f"<!-- dspx:section {section} -->"


def _depth(article: str, section: str) -> int:
    """文章內深度（article 之後的路徑段數）。根節(section==article)＝0。"""
    return len([p for p in section.split("/") if p]) - 1


def _order_key(article: str, section: str, order_by_section: dict[str, float]):
    """沿路徑逐層 (order, name) 當排序鍵，做 outline order 拓樸。"""
    parts = [p for p in section.split("/") if p]
    key = []
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        key.append((order_by_section.get(prefix, 0.0), parts[i - 1]))
    return key


def parse_section_bodies(text: str) -> dict[str, str]:
    """從現有 _latest.md 解析每節已寫散文（去掉 marker 與其後第一行標題）。"""
    _, body = parse_frontmatter(text)
    lines = body.split("\n")
    bodies: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush():
        if current is None:
            return
        block = buf[:]
        # 去掉前導空行 + 一行 markdown 標題（render 會重生標題）
        while block and not block[0].strip():
            block.pop(0)
        if block and re.match(r"^#{1,6}\s", block[0]):
            block.pop(0)
        bodies[current] = "\n".join(block).strip()

    for line in lines:
        m = MARKER_RE.match(line)
        if m:
            flush()
            current = m.group(1)
            buf = []
        elif current is not None:
            buf.append(line)
    flush()
    return bodies


def render_article(layout: Layout, leaves: list[Leaf], article: str) -> dict:
    """同步 docs/<article>/_latest.md 骨架；保留已寫散文；回報統計。

    回傳 {sections, drafted, written_path}。
    """
    by_section = {lf.section: lf for lf in leaves}   # 全專案，供祖先 brief 查找
    dindex = decision_index(leaves)                  # 全專案決策索引，供 deps 指紋
    art_leaves = [lf for lf in leaves if lf.article == article]
    order_by_section = {
        lf.section: lf.order for lf in art_leaves if lf.concept is not None
    }
    art_leaves.sort(key=lambda lf: _order_key(article, lf.section, order_by_section))

    latest = layout.docs_latest(article)
    existing_bodies: dict[str, str] = {}
    if latest.is_file():
        existing_bodies = parse_section_bodies(latest.read_text(encoding="utf-8"))

    # 根節（section==article）＝文章標題＋全域導言；存在就由它當 `#`，
    # 否則退回印一行純標題（導言由人/文類決定，render 不強制生）。
    has_root = any(lf.section == article for lf in art_leaves)
    out: list[str] = [] if has_root else [f"# {article}", ""]
    hashes: dict[str, str] = {}
    drafted = 0
    for lf in art_leaves:
        depth = _depth(article, lf.section)
        heading = "#" * (depth + 1) + " " + lf.title
        body = existing_bodies.get(lf.section, "").strip()
        out.append(section_marker(lf.section))
        out.append(heading)
        out.append("")
        if body:
            out.append(body)
            out.append("")
            # 有散文才記指紋：own=自己源、anc=祖先 brief、deps=realizes 共享真相、
            # prose=散文本身（diff 偵測手改）
            rec = {
                "own": lf.source_hash(),
                "anc": ancestor_brief_fingerprint(lf.section, by_section),
                "deps": deps_fingerprint(lf, dindex),
                "prose": prose_hash(body),
            }
            hashes[lf.section] = rec
            drafted += 1
        else:
            out.append("")

    # 保留現有 version（若有），render 不升版（升版是 publish 的事）。
    # 版本＝semver 字串；未發行的骨架預設 "0.0.0"（佔位、非真版）。
    version = "0.0.0"
    if latest.is_file():
        meta, _ = parse_frontmatter(latest.read_text(encoding="utf-8"))
        existing = meta.get("version")
        if existing not in (None, "", 0):
            version = existing

    meta = {"article": article, "version": version, "sections": hashes}
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(render_frontmatter(meta, "\n".join(out)), encoding="utf-8")

    return {
        "sections": [lf.section for lf in art_leaves],
        "drafted": drafted,
        "written_path": str(latest),
    }


def detect_drift(layout: Layout, article: str) -> list[dict]:
    """偵測交付物被手改：_latest 某節散文 ≠ 上次 render 記的 prose 指紋。

    回傳每個漂移節 {section, recorded, current}。沒 _latest 或沒記指紋 → 跳過。
    純確定性：只報「散文被改過」，不判斷改得對不對（那是 agent 的事）。
    """
    latest = layout.docs_latest(article)
    if not latest.is_file():
        return []
    text = latest.read_text(encoding="utf-8")
    meta, _ = parse_frontmatter(text)
    recorded = meta.get("sections") or {}
    bodies = parse_section_bodies(text)
    drift = []
    for section, body in bodies.items():
        rec = recorded.get(section)
        rec_prose = rec.get("prose") if isinstance(rec, dict) else None
        if rec_prose is None:
            continue                      # 沒基準（未撰寫/舊格式）→ 不算漂移
        if prose_hash(body) != rec_prose:
            drift.append({"section": section, "recorded": rec_prose,
                          "current": prose_hash(body)})
    return drift


def strip_markers(text: str) -> str:
    """移除所有隱形 section 標記，保留內容（publish 凍結快照用）。"""
    return "\n".join(
        line for line in text.split("\n")
        if not MARKER_RE.match(line)
    )
