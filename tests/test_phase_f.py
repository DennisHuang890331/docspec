"""Phase F — 散布/更新 UX：doctor（唯讀診斷）、setup（資產層安裝＋對齊已裝）、version（三版本）、
init 排版提示。連網一律 mock（CI 絕不真連網）。

（upgrade 已併入 setup：setup 冪等，且偵測到已裝 TinyTeX 就對齊——原 upgrade 的「對齊已裝資產」
職責＝setup 的一個切面。）"""

from __future__ import annotations

import json
import time

import pytest

from dspx.engine import paths
from dspx.commands.maintenance import doctor as doctor_cmd
from dspx.commands.maintenance import init as init_cmd
from dspx.commands.maintenance import setup as setup_cmd
from dspx.commands.maintenance import version as version_cmd


# ── 共用：把 data_dir 導到 tmp、灌一個健康的 tex.lock＋字型 ─────────────

def _healthy_env(monkeypatch, tmp_path):
    """建立健康環境（tex.lock 對齊 _MANIFEST、全字型齊、xelatex/pandoc 命中）。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    fonts = tmp_path / "fonts"
    fonts.mkdir(parents=True)
    for f in paths.REQUIRED_FONT_FILES:
        (fonts / f).write_bytes(b"x")
    lock = {
        "tinytex_tag": setup_cmd._MANIFEST["tag"],
        "tlmgr_packages": list(setup_cmd._TEX_PACKAGES),
        "fonts": list(paths.REQUIRED_FONT_FILES),
    }
    paths.tex_lock_path().write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(paths, "resolve_typst", lambda: tmp_path / "typst")   # 預設引擎（核心）
    monkeypatch.setattr(paths, "resolve_xelatex", lambda: tmp_path / "xelatex")  # 可選 LaTeX 軌
    monkeypatch.setattr(paths, "resolve_pandoc", lambda: "/usr/bin/pandoc")


# ── doctor：個別檢查 ─────────────────────────────────────────────

def test_doctor_healthy_all_ok(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    assert doctor_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "[FAIL]" not in out
    assert "[WARN]" not in out
    assert "Typesetting environment healthy" in out


def test_doctor_missing_typst_fails(monkeypatch, tmp_path, capsys):
    """typst＝預設 render 引擎，缺＝FAIL（預設 export 出不了 PDF）。"""
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "resolve_typst", lambda: None)
    assert doctor_cmd.run([]) == 1     # FAIL → 非零
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "typst" in out
    assert "docspec setup" in out      # 修復指令


def test_doctor_missing_tinytex_warns(monkeypatch, tmp_path, capsys):
    """TinyTeX/xelatex 現為 OPTIONAL：缺＝WARN（非 FAIL）、exit 0；指向 --with-latex。"""
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "resolve_xelatex", lambda: None)
    assert doctor_cmd.run([]) == 0     # WARN → 不致非零
    out = capsys.readouterr().out
    assert "[FAIL]" not in out
    assert "[WARN]" in out
    assert "docspec setup --with-latex" in out  # 修復指令指向可選安裝


def test_doctor_missing_fonts_fails(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    # 移除一個字型 → resolve_fonts_dir 仍回夾（含部分字型），但齊全檢查失敗
    (tmp_path / "fonts" / paths.REQUIRED_FONT_FILES[0]).unlink()
    assert doctor_cmd.run([]) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "docspec setup" in out
    assert paths.REQUIRED_FONT_FILES[0] in out


def test_doctor_missing_pandoc_fails(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "resolve_pandoc", lambda: None)
    assert doctor_cmd.run([]) == 1
    out = capsys.readouterr().out
    assert "controlled pandoc not found" in out
    assert "docspec setup" in out


def test_doctor_lock_missing_packages_warns(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    # tex.lock 少宣告套件 → WARN（非 FAIL）→ exit 0
    lock = json.loads(paths.tex_lock_path().read_text(encoding="utf-8"))
    lock["tlmgr_packages"] = setup_cmd._TEX_PACKAGES[:3]
    paths.tex_lock_path().write_text(json.dumps(lock), encoding="utf-8")
    assert doctor_cmd.run([]) == 0      # WARN 不致非零
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "docspec setup" in out


def test_doctor_no_lock_warns_setup(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    paths.tex_lock_path().unlink()
    assert doctor_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "docspec setup" in out


def test_doctor_is_read_only(monkeypatch, tmp_path):
    """doctor 不得寫任何檔（除非 --check-latest 寫快取）。"""
    _healthy_env(monkeypatch, tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    doctor_cmd.run([])
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after      # 無新增/刪除


# ── doctor --check-latest：連網 mock + TTL 快取 ─────────────────────

def test_check_latest_same_version_ok(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor_cmd, "_fetch_latest_tinytex_tag",
                        lambda: setup_cmd._MANIFEST["tag"])
    assert doctor_cmd.run(["--check-latest"]) == 0
    out = capsys.readouterr().out
    assert "update check" in out
    assert "already at the upstream latest" in out
    # 結果寫快取
    assert (tmp_path / "update-cache.json").is_file()


def test_check_latest_newer_warns(monkeypatch, tmp_path, capsys):
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor_cmd, "_fetch_latest_tinytex_tag", lambda: "v9999.99")
    assert doctor_cmd.run(["--check-latest"]) == 0   # 新版＝WARN、不致非零
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "v9999.99" in out


def test_check_latest_offline_silent(monkeypatch, tmp_path, capsys):
    """離線/查無 → 靜默零噪音（不印「新版檢查」行）。"""
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor_cmd, "_fetch_latest_tinytex_tag", lambda: None)
    assert doctor_cmd.run(["--check-latest"]) == 0
    assert "新版檢查" not in capsys.readouterr().out


def test_check_latest_uses_cache_within_ttl(monkeypatch, tmp_path, capsys):
    """TTL 內：讀快取、不連網（_fetch 被呼叫即測試失敗）。"""
    _healthy_env(monkeypatch, tmp_path)
    (tmp_path / "update-cache.json").write_text(json.dumps(
        {"fetched_at": time.time(), "latest_tinytex_tag": setup_cmd._MANIFEST["tag"]}),
        encoding="utf-8")

    def _boom():
        raise AssertionError("TTL 內不該連網")

    monkeypatch.setattr(doctor_cmd, "_fetch_latest_tinytex_tag", _boom)
    assert doctor_cmd.run(["--check-latest"]) == 0
    assert "already at the upstream latest" in capsys.readouterr().out


def test_check_latest_expired_cache_refetches(monkeypatch, tmp_path):
    """過期快取 → 重連網。"""
    _healthy_env(monkeypatch, tmp_path)
    (tmp_path / "update-cache.json").write_text(json.dumps(
        {"fetched_at": time.time() - doctor_cmd._UPDATE_CACHE_TTL - 10,
         "latest_tinytex_tag": "v0000.00"}), encoding="utf-8")
    called = {"n": 0}

    def _fetch():
        called["n"] += 1
        return setup_cmd._MANIFEST["tag"]

    monkeypatch.setattr(doctor_cmd, "_fetch_latest_tinytex_tag", _fetch)
    doctor_cmd.run(["--check-latest"])
    assert called["n"] == 1


# ── version：三版本一併印 ─────────────────────────────────────────

def test_version_report_includes_three(monkeypatch, tmp_path):
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(version_cmd, "_pandoc_version", lambda: "3.9.0.2")
    rep = version_cmd.report()
    assert "docspec" in rep
    assert setup_cmd._MANIFEST["tag"] in rep    # tex.lock 的 TinyTeX 版
    assert "3.9.0.2" in rep                     # pandoc 版


def test_version_no_lock_hints_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)   # 無 tex.lock
    assert "docspec setup" in version_cmd._tinytex_version()


def test_cli_version_flag_uses_report(monkeypatch, tmp_path, capsys):
    from dspx import cli
    _healthy_env(monkeypatch, tmp_path)
    monkeypatch.setattr(version_cmd, "_pandoc_version", lambda: "x")
    assert cli.main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "TinyTeX" in out and "pandoc" in out


# ── setup：資產層安裝、對齊已裝 TinyTeX（吸收 upgrade）、印程式更新提示 ──────────────────

def test_setup_aligns_installed_tinytex_and_prints_program_hint(monkeypatch, tmp_path, capsys):
    """setup 偵測到已裝 TinyTeX（tlmgr_path 命中）就對齊它（無 --with-latex 也對齊）＝原 upgrade
    的「對齊已裝資產」職責；末尾印程式更新提示（uv 換 wheel）。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(setup_cmd, "_platform_key", lambda: "windows")
    calls = []
    monkeypatch.setattr(setup_cmd, "_ensure_tinytex",
                        lambda *a, **k: calls.append("tinytex") or True)
    # TinyTeX 已裝（tlmgr_path 命中）→ setup 對齊它，即使沒給 --with-latex
    monkeypatch.setattr(paths, "tlmgr_path", lambda root: tmp_path / "tlmgr")
    monkeypatch.setattr(setup_cmd, "_ensure_packages",
                        lambda tlmgr: (calls.append("pkgs") or (True, ["xecjk"])))
    monkeypatch.setattr(setup_cmd, "_ensure_fonts",
                        lambda **k: calls.append("fonts") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_pandoc",
                        lambda **k: calls.append("pandoc") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_typst",
                        lambda **k: calls.append("typst") or True)
    monkeypatch.setattr(paths, "resolve_xelatex", lambda: tmp_path / "xelatex")
    monkeypatch.setattr(paths, "resolve_pandoc", lambda: tmp_path / "pandoc")
    monkeypatch.setattr(paths, "resolve_typst", lambda: tmp_path / "typst")
    monkeypatch.setattr(paths, "resolve_drawio", lambda: None)
    written = {}
    monkeypatch.setattr(setup_cmd, "_write_lock",
                        lambda tlmgr, xe, pkgs, pandoc=None, typst=None, drawio=None:
                        written.update(pkgs=pkgs, pandoc=pandoc, typst=typst))
    assert setup_cmd.run([]) == 0
    # 核心先（fonts/pandoc/typst），TinyTeX 已裝才對齊（tinytex/pkgs）
    assert calls == ["fonts", "pandoc", "typst", "tinytex", "pkgs"]
    assert written["pkgs"] == ["xecjk"] and written["typst"] == tmp_path / "typst"
    out = capsys.readouterr().out
    assert "--reinstall --no-cache" in out      # 程式更新提示（兩軌）
    assert "uv tool install" in out


def test_setup_skips_tinytex_when_not_installed(monkeypatch, tmp_path):
    """TinyTeX 未裝（tlmgr_path 回 None）且無 --with-latex → setup 不碰 TinyTeX（不硬塞數百 MB）。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(setup_cmd, "_platform_key", lambda: "windows")
    calls = []
    monkeypatch.setattr(setup_cmd, "_ensure_fonts", lambda **k: calls.append("fonts") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_pandoc", lambda **k: calls.append("pandoc") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_typst", lambda **k: calls.append("typst") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_tinytex", lambda *a, **k: calls.append("tinytex") or True)
    monkeypatch.setattr(paths, "tlmgr_path", lambda root: None)   # 未裝
    monkeypatch.setattr(paths, "resolve_xelatex", lambda: None)
    monkeypatch.setattr(paths, "resolve_pandoc", lambda: tmp_path / "pandoc")
    monkeypatch.setattr(paths, "resolve_typst", lambda: tmp_path / "typst")
    monkeypatch.setattr(paths, "resolve_drawio", lambda: None)
    monkeypatch.setattr(setup_cmd, "_write_lock", lambda *a, **k: None)
    assert setup_cmd.run([]) == 0
    assert "tinytex" not in calls and calls == ["fonts", "pandoc", "typst"]


def test_setup_aborts_on_tinytex_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(setup_cmd, "_platform_key", lambda: "windows")
    monkeypatch.setattr(setup_cmd, "_ensure_fonts", lambda **k: True)
    monkeypatch.setattr(setup_cmd, "_ensure_pandoc", lambda **k: True)
    monkeypatch.setattr(setup_cmd, "_ensure_typst", lambda **k: True)
    # 強制走 LaTeX 軌（--with-latex），且 TinyTeX 安裝失敗 → 中止
    monkeypatch.setattr(paths, "tlmgr_path", lambda root: None)
    monkeypatch.setattr(setup_cmd, "_ensure_tinytex", lambda *a, **k: False)
    assert setup_cmd.run(["--with-latex"]) == 1


# ── init：被動排版提示（離線、可關）─────────────────────────────────

def test_init_hint_when_no_lock(monkeypatch, tmp_path, capsys):
    proj = tmp_path / "p"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setattr(paths, "read_tex_lock", lambda: None)   # 無 tex.lock
    assert init_cmd.run(["--tool", "claude"]) == 0
    assert "docspec doctor" in capsys.readouterr().out


def test_init_hint_when_tag_mismatch(monkeypatch, tmp_path, capsys):
    proj = tmp_path / "p2"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setattr(paths, "read_tex_lock", lambda: {"tinytex_tag": "v0000.00"})
    assert init_cmd.run(["--tool", "claude"]) == 0
    out = capsys.readouterr().out
    assert "docspec doctor" in out
    assert "does not match" in out


def test_init_no_hint_when_aligned(monkeypatch, tmp_path, capsys):
    proj = tmp_path / "p3"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setattr(paths, "read_tex_lock",
                        lambda: {"tinytex_tag": setup_cmd._MANIFEST["tag"]})
    assert init_cmd.run(["--tool", "claude"]) == 0
    assert "docspec doctor" not in capsys.readouterr().out


def test_init_no_tex_hint_flag_silences(monkeypatch, tmp_path, capsys):
    proj = tmp_path / "p4"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setattr(paths, "read_tex_lock", lambda: None)   # 本會提示
    assert init_cmd.run(["--tool", "claude", "--no-tex-hint"]) == 0
    assert "docspec doctor" not in capsys.readouterr().out


# ── CLI robustness (oss-release-prep group 2) ─────────────────────────

def test_init_degrades_on_broken_skills(monkeypatch, tmp_path, capsys):
    """init guards against an uncaught SkillError from broken packaged-skill data."""
    from dspx.commands.maintenance import skills_cmd
    from dspx.env.skills import SkillError
    proj = tmp_path / "pbroken"
    proj.mkdir()
    monkeypatch.chdir(proj)
    monkeypatch.setattr(paths, "read_tex_lock", lambda: None)

    def _boom(*a, **k):
        raise SkillError("packaged skill data is broken")

    monkeypatch.setattr(skills_cmd, "_install", _boom)
    assert init_cmd.run(["--tool", "claude"]) == 1   # non-zero, no traceback
    assert "skill install failed" in capsys.readouterr().err


def test_version_honors_help(capsys):
    import pytest
    from dspx.commands.maintenance import version as version_cmd
    with pytest.raises(SystemExit) as ei:        # argparse exits 0 on --help
        version_cmd.run(["--help"])
    assert ei.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_hook_honors_help(capsys):
    from dspx.commands._internal import hook as hook_cmd
    assert hook_cmd.run(["--help"]) == 0
    assert "guard" in capsys.readouterr().out


# ── registry 註冊 ────────────────────────────────────────────────

def test_new_commands_registered():
    from dspx.commands import REGISTRY
    for name in ("doctor", "setup", "version"):
        assert name in REGISTRY
    assert "upgrade" not in REGISTRY          # 已併入 setup
