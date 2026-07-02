"""docspec setup（Phase B）：data_dir 解析、release asset 解析、sha 驗證、字型 copy、
tex.lock、冪等。網路/下載一律 mock（CI 絕不真下載）。"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile

import pytest

from dspx import paths
from dspx.commands import setup as setup_cmd


# ── setup.run()：TinyTeX 改 optional（--with-latex 才裝）─────────────

def _stub_setup_run(monkeypatch, tmp_path):
    """把所有 _ensure_* 換成記錄呼叫的 stub，避免真下載；回傳 calls list。"""
    calls: list[str] = []
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(setup_cmd, "_platform_key", lambda: "windows")
    monkeypatch.setattr(setup_cmd, "_ensure_fonts", lambda **k: calls.append("fonts") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_pandoc", lambda **k: calls.append("pandoc") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_typst", lambda **k: calls.append("typst") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_tinytex", lambda *a, **k: calls.append("tinytex") or True)
    monkeypatch.setattr(setup_cmd, "_ensure_packages", lambda tlmgr: calls.append("pkgs") or (True, []))
    monkeypatch.setattr(setup_cmd, "_ensure_drawio", lambda **k: calls.append("drawio") or True)
    monkeypatch.setattr(paths, "tlmgr_path", lambda root: tmp_path / "tlmgr")
    monkeypatch.setattr(paths, "resolve_xelatex", lambda: tmp_path / "xelatex")
    monkeypatch.setattr(paths, "resolve_pandoc", lambda: tmp_path / "pandoc")
    monkeypatch.setattr(paths, "resolve_typst", lambda: tmp_path / "typst")
    monkeypatch.setattr(paths, "resolve_drawio", lambda: None)
    monkeypatch.setattr(setup_cmd, "_write_lock", lambda *a, **k: calls.append("lock"))
    return calls


def test_setup_core_does_not_install_tinytex(monkeypatch, tmp_path, capsys):
    """核心 setup（無旗標）只裝 fonts+pandoc+typst，不碰 TinyTeX/tlmgr/drawio。"""
    calls = _stub_setup_run(monkeypatch, tmp_path)
    assert setup_cmd.run([]) == 0
    assert "tinytex" not in calls and "pkgs" not in calls and "drawio" not in calls
    assert {"fonts", "pandoc", "typst"} <= set(calls)
    out = capsys.readouterr().out
    assert "setup --with-latex" in out   # 提示可選安裝


def test_setup_with_latex_installs_tinytex(monkeypatch, tmp_path):
    """--with-latex 才裝 TinyTeX + tlmgr 套件。"""
    calls = _stub_setup_run(monkeypatch, tmp_path)
    assert setup_cmd.run(["--with-latex"]) == 0
    assert "tinytex" in calls and "pkgs" in calls


def test_setup_warns_macos_not_verified(monkeypatch, tmp_path, capsys):
    """macOS 尚未實機驗證：setup 照跑但在 stderr 誠實提醒（不擋）。"""
    _stub_setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(setup_cmd.platform, "system", lambda: "Darwin")
    assert setup_cmd.run([]) == 0
    err = capsys.readouterr().err
    assert "macOS is not yet verified" in err


def test_setup_no_macos_warning_on_other_platforms(monkeypatch, tmp_path, capsys):
    """非 macOS 平台不印那行提醒。"""
    _stub_setup_run(monkeypatch, tmp_path)
    monkeypatch.setattr(setup_cmd.platform, "system", lambda: "Windows")
    assert setup_cmd.run([]) == 0
    assert "macOS is not yet verified" not in capsys.readouterr().err


# ── paths 解析 ────────────────────────────────────────────────────

def test_data_dir_subpaths_consistent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    assert paths.tinytex_root() == tmp_path / "tinytex"
    assert paths.fonts_dir() == tmp_path / "fonts"
    assert paths.tex_lock_path() == tmp_path / "tex.lock"
    assert paths.cache_dir() == tmp_path / "cache"


def test_resolve_xelatex_env_override(monkeypatch, tmp_path):
    exe = "xelatex.exe" if paths.os.name == "nt" else "xelatex"
    bindir = tmp_path / "bin" / "plat"
    bindir.mkdir(parents=True)
    (bindir / exe).write_text("#!stub", encoding="utf-8")
    monkeypatch.setenv("DOCSPEC_TINYTEX", str(bindir))
    assert paths.resolve_xelatex() == bindir / exe


def test_resolve_fonts_dir_prefers_data_dir(monkeypatch, tmp_path):
    fdir = tmp_path / "fonts"
    fdir.mkdir()
    for f in paths.REQUIRED_FONT_FILES:
        (fdir / f).write_bytes(b"x")
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    assert paths.resolve_fonts_dir() == fdir


# ── sha256 驗證下載 ───────────────────────────────────────────────

def test_download_verifies_sha256(monkeypatch, tmp_path):
    payload = b"tinytex-bytes"
    good = hashlib.sha256(payload).hexdigest()

    class _Resp:
        def __init__(self):
            self._b = payload
        def read(self, n=-1):
            b, self._b = self._b, b""
            return b
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", lambda *a, **k: _Resp())
    dest = tmp_path / "pkg.exe"
    assert setup_cmd._download("http://x", dest, good) is True
    assert dest.read_bytes() == payload
    # 壞 sha → 失敗、不留半成品
    dest2 = tmp_path / "pkg2.exe"
    assert setup_cmd._download("http://x", dest2, "00" * 32) is False
    assert not dest2.exists()
    assert not (tmp_path / "pkg2.exe.part").exists()


# ── TinyTeX 解壓正規化（跨平台目錄名；T2 回歸）──────────────────────

def _tlmgr_name() -> str:
    return "tlmgr.bat" if paths.os.name == "nt" else "tlmgr"


def _make_tinytex_tar(tar_path, top_name: str) -> None:
    """造一個內含 <top_name>/bin/<plat>/<tlmgr> 的 tar.gz（模擬官方 release）。"""
    payload = b"#!stub tlmgr\n"
    with tarfile.open(tar_path, "w:gz") as tf:
        info = tarfile.TarInfo(f"{top_name}/bin/x86_64-linux/{_tlmgr_name()}")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))


def test_extract_tar_normalizes_hidden_dot_tinytex(monkeypatch, tmp_path):
    """Linux/mac 官方 tar 解出隱藏的 .TinyTeX/——須正規化成 data_dir/tinytex（T2 bug 回歸）。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    tar_path = tmp_path / "tinytex.tar.gz"
    _make_tinytex_tar(tar_path, ".TinyTeX")  # ← 點前綴＝Linux/mac 實況
    root = paths.tinytex_root()
    assert setup_cmd._extract_tar(tar_path, root) is True
    assert paths.tlmgr_path(root) is not None
    assert not (tmp_path / ".TinyTeX").exists()  # 已搬走、不留殘層


def test_extract_tar_normalizes_plain_tinytex(monkeypatch, tmp_path):
    """無點的 TinyTeX/（Windows SFX 風格）也走同一條 normalize。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    tar_path = tmp_path / "tinytex.tar.gz"
    _make_tinytex_tar(tar_path, "TinyTeX")
    root = paths.tinytex_root()
    assert setup_cmd._extract_tar(tar_path, root) is True
    assert paths.tlmgr_path(root) is not None


def test_tex_packages_use_tl_package_names_not_sty_filenames():
    """stfloats.sty 由 TL 套件 sttools 提供——清單須用 sttools，否則 tlmgr install
    報「not present in repository」整批回非零（Linux 真測 T2 抓到）。"""
    assert "stfloats" not in setup_cmd._TEX_PACKAGES
    assert "sttools" in setup_cmd._TEX_PACKAGES


# ── release asset 解析（不寫死檔名）────────────────────────────────

def test_resolve_asset_matches_by_substr_and_tag(monkeypatch):
    fake = {"assets": [
        {"name": "TinyTeX-0-windows-v2026.06.exe", "browser_download_url": "u0"},
        {"name": "TinyTeX-1-windows-v2026.06.exe", "browser_download_url": "u1"},
        {"name": "TinyTeX-1-linux-x86_64-v2026.06.tar.xz", "browser_download_url": "ul"},
    ]}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(fake).encode()

    monkeypatch.setattr(setup_cmd.json, "load", lambda resp: fake)
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", lambda *a, **k: _Resp())
    got = setup_cmd._resolve_asset("v2026.06", "TinyTeX-1-windows-")
    assert got == ("u1", "TinyTeX-1-windows-v2026.06.exe")


def test_manifest_has_current_platform():
    # 本機平台必須在 manifest（否則 setup 直接擋）
    assert setup_cmd._platform_key() in setup_cmd._MANIFEST["assets"]


# ── 字型 copy（冪等）──────────────────────────────────────────────

def test_ensure_fonts_copies_from_dev_source(monkeypatch, tmp_path):
    src = tmp_path / "src_fonts"
    src.mkdir()
    for f in paths.REQUIRED_FONT_FILES:
        (src / f).write_bytes(b"font")
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: src)
    assert setup_cmd._ensure_fonts(force=False) is True
    for f in paths.REQUIRED_FONT_FILES:
        assert (tmp_path / "dd" / "fonts" / f).is_file()
    # 冪等：再跑一次仍 True（跳過）
    assert setup_cmd._ensure_fonts(force=False) is True


def test_ensure_fonts_no_download_reports_missing(monkeypatch, tmp_path, capsys):
    # 無本地來源 + --no-download → 中止、清楚報缺，絕不嘗試下載。
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: None)
    assert setup_cmd._ensure_fonts(force=False, no_download=True) is False
    assert "--no-download" in capsys.readouterr().err


# ── 字型 manifest 完整性 ──────────────────────────────────────────

def test_font_manifest_covers_all_required_files():
    # 每個 REQUIRED_FONT_FILES 都有一個下載來源（否則乾淨機器永遠補不齊）。
    targets = {
        t for (_v, _u, _s, members) in setup_cmd._FONT_MANIFEST.values()
        for t in members.values()
    }
    assert set(paths.REQUIRED_FONT_FILES) == targets


def test_font_manifest_entries_well_formed():
    for key, entry in setup_cmd._FONT_MANIFEST.items():
        version, url, sha, members = entry
        assert version and isinstance(version, str)
        assert url.startswith("https://")
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
        assert members and all(members.values())


def test_font_file_source_reverse_index_consistent():
    # 反查表覆蓋所有 required，且每個指回真實 manifest key。
    for f in paths.REQUIRED_FONT_FILES:
        k = setup_cmd._FONT_FILE_SOURCE[f]
        assert k in setup_cmd._FONT_MANIFEST


# ── zip member 解壓（挑檔）──────────────────────────────────────────

def _make_zip(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_extract_fonts_from_zip_picks_members(tmp_path):
    arc = tmp_path / "a.zip"
    _make_zip(arc, {
        "OTF/Wanted-Regular.otf": b"R",
        "OTF/Wanted-Bold.otf": b"B",
        "OTF/Ignored.otf": b"X",
        "LICENSE.md": b"ofl",
    })
    dest = tmp_path / "fonts"
    dest.mkdir()
    n = setup_cmd._extract_fonts_from_zip(
        arc,
        {"OTF/Wanted-Regular.otf": "W-Regular.otf",
         "OTF/Wanted-Bold.otf": "W-Bold.otf"},
        dest,
    )
    assert n == 2
    assert (dest / "W-Regular.otf").read_bytes() == b"R"
    assert (dest / "W-Bold.otf").read_bytes() == b"B"
    assert not (dest / "Ignored.otf").exists()


def test_extract_fonts_from_zip_skips_absent_member(tmp_path, capsys):
    arc = tmp_path / "a.zip"
    _make_zip(arc, {"OTF/Present.otf": b"P"})
    dest = tmp_path / "fonts"
    dest.mkdir()
    n = setup_cmd._extract_fonts_from_zip(
        arc, {"OTF/Absent.otf": "X.otf"}, dest)
    assert n == 0
    assert "not found in zip" in capsys.readouterr().err


# ── 下載主路（全 mock：sha 驗證 + 挑檔 + 冪等）──────────────────────

def _patch_font_manifest_with_fake_zip(monkeypatch, tmp_path):
    """把 _FONT_MANIFEST 換成單一假來源，並 mock urlopen 吐該 zip 的 bytes。"""
    members_inner = {"DIR/Foo-Regular.otf": b"reg", "DIR/Foo-Bold.otf": b"bold"}
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        for n, d in members_inner.items():
            zf.writestr(n, d)
    zip_bytes = zbuf.getvalue()
    sha = hashlib.sha256(zip_bytes).hexdigest()

    fake = {"fake-src": (
        "9.9", "https://example.invalid/fake.zip", sha,
        {"DIR/Foo-Regular.otf": "Foo-Regular.otf",
         "DIR/Foo-Bold.otf": "Foo-Bold.otf"},
    )}
    monkeypatch.setattr(setup_cmd, "_FONT_MANIFEST", fake)
    monkeypatch.setattr(
        setup_cmd, "_FONT_FILE_SOURCE",
        {"Foo-Regular.otf": "fake-src", "Foo-Bold.otf": "fake-src"})
    monkeypatch.setattr(
        paths, "REQUIRED_FONT_FILES", ("Foo-Regular.otf", "Foo-Bold.otf"))

    class _Resp:
        def __init__(self): self._b = zip_bytes
        def read(self, n=-1):
            b, self._b = self._b, b""
            return b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen",
                        lambda *a, **k: _Resp())
    return zip_bytes, sha


def test_ensure_fonts_downloads_and_extracts(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: None)  # 無本地→走下載
    _patch_font_manifest_with_fake_zip(monkeypatch, tmp_path)

    assert setup_cmd._ensure_fonts(force=False) is True
    fdir = tmp_path / "dd" / "fonts"
    assert (fdir / "Foo-Regular.otf").read_bytes() == b"reg"
    assert (fdir / "Foo-Bold.otf").read_bytes() == b"bold"


def test_ensure_fonts_download_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: None)
    _patch_font_manifest_with_fake_zip(monkeypatch, tmp_path)
    assert setup_cmd._ensure_fonts(force=False) is True

    # 第二次：字型已齊 → urlopen 一被呼叫就炸（證明走跳過、不重下載）
    def _boom(*a, **k):
        raise AssertionError("不該再下載")
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _boom)
    assert setup_cmd._ensure_fonts(force=False) is True


def test_ensure_fonts_download_bad_sha_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: None)
    _zip, _sha = _patch_font_manifest_with_fake_zip(monkeypatch, tmp_path)
    # 竄改 manifest 的 sha → 下載後驗證必敗
    key, (v, u, _s, m) = next(iter(setup_cmd._FONT_MANIFEST.items()))
    monkeypatch.setattr(setup_cmd, "_FONT_MANIFEST", {key: (v, u, "00" * 32, m)})
    assert setup_cmd._ensure_fonts(force=False) is False
    assert "sha256 verification failed" in capsys.readouterr().err


def test_ensure_fonts_local_fast_path_skips_download(monkeypatch, tmp_path):
    # 本地來源齊 → 走快路 copy，urlopen 一被碰就炸。
    src = tmp_path / "local"
    src.mkdir()
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(
        paths, "REQUIRED_FONT_FILES", ("Foo-Regular.otf", "Foo-Bold.otf"))
    for f in paths.REQUIRED_FONT_FILES:
        (src / f).write_bytes(b"local")
    monkeypatch.setattr(paths, "_bundled_fonts_dir", lambda: src)

    def _boom(*a, **k):
        raise AssertionError("有本地來源不該下載")
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _boom)
    assert setup_cmd._ensure_fonts(force=False) is True
    assert (tmp_path / "dd" / "fonts" / "Foo-Regular.otf").read_bytes() == b"local"


# ── tex.lock ──────────────────────────────────────────────────────

def test_write_lock_records_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    tlmgr = tmp_path / "tinytex" / "bin" / "plat" / "tlmgr"
    tlmgr.parent.mkdir(parents=True)
    tlmgr.write_text("x", encoding="utf-8")
    setup_cmd._write_lock(tlmgr, tlmgr.parent / "xelatex", ["xecjk", "fontspec"])
    lock = json.loads(paths.tex_lock_path().read_text(encoding="utf-8"))
    assert lock["tinytex_tag"] == setup_cmd._MANIFEST["tag"]
    assert lock["tlmgr_packages"] == ["xecjk", "fontspec"]
    assert lock["fonts"] == list(paths.REQUIRED_FONT_FILES)


# ── pandoc（受控 binary：平台 key／解壓挑主程式／下載冪等／resolve 優先）─────

def test_pandoc_manifest_covers_current_platform():
    pkey = setup_cmd._pandoc_platform_key()
    assert pkey is not None
    assert pkey in setup_cmd._PANDOC_MANIFEST["assets"]


def test_pandoc_manifest_entries_well_formed():
    for pkey, (name, sha) in setup_cmd._PANDOC_MANIFEST["assets"].items():
        assert name.endswith((".zip", ".tar.gz")), pkey
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), pkey


def _make_pandoc_tar(tar_path, exe_rel: str) -> None:
    """tar.gz：pandoc 主程式 + lua/server 誘餌（驗證只挑 basename 對的那個）。"""
    with tarfile.open(tar_path, "w:gz") as tf:
        for rel, body in [(exe_rel, b"PANDOC"),
                          ("pandoc-3.10/bin/pandoc-lua", b"LUA"),
                          ("pandoc-3.10/bin/pandoc-server", b"SRV")]:
            info = tarfile.TarInfo(rel)
            info.size = len(body)
            tf.addfile(info, io.BytesIO(body))


def _make_pandoc_zip(zip_path, exe_rel: str) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(exe_rel, b"PANDOC")
        zf.writestr("pandoc-3.10/pandoc-lua", b"LUA")  # 誘餌


def test_extract_pandoc_binary_from_tar_picks_main_exe(tmp_path):
    tar_path = tmp_path / "p.tar.gz"
    _make_pandoc_tar(tar_path, "pandoc-3.10/bin/pandoc")
    target = tmp_path / "out" / "pandoc"
    assert setup_cmd._extract_pandoc_binary(tar_path, "pandoc", target) is True
    assert target.read_bytes() == b"PANDOC"  # 不是 lua/server


def test_extract_pandoc_binary_from_zip_picks_main_exe(tmp_path):
    zip_path = tmp_path / "p.zip"
    _make_pandoc_zip(zip_path, "pandoc-3.10/pandoc.exe")
    target = tmp_path / "out" / "pandoc.exe"
    assert setup_cmd._extract_pandoc_binary(zip_path, "pandoc.exe", target) is True
    assert target.read_bytes() == b"PANDOC"


def test_ensure_pandoc_downloads_extracts_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    exe_name = paths.pandoc_exe_name()
    pkey = setup_cmd._pandoc_platform_key()
    asset_name, _sha = setup_cmd._PANDOC_MANIFEST["assets"][pkey]
    archive = tmp_path / asset_name
    if asset_name.endswith(".zip"):
        _make_pandoc_zip(archive, f"pandoc-3.10/{exe_name}")
    else:
        _make_pandoc_tar(archive, f"pandoc-3.10/bin/{exe_name}")
    payload = archive.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(setup_cmd, "_PANDOC_MANIFEST",
                        {"tag": "3.10", "assets": {pkey: (asset_name, sha)}})

    class _Resp:
        def __init__(self): self._b = payload
        def read(self, n=-1):
            b, self._b = self._b, b""
            return b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", lambda *a, **k: _Resp())

    assert setup_cmd._ensure_pandoc(force=False, no_download=False) is True
    target = paths.pandoc_dir() / exe_name
    assert target.read_bytes() == b"PANDOC"

    # 第二次：已在 → 不再下載（urlopen 一被碰就炸）
    def _boom(*a, **k):
        raise AssertionError("已有 pandoc 不該重下載")
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _boom)
    assert setup_cmd._ensure_pandoc(force=False, no_download=False) is True


def test_ensure_pandoc_no_download_when_absent_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    assert setup_cmd._ensure_pandoc(force=False, no_download=True) is False
    assert "no pandoc in data_dir" in capsys.readouterr().err


def test_resolve_pandoc_prefers_managed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.delenv("DOCSPEC_PANDOC", raising=False)
    pdir = tmp_path / "pandoc"
    pdir.mkdir()
    managed = pdir / paths.pandoc_exe_name()
    managed.write_text("x", encoding="utf-8")
    assert paths.resolve_pandoc() == str(managed)


def test_write_lock_records_pandoc(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    tlmgr = tmp_path / "tinytex" / "bin" / "plat" / "tlmgr"
    tlmgr.parent.mkdir(parents=True)
    tlmgr.write_text("x", encoding="utf-8")
    setup_cmd._write_lock(tlmgr, tlmgr.parent / "xelatex", ["xecjk"], "/p/pandoc")
    lock = json.loads(paths.tex_lock_path().read_text(encoding="utf-8"))
    assert lock["pandoc_tag"] == setup_cmd._PANDOC_MANIFEST["tag"]
    assert lock["pandoc_path"] == "/p/pandoc"


# ── drawio（選用受控可攜版：平台 key／manifest 形狀／解壓／下載冪等／resolve）─────

def test_drawio_manifest_covers_current_platform():
    pkey = setup_cmd._pandoc_platform_key()
    assert pkey is not None
    assert pkey in setup_cmd._DRAWIO_MANIFEST["assets"]


def test_drawio_manifest_entries_well_formed():
    for pkey, (name, sha) in setup_cmd._DRAWIO_MANIFEST["assets"].items():
        assert name.endswith((".zip", ".AppImage")), pkey
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), pkey
    # tag 不含 'v' 前綴（URL 才補 v）
    assert not setup_cmd._DRAWIO_MANIFEST["tag"].startswith("v")


def _make_drawio_archive(path, pkey: str) -> None:
    """造出對應平台的假 draw.io 可攜資產（windows/darwin=zip、linux=AppImage 單檔）。"""
    if pkey == "windows":
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("draw.io.exe", b"DRAWIO")
            zf.writestr("resources/app.asar", b"x")  # 誘餌：整包 app
    elif pkey.startswith("darwin"):
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("draw.io.app/Contents/MacOS/draw.io", b"DRAWIO")
            zf.writestr("draw.io.app/Contents/Info.plist", b"x")
    else:  # linux: AppImage 單檔
        path.write_bytes(b"DRAWIO-APPIMAGE")


def test_ensure_drawio_downloads_extracts_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    pkey = setup_cmd._pandoc_platform_key()
    asset_name, _sha = setup_cmd._DRAWIO_MANIFEST["assets"][pkey]
    archive = tmp_path / asset_name
    _make_drawio_archive(archive, pkey)
    payload = archive.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(setup_cmd, "_DRAWIO_MANIFEST",
                        {"tag": "30.2.4", "assets": {pkey: (asset_name, sha)}})
    # Linux runtime 檢查不要真跑 ldconfig/apt
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)

    class _Resp:
        def __init__(self): self._b = payload
        def read(self, n=-1):
            b, self._b = self._b, b""
            return b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", lambda *a, **k: _Resp())

    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True
    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    assert paths.drawio_managed_binary(plat).is_file()

    # 第二次：已在 → 不再下載
    def _boom(*a, **k):
        raise AssertionError("已有 draw.io 不該重下載")
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _boom)
    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True


def test_ensure_drawio_no_download_when_absent_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)
    assert setup_cmd._ensure_drawio(force=False, no_download=True) is False
    assert "no draw.io in data_dir" in capsys.readouterr().err


def test_resolve_drawio_prefers_managed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.delenv("DOCSPEC_DRAWIO", raising=False)
    managed = paths.drawio_managed_binary()
    managed.parent.mkdir(parents=True, exist_ok=True)
    managed.write_text("x", encoding="utf-8")
    assert paths.resolve_drawio() == str(managed)


def test_write_lock_records_drawio(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(setup_cmd, "_drawio_version", lambda b: "30.2.4")
    tlmgr = tmp_path / "tinytex" / "bin" / "plat" / "tlmgr"
    tlmgr.parent.mkdir(parents=True)
    tlmgr.write_text("x", encoding="utf-8")
    setup_cmd._write_lock(tlmgr, None, ["xecjk"], "/p/pandoc", "/t/typst", "/d/drawio")
    lock = json.loads(paths.tex_lock_path().read_text(encoding="utf-8"))
    assert lock["drawio_tag"] == setup_cmd._DRAWIO_MANIFEST["tag"]
    assert lock["drawio_path"] == "/d/drawio"
    assert lock["drawio_installed_version"] == "30.2.4"   # C1：記實際自報版本


# ── drawio 版本擔保（C1：不只信檔案存在；舊版殘檔會拒 -x -f）─────────────

def test_drawio_version_strips_electron_env(monkeypatch):
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["env"] = kw.get("env", {})

        class R:
            stdout = "30.2.4\n"
            stderr = ""
        return R()

    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    monkeypatch.setattr(setup_cmd.subprocess, "run", fake_run)
    assert setup_cmd._drawio_version("draw.io") == "30.2.4"
    assert "ELECTRON_RUN_AS_NODE" not in seen["env"]   # 必須剝掉，否則 Electron 當 node 跑


def test_ensure_drawio_keeps_mismatched_but_above_floor(monkeypatch, tmp_path):
    """drawio-min-version-floor：版本 ≠ pinned 但 ≥ 門檻（v24.16.0 ≥ (24,0,0)）→ 留著、不重抓。
    （舊行為＝精確匹配會重抓；新行為＝門檻內就用，免 churn、不降級。）"""
    target = tmp_path / "drawio" / "draw.io.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"v24 binary, works fine")
    monkeypatch.setattr(setup_cmd, "_pandoc_platform_key", lambda: "windows")
    monkeypatch.setattr(paths, "drawio_managed_binary", lambda plat=None: target)
    monkeypatch.setattr(setup_cmd, "_drawio_version", lambda b: "24.16.0")  # ≠ pinned 30.2.4，但 ≥ 門檻
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)
    dl: list = []
    monkeypatch.setattr(setup_cmd, "_download", lambda *a: dl.append(a) or True)
    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True
    assert not dl, "≥ floor 即使 ≠ pinned 也不該重抓"


def test_ensure_drawio_skips_when_version_matches(monkeypatch, tmp_path):
    target = tmp_path / "drawio" / "draw.io.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"good binary")
    monkeypatch.setattr(setup_cmd, "_pandoc_platform_key", lambda: "windows")
    monkeypatch.setattr(paths, "drawio_managed_binary", lambda plat=None: target)
    monkeypatch.setattr(setup_cmd, "_drawio_version",
                        lambda b: setup_cmd._DRAWIO_MANIFEST["tag"])
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)
    dl: list = []
    monkeypatch.setattr(setup_cmd, "_download", lambda *a: dl.append(a) or True)
    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True
    assert not dl, "matching version must skip download"


# ── drawio 最小版本門檻（drawio-min-version-floor）─────────────────

def _put_managed_drawio(tmp_path, monkeypatch, body=b"stub"):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)
    pkey = setup_cmd._pandoc_platform_key()
    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    binp = paths.drawio_managed_binary(plat)
    binp.parent.mkdir(parents=True, exist_ok=True)
    binp.write_bytes(body)
    return binp


def _no_download(*a, **k):
    raise AssertionError("不該下載")


def test_ensure_drawio_keeps_version_at_or_above_floor(monkeypatch, tmp_path):
    """版本 ≥ 門檻（含 = pinned、含比 pinned 更新）→ 留著、不重抓、不降級。"""
    _put_managed_drawio(tmp_path, monkeypatch)
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _no_download)
    for ver in ("30.2.4", "31.5.0"):          # == pinned 與 > pinned 都要留
        monkeypatch.setattr(setup_cmd, "_drawio_version", lambda b, _v=ver: _v)
        assert setup_cmd._ensure_drawio(force=False, no_download=False) is True


def test_ensure_drawio_keeps_unprobeable(monkeypatch, tmp_path):
    """版本探不到（None）→ 留著（探測失敗≠壞 binary，可能 headless），不重抓。"""
    _put_managed_drawio(tmp_path, monkeypatch)
    monkeypatch.setattr(setup_cmd, "_drawio_version", lambda b: None)
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _no_download)
    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True


def test_ensure_drawio_redownloads_below_floor(monkeypatch, tmp_path):
    """確實探到且 < 門檻 → 重抓 pinned。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "dd")
    monkeypatch.setattr(setup_cmd, "_check_linux_drawio_runtime", lambda **k: None)
    pkey = setup_cmd._pandoc_platform_key()
    asset_name, _sha = setup_cmd._DRAWIO_MANIFEST["assets"][pkey]
    archive = tmp_path / asset_name
    _make_drawio_archive(archive, pkey)
    payload = archive.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(setup_cmd, "_DRAWIO_MANIFEST",
                        {"tag": "30.2.4", "assets": {pkey: (asset_name, sha)}})
    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    binp = paths.drawio_managed_binary(plat)
    binp.parent.mkdir(parents=True, exist_ok=True)
    binp.write_bytes(b"old")
    monkeypatch.setattr(setup_cmd, "_drawio_version", lambda b: "23.0.0")   # < (24,0,0)
    called = []

    class _Resp:
        def __init__(self): self._b = payload
        def read(self, n=-1):
            b, self._b = self._b, b""
            return b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _urlopen(*a, **k):
        called.append(1)
        return _Resp()
    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", _urlopen)
    assert setup_cmd._ensure_drawio(force=False, no_download=False) is True
    assert called, "版本低於門檻應重抓 pinned"


def test_version_tuple_parsing():
    assert setup_cmd._version_tuple("30.2.4") == (30, 2, 4)
    assert setup_cmd._version_tuple("v24.16.0") == (24, 16, 0)
    assert setup_cmd._version_tuple(None) is None
    assert setup_cmd._version_tuple("garbage") is None
