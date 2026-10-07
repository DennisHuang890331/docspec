"""External ArtiSpec branding preserves the existing package and project data."""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from dspx import __version__
from dspx import cli
from dspx.commands.maintenance import init as init_cmd
from dspx.commands.maintenance import version as version_cmd


def test_single_cli_entrypoint_uses_artispec_install_package():
    config = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["name"] == "artispec"
    assert config["project"]["scripts"]["artispec"] == "dspx.cli:main"
    assert config["project"]["scripts"] == {"artispec": "dspx.cli:main"}


@pytest.mark.parametrize("args", [[], ["--help"], ["--help-all"]])
def test_root_help_explains_both_domains(args, capsys):
    assert cli.main(args) == 0
    output = capsys.readouterr().out
    assert "ArtiSpec" in output
    assert "document and software" in output
    assert "Usage: artispec" in output


def test_version_reports_brand_and_canonical_setup(monkeypatch, capsys):
    monkeypatch.setattr(version_cmd, "_install_source_line", lambda: None)
    monkeypatch.setattr(version_cmd.paths, "resolve_typst", lambda: None)
    monkeypatch.setattr(version_cmd.paths, "resolve_pandoc", lambda: None)
    monkeypatch.setattr(version_cmd.paths, "read_tex_lock", lambda: None)
    assert cli.main(["--version"]) == 0
    output = capsys.readouterr().out
    assert output.startswith(f"ArtiSpec {__version__}\n")
    assert "artispec setup" in output
    assert version_cmd.run([]) == 0
    assert capsys.readouterr().out == output


@pytest.mark.parametrize("lang", ["zh-TW", "en"])
def test_generated_rules_common_queries_preserve_domain_workflow(lang):
    block = init_cmd.agents_md_block(lang)
    assert "<!-- docspec:begin -->" in block
    assert "<!-- docspec:end -->" in block
    assert "ArtiSpec" in block
    for command in (
        "artispec handover", "artispec roadmap", "artispec roadmap show",
        "artispec change`", "artispec change show", "artispec change new",
        "artispec code change new", "artispec change migrate",
    ):
        assert command in block
    assert "--all" in block
    assert "docspec/changes/" in block
    assert "dspx-factcheck" in block
    assert "dspx-verify" in block
    assert "`docspec " not in block


def test_init_updates_old_managed_block_without_renaming_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "docspec"
    home.mkdir()
    config = b"language: en\n# project setting\n"
    (home / "config.yaml").write_bytes(config)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Owner rules\n\n<!-- docspec:begin -->\nOld rule\n<!-- docspec:end -->\n\n# Footer\n", encoding="utf-8")
    assert init_cmd.run(["--tool", "codex", "--agents-md", "--no-update-check", "--no-tex-hint"]) == 0
    assert (home / "config.yaml").read_bytes() == config
    assert (home / "corpus").is_dir()
    assert not (tmp_path / "artispec").exists()
    block = agents.read_text(encoding="utf-8")
    assert block.startswith("# Owner rules\n") and block.endswith("# Footer\n")
    assert "Old rule" not in block
    assert block.count("<!-- docspec:begin -->") == 1
    assert "artispec change show" in block
    assert (tmp_path / ".agents" / "skills" / "dspx-develop" / "SKILL.md").is_file()
