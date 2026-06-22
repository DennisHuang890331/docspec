"""config 載入（section 模型預設）。"""

from __future__ import annotations

import pytest

from dspx.config import ConfigError, load_config


def test_defaults_when_absent(make_project):
    home = make_project()
    (home / "config.yaml").unlink()
    cfg = load_config(home)
    assert cfg["schema"] == "section-driven"
    assert cfg["autonomy"]["publish"] == "human"


def test_defaults_have_purpose_no_tags(make_project):
    """metadata 清理（已拍）：DEFAULTS 有 purpose、無 tags、autonomy 只剩 publish。"""
    home = make_project()
    (home / "config.yaml").unlink()
    cfg = load_config(home)
    assert cfg["purpose"] == ""           # metadata，預設空字串（authored 後填）
    assert "tags" not in cfg              # 死旋鈕已砍（無讀者）
    assert set(cfg["autonomy"]) == {"publish"}   # 非-publish 自主度旋鈕已砍


def test_purpose_loaded(make_project):
    home = make_project("purpose: 整座森林的目標\n")
    cfg = load_config(home)
    assert cfg["purpose"] == "整座森林的目標"


def test_unknown_key_ignored(make_project):
    home = make_project("language: zh-TW\nbogus: 1\n")
    cfg = load_config(home)
    assert "bogus" not in cfg


def test_publish_human_ok(make_project):
    home = make_project("autonomy:\n  publish: human\n")
    cfg = load_config(home)
    assert cfg["autonomy"]["publish"] == "human"


def test_publish_lock_enforced(make_project):
    home = make_project("autonomy:\n  publish: auto\n")
    with pytest.raises(ConfigError):
        load_config(home)


def test_dropped_autonomy_knob_warns_and_ignored(make_project):
    """砍掉的旋鈕（如 lint）若仍出現＝未知旋鈕：warn＋忽略，不 crash；publish 仍預設 human。"""
    warnings: list[str] = []
    home = make_project("autonomy:\n  lint: auto\n")
    cfg = load_config(home, warn=warnings.append)
    assert "lint" not in cfg["autonomy"]                 # 未知旋鈕被忽略
    assert cfg["autonomy"]["publish"] == "human"          # 補回預設、無 crash
    assert any("lint" in w for w in warnings)             # 有 warn
