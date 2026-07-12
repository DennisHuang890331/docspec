"""frontmatter 模組測試。"""

import pytest

from dspx.env.frontmatter import (
    FrontmatterError,
    parse_frontmatter,
    read_frontmatter,
    write_frontmatter,
)


def test_roundtrip(tmp_path):
    path = tmp_path / "x.md"
    write_frontmatter(path, {"status": "exploring", "中文鍵": "值"}, "\n# 標題\n內文\n")
    data, body = read_frontmatter(path)
    assert data == {"status": "exploring", "中文鍵": "值"}
    assert "# 標題" in body


def test_no_frontmatter_passthrough():
    data, body = parse_frontmatter("# 純內文\n")
    assert data == {}
    assert body == "# 純內文\n"


def test_unclosed_raises():
    with pytest.raises(FrontmatterError, match="not closed"):
        parse_frontmatter("---\nstatus: x\n# 沒有關閉")


def test_bad_yaml_raises():
    with pytest.raises(FrontmatterError, match="parse failed"):
        parse_frontmatter("---\nkey: [1, 2\n---\nbody")


def test_non_mapping_raises():
    with pytest.raises(FrontmatterError, match="key-value mapping"):
        parse_frontmatter("---\n- a\n- b\n---\nbody")
