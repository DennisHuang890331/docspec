"""section-driven schema 載入。"""

from __future__ import annotations

import pytest

from dspx.engine.schema import DEFAULT_SCHEMA, SchemaError, load_schema


def test_load_builtin_section_driven():
    schema = load_schema()  # 預設 section-driven
    assert schema.name == "section-driven"
    ids = {a.id for a in schema.artifacts}
    # ★retire-develop-workbench：develop artifact 已廢除
    assert ids == {"concept", "decisions", "material", "history", "history-md"}


def test_artifact_kinds_and_aperture():
    schema = load_schema(DEFAULT_SCHEMA)
    concept = schema.by_id("concept")
    assert concept.kind == "yaml"
    assert concept.aperture.projects_into == "docs"
    assert "develop" in concept.aperture.write

    # ★retire-develop-workbench：develop artifact 不存在（工作台廢除）
    assert schema.by_id("develop") is None


def test_skills_table_present():
    schema = load_schema()
    assert set(schema.skills) == {"develop", "apply", "factcheck", "publish", "release"}
    assert schema.skills["apply"]["reads"] == ["concept", "decisions", "material", "docs"]


def test_unknown_schema_raises():
    with pytest.raises(SchemaError):
        load_schema("no-such-schema")
