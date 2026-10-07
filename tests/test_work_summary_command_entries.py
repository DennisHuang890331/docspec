"""Suggested governance queries must execute and preserve their real sources."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"


def _hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def cli_project(make_project):
    home = make_project()
    environment = os.environ.copy()
    environment.update(
        PYTHONPATH=str(SOURCE_ROOT),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
        DOCSPEC_AGENT="gpt",
    )

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "dspx.cli", *args],
            cwd=home.parent,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    return home.parent, run


def _ok(run, *args):
    result = run(*args)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


def _read_only(run, root, *args):
    before = _hashes(root)
    result = run(*args)
    assert _hashes(root) == before, f"Query changed project files: {args!r}"
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


def _records(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _records(child)


def _assert_readback(output, identifier, fields, status):
    """Check the returned record, without prescribing the command's spelling."""
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        assert identifier in output
        for value in fields.values():
            assert value in output
        assert status in output
    else:
        matching = [row for row in _records(payload) if row.get("id") == identifier]
        assert matching, f"Suggested query omitted {identifier}: {output}"
        assert any(
            all(row.get(key) == value for key, value in fields.items())
            and row.get("effective-status", row.get("status")) == status
            for row in matching
        ), f"Suggested query did not return the original fields/status: {matching}"


def _suggested_query(run, root, identifier, expected_status):
    _ok(run, "roadmap", "add", "--title", "相關來源查詢", "--ref", f"gov:{identifier}")
    summary = json.loads(_read_only(run, root, "roadmap", "show", "W-gpt-1", "--json"))
    row = next(item for item in summary["governance"] if item["id"] == identifier)
    assert row["status"] == expected_status
    assert f"gov:{identifier}" in summary["work"]["refs"]
    assert row["sources"]
    assert all((root / source).is_file() for source in row["sources"])
    text = _read_only(run, root, "roadmap", "show", "W-gpt-1")
    assert row["command"] in text
    command = shlex.split(row["command"])
    assert command[0] == "artispec", f"Not a CLI query: {row['command']}"
    return _read_only(run, root, *command[1:])


@pytest.mark.parametrize("state", ["open", "answered", "withdrawn", "needs-explanation"])
def test_suggested_question_query_returns_original_body_and_effective_state(cli_project, state):
    root, run = cli_project
    title = "合成問題：是否支援含空白的中文路徑？"
    body = '請保存這份原文。\n選項 A：「目前支援」；選項 B：「下一版再做」。'
    _ok(run, "question", "add", "--title", title, "--body", body)
    identifier = "Q-gpt-1"
    if state == "answered":
        _ok(run, "ruling", "add", "--quote", "合成負責人決定本版支援。", "--answers", identifier)
    elif state in ("withdrawn", "needs-explanation"):
        _ok(run, "question", "withdraw" if state == "withdrawn" else "explain", identifier)

    default_rows = json.loads(_read_only(run, root, "question", "list", "--json"))["questions"]
    assert (identifier in {row["id"] for row in default_rows}) == (state in ("open", "needs-explanation"))
    source_rows = json.loads(_read_only(run, root, "question", "list", "--all", "--json"))["questions"]
    original = next(row for row in source_rows if row["id"] == identifier)
    assert original["title"] == title and original["body"] == body
    assert original["effective-status"] == state

    output = _suggested_query(run, root, identifier, state)
    _assert_readback(output, identifier, {"title": title, "body": body}, state)


@pytest.mark.parametrize("kind", ["ruling", "info", "decision"])
def test_existing_governance_query_suggestions_remain_executable_and_read_only(cli_project, kind):
    root, run = cli_project
    if kind == "ruling":
        quote = "合成裁定：本版保留所有原始引用。"
        _ok(run, "ruling", "add", "--quote", quote)
        identifier, fields, status = "RL-gpt-1", {"quote": quote}, "effective"
    elif kind == "info":
        quote, about = "合成環境已有瀏覽器，不需下載。", "執行環境"
        _ok(run, "info", "add", "--quote", quote, "--about", about)
        identifier, fields, status = "I-gpt-1", {"quote": quote, "about": about}, "current"
    else:
        statement, title = "完整決策：所有查詢保留原始紀錄。", "查詢原則"
        _ok(run, "ruling", "add", "--quote", "合成負責人同意此完整決策。")
        _ok(run, "decision", "add", "--title", title, "--statement", statement, "--based-on", "RL-gpt-1")
        _ok(run, "decision", "activate", "D-gpt-1")
        identifier, fields, status = "D-gpt-1", {"statement": statement, "title": title}, "active"

    output = _suggested_query(run, root, identifier, status)
    _assert_readback(output, identifier, fields, status)


def _governance_query_from_work(run, root, work, source):
    summary = json.loads(_read_only(run, root, "roadmap", "show", work, "--json"))
    row = next(item for item in summary["governance"] if item["id"] == source)
    assert f"gov:{source}" in summary["work"]["refs"]
    assert row["sources"] and all((root / path).is_file() for path in row["sources"])
    text = _read_only(run, root, "roadmap", "show", work)
    assert row["command"] in text
    command = shlex.split(row["command"])
    assert command[0] == "artispec"
    return _read_only(run, root, *command[1:])


def test_suggested_work_query_returns_the_original_work_and_its_derived_state(cli_project):
    root, run = cli_project
    title, what = "原有合成工作", "保留原識別碼及完整工作目標。"
    _ok(run, "ruling", "add", "--quote", "合成負責人要求追查工作來源。")
    _ok(run, "roadmap", "add", "--title", title, "--what", what)
    _ok(run, "roadmap", "done", "W-gpt-1", "--note", "已完成這項合成整理。")
    expected = json.loads(_read_only(run, root, "roadmap", "show", "W-gpt-1", "--json"))["work"]
    assert expected["status"] == "done"
    _ok(run, "roadmap", "add", "--title", "追查工作", "--ref", "gov:W-gpt-1")
    output = _governance_query_from_work(run, root, "W-gpt-2", "W-gpt-1")
    _assert_readback(output, "W-gpt-1", {"title": title, "what": what}, expected["status"])


def test_suggested_milestone_query_returns_relevant_work_counts_without_other_milestones(cli_project):
    root, run = cli_project
    title = "合成交付里程碑"
    _ok(run, "ruling", "add", "--quote", "合成負責人要求追查指定里程碑。")
    _ok(run, "roadmap", "milestone", "--title", title, "--type", "deliverable")
    _ok(run, "roadmap", "milestone", "--title", "無關里程碑", "--type", "checkpoint")
    _ok(run, "roadmap", "add", "--title", "相關已完成工作", "--milestone", "M-gpt-1")
    _ok(run, "roadmap", "done", "W-gpt-1", "--note", "合成工作已完成。")
    _ok(run, "roadmap", "add", "--title", "相關未完成工作", "--milestone", "M-gpt-1")
    _ok(run, "roadmap", "add", "--title", "無關工作", "--milestone", "M-gpt-2")
    _ok(run, "roadmap", "add", "--title", "追查里程碑", "--ref", "gov:M-gpt-1")

    existing = json.loads(_read_only(run, root, "roadmap", "--milestone", "M-gpt-1", "--json"))
    expected, = existing["milestones"]
    assert expected["id"] == "M-gpt-1" and expected["status"] == "in-progress"
    assert expected["done"] == 1 and expected["total"] == 2
    assert {row["id"] for row in expected["items"]} == {"W-gpt-1", "W-gpt-2"}

    output = _governance_query_from_work(run, root, "W-gpt-4", "M-gpt-1")
    payload = json.loads(output)
    returned = [row for row in _records(payload) if row.get("id") == "M-gpt-1"]
    assert len(returned) == 1
    for field in ("id", "title", "type", "status", "done", "total"):
        assert returned[0][field] == expected[field]
    assert {row["id"] for row in returned[0]["items"]} == {"W-gpt-1", "W-gpt-2"}
    assert all(row.get("id") not in {"M-gpt-2", "W-gpt-3"} for row in _records(payload))
