"""共用測試夾具（section 模型）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture(autouse=True)
def _isolate_codex_home(tmp_path, monkeypatch):
    """codex command 寫到 $CODEX_HOME（預設 ~/.codex）；測試一律導向 tmp，別污染真 home。"""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "_codex_home"))


@pytest.fixture
def make_project(tmp_path):
    """建立含中文路徑的最小 docspec 專案，回傳 planning home。"""

    def _make(config_text: str = "language: zh-TW\ndocs_layout: per-article\n") -> Path:
        home = tmp_path / "中文專案" / "docspec"
        home.mkdir(parents=True)
        (home / "config.yaml").write_text(config_text, encoding="utf-8")
        return home

    return _make


@pytest.fixture
def write_leaf():
    """在 corpus/ 下寫一個末節（concept 必給，其餘可選）。"""

    def _write(home: Path, section: str, *, concept: dict,
               decisions: list[dict] | None = None,
               history: list[dict] | None = None,
               material: str | None = None,
               develop: str | None = None) -> Path:
        leaf = home / "corpus"
        for part in section.split("/"):
            leaf = leaf / part
        leaf.mkdir(parents=True, exist_ok=True)
        # 補齊 schema 必填欄預設，讓最小 fixture 也通過 check 的欄位驗證
        full = {"status": "draft", "concept": section, "brief": {}, **concept}
        (leaf / "concept.yaml").write_text(
            yaml.safe_dump(full, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if decisions is not None:
            (leaf / "decisions.yaml").write_text(
                yaml.safe_dump({"entries": decisions}, allow_unicode=True, sort_keys=False),
                encoding="utf-8")
        if history is not None:
            (leaf / "history.yaml").write_text(
                yaml.safe_dump({"entries": history}, allow_unicode=True, sort_keys=False),
                encoding="utf-8")
            # history.md＝可選散文細節（乾淨 ## <id>，純 id 不帶標題；非硬綁）
            md = "# history\n\n" + "".join(
                f"## {e.get('id')}\n（退場理由：{e.get('statement', '')}）\n\n"
                for e in history if e.get("id"))
            (leaf / "history.md").write_text(md, encoding="utf-8")
        if material is not None:
            (leaf / "material.md").write_text(material, encoding="utf-8")
        if develop is not None:
            (leaf / "develop.md").write_text(develop, encoding="utf-8")
        return leaf

    return _write
