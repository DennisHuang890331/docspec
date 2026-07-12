"""docs_layout：per-article（預設）vs flat（平鋪＋archive/）。"""

from __future__ import annotations

import pytest

from dspx.engine.layout import Layout, next_version, parse_semver


def test_per_article_paths(tmp_path):
    home = tmp_path / "docspec"
    lay = Layout(home, "per-article")
    assert lay.docs_latest("guide") == home.parent / "docs" / "guide" / "_latest.md"
    assert lay.docs_snapshot("guide", "1.2.0") == home.parent / "docs" / "guide" / "archive" / "v1.2.0.md"


def test_flat_paths(tmp_path):
    home = tmp_path / "docspec"
    lay = Layout(home, "flat")
    assert lay.docs_latest("guide") == home.parent / "docs" / "guide_latest.md"
    assert lay.docs_snapshot("guide", "1.2.0") == home.parent / "docs" / "archive" / "guide_v1.2.0.md"


def test_existing_versions_flat(tmp_path):
    home = tmp_path / "docspec"
    docs_archive = home.parent / "docs" / "archive"
    docs_archive.mkdir(parents=True)
    (docs_archive / "guide_v1.0.0.md").write_text("x", encoding="utf-8")
    (docs_archive / "guide_v1.2.0.md").write_text("x", encoding="utf-8")
    (docs_archive / "guide_v2.0.1.md").write_text("x", encoding="utf-8")
    (docs_archive / "guide_vNOTSEMVER.md").write_text("x", encoding="utf-8")  # 不合 semver → 跳過
    lay = Layout(home, "flat")
    assert sorted(lay.existing_versions("guide")) == [(1, 0, 0), (1, 2, 0), (2, 0, 1)]


def test_existing_versions_none(tmp_path):
    home = tmp_path / "docspec"
    lay = Layout(home, "flat")
    assert lay.existing_versions("guide") == []


def test_parse_semver():
    assert parse_semver("1.2.3") == (1, 2, 3)
    assert parse_semver("10.0.1") == (10, 0, 1)
    assert parse_semver("1.2") is None
    assert parse_semver("1.2.3.4") is None
    assert parse_semver("v1.2.3") is None
    assert parse_semver("abc") is None


def test_next_version_bumps():
    assert next_version(None, "patch") == "1.0.0"
    assert next_version(None, "minor") == "1.0.0"
    assert next_version(None, "major") == "1.0.0"
    assert next_version((1, 0, 0), "patch") == "1.0.1"
    assert next_version((1, 0, 0), "minor") == "1.1.0"
    assert next_version((1, 0, 0), "major") == "2.0.0"
    assert next_version((1, 2, 3), "minor") == "1.3.0"   # patch 歸零
    assert next_version((1, 2, 3), "major") == "2.0.0"   # minor/patch 歸零
    assert next_version("1.4.2", "patch") == "1.4.3"     # 接受字串前版


def test_next_version_rejects_bad_level():
    with pytest.raises(ValueError):
        next_version((1, 0, 0), "huge")
