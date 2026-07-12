"""export 設定合成：專案 config 的 export 區塊、旋鈕表合併、pandoc 路徑 probe。"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.engine import paths
from dspx.engine.config import DEFAULTS
from dspx.typeset.format_config import FormatConfigError, validate_format_config

# pandoc 輸入格式：標準 markdown 但關掉兩個擴充（兩軌共用單一常數）：
#   -citations         : @token（MPE @import、@提及）不被當成引用文獻。
#   -yaml_metadata_block: 文件中段的 --- ... --- 不被當 mid-doc YAML block（台中港風格
#                          用 --- 當 section divider，夾在兩個 --- 間的散文被 pandoc
#                          嘗試解析為 YAML 而失敗）；關掉後 --- 一律轉 thematic break。
#
# ★D7（issue #22）`+lists_without_preceding_blankline`＝**經實測否決、不採用**：design 宣稱它治
#   兩個 false-positive，但對 docspec 受控 pandoc 實測結果**相反**——① 硬換行散文續行行首 `- ` 在
#   現狀（不開擴充）本就正確保留為散文，開了擴充**反而**被切成 bullet list（引入 false-positive）；
#   ② 行首 `2026. ` 自成段落時在開/不開擴充下**皆**被當有序清單（擴充治不了）。export 用的就是這顆
#   受控 pandoc，故加此擴充只會製造 design 想防的 regression。保持現狀＝已正確處理 ①；② 需源端
#   escape（design 列為 future 的 lint 兜底），非本常數所能解，不在此硬塞。實測見 commit 說明。
_PANDOC_FROM = "markdown-citations-yaml_metadata_block"


# ── 相依 probe（soft dependency）────────────────────────────────────

def _pandoc_path() -> str | None:
    """找得到的 pandoc（委派 dspx.engine.paths；優先 pypandoc 自帶 binary、退回系統 PATH）。"""
    return paths.resolve_pandoc()


# ── 設定合併（缺鍵給預設）────────────────────────────────────────

def _export_config(config: dict) -> dict:
    """export 設定：頂層整塊可被 config 覆寫，故在此 merge 回預設、確保子鍵齊全。"""
    base = DEFAULTS["export"]
    econf = {**base, **(config.get("export") or {})}
    return econf


def _section_merge(base: dict, over: dict) -> dict:
    """旋鈕表逐區塊淺合併（over 同名區塊鍵覆蓋 base，其餘區塊保留 base）。"""
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for section, body in over.items():
        if isinstance(body, dict) and isinstance(out.get(section), dict):
            out[section] = {**out[section], **body}
        else:
            out[section] = body
    return out


def _resolve_format(econf: dict, format_config_file: str | None) -> dict:
    """合成最終旋鈕表並驗證：專案 config 的 export.format（預設）＋ --format-config 檔覆寫。

    回**已驗證**的完整旋鈕表（可直接 compile）。任一層含不合法值 → 拋 FormatConfigError
    （由 run() 攔成清楚錯誤、export 非零、不進 render——壞值/幻覺永不進 typst）。
    """
    raw = dict(econf.get("format") or {})
    if format_config_file is not None:
        path = Path(format_config_file)
        if not path.is_file():
            raise FormatConfigError(f"the file given to --format-config does not exist: {path}")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise FormatConfigError(f"failed to parse the --format-config file ({path}): {exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise FormatConfigError(f"the --format-config file's top level must be a key-value mapping: {path}")
        if "format" in data and isinstance(data["format"], dict):
            data = data["format"]
        raw = _section_merge(raw, data)
    return validate_format_config(raw)
