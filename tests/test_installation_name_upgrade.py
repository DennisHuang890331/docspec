"""ArtiSpec 安裝契約；dspx import 與 docspec 專案目錄仍相容。"""

from __future__ import annotations

import configparser
import json
import subprocess
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

from dspx.engine import paths
from dspx.env import _install_source


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory):
    directory = tmp_path_factory.mktemp("artispec-wheel")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(directory)],
        cwd=Path(__file__).parents[1], check=True, capture_output=True, text=True,
    )
    wheels = list(directory.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_project_distribution_name_and_only_console_entry():
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text("utf-8"))["project"]
    assert project["name"] == "artispec"
    assert project["scripts"] == {"artispec": "dspx.cli:main"}


def test_wheel_name_metadata_and_core_import_are_consistent(built_wheel):
    assert built_wheel.name.startswith("artispec-")
    with zipfile.ZipFile(built_wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        assert len(metadata_names) == 1
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        assert metadata["Name"] == "artispec"
        assert "dspx/__init__.py" in archive.namelist()
        assert "dspx/cli.py" in archive.namelist()
        entries = configparser.ConfigParser()
        entries.read_string(archive.read(metadata_names[0].replace("METADATA", "entry_points.txt")).decode())
        assert dict(entries["console_scripts"]) == {"artispec": "dspx.cli:main"}


def test_read_install_source_reads_new_distribution_by_default(monkeypatch):
    requested = []

    class Distribution:
        def read_text(self, name):
            assert name == "direct_url.json"
            return json.dumps({"url": "file:///tmp/docspec", "dir_info": {}})

    def distribution(name):
        requested.append(name)
        return Distribution()

    monkeypatch.setattr("importlib.metadata.distribution", distribution)
    assert _install_source.read_install_source() == {"kind": "dir", "path": "/tmp/docspec"}
    assert requested == ["artispec"]


def test_data_roots_use_new_app_name_and_exact_legacy_location(monkeypatch, tmp_path):
    calls = []

    def user_data_dir(appname, **kwargs):
        calls.append((appname, kwargs))
        return str(tmp_path / appname)

    monkeypatch.setattr("platformdirs.user_data_dir", user_data_dir)
    assert paths.data_dir() == tmp_path / "artispec"
    assert paths.legacy_data_dir() == tmp_path / "docspec"
    assert calls == [("artispec", {"appauthor": False}), ("docspec", {})]
    assert not list(tmp_path.iterdir())


def test_program_update_targets_new_package_and_dev_source():
    remote = "git+https://github.com/DennisHuang890331/docspec@dev"
    git = {"kind": "git", "commit": "synthetic", "url": "synthetic"}
    assert _install_source.update_argv(git) == [
        "uv", "tool", "install", "--from", remote, "artispec", "--reinstall", "--no-cache",
    ]
    assert _install_source.update_command(git) == (
        f"uv tool install --from {remote} artispec --reinstall --no-cache"
    )
    assert _install_source.update_argv(None) == ["uv", "tool", "upgrade", "artispec"]
    assert _install_source.update_command(None) == "uv tool upgrade artispec"
