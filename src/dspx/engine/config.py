"""專案 config（<planning-home>/config.yaml）載入。

規則（spec: project-config）：
- 檔案缺席 → 回傳預設值，不報錯（verbose 時提示）。
- 未知鍵 → 警告、忽略，不報錯。
- YAML 格式錯誤 → 拋 ConfigError（含路徑與行號），絕不回退預設值。
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Callable

import yaml

CONFIG_FILE_NAME = "config.yaml"

DEFAULTS: dict = {
    "schema": "section-driven",
    "language": "zh-TW",
    "docs_layout": "flat",          # flat（<article>_latest.md＋archive/<article>_v<N>.md，預設）| per-article（每篇子夾）
    "purpose": "",                  # metadata：整座森林/專案的整體目標（一兩句，authored）；develop 投影、guide 可見
    "audit": {
        "core": ["logic", "completeness", "clarity", "discipline", "consistency"],
        "packs": {},
    },
    # autonomy 旋鈕：唯一活的是 publish＝human 鎖（不可逆板機在人手上，引擎強制）。
    # 其餘 per-skill 自主度＝未來功能；現在只留 publish，其他旋鈕鍵＝未知鍵 warn。
    "autonomy": {
        "publish": "human",
    },
    # export：md→PDF 終端投影設定（指令 `docspec export`）。layout/export 層、非 schema artifact。
    # 現定版＝Typst 預設（docspec-typst 自帶模板 + 受控 typst binary、原生 CJK），另有 journal 軌
    # （BYO LaTeX、emit-only：產 .tex 不自編）；舊 docspec-cas/xelatex latex 軌已退場。
    #   formats＝預設輸出格式（目前僅 pdf）；engine＝預設 render 引擎（空＝typst）；template＝
    #   journal 軌的 BYO 模板夾（空＝用內建 journal adapter）。
    # 子鍵採「缺鍵給預設」（command 端再 merge），故此處頂層整塊被 config 覆寫亦不致缺鍵。
    #   format＝結構化「格式旋鈕」（旋鈕 schema 見 format_config.py）：agent 只填驗證過的
    #   值，壞值/幻覺在驗證階段就被擋、永不進編譯。此處頂層留空 dict＝全用
    #   format_config.DEFAULT_FORMAT 預設（＝現狀）。
    #   專案級預設寫在這；per-article 覆寫＝`docspec export --format-config <file>`。
    "export": {
        "formats": ["pdf"],
        "template": "",
        "format": {},
        "profile": "default",   # 文類版面 profile（default|academic|paper|manual|essay|novel）；`--profile` per-export 覆寫
    },
}

# export.profile 合法文類（Typst 模板依此切換字型/段落/邊界/標題/場景分隔）。
EXPORT_PROFILES = ("default", "academic", "paper", "manual", "essay", "novel")

# docs_layout 封閉 enum（corpus-fail-loud-batch D1）：非法值（typo/大小寫/空白）一律
# ConfigError fail-loud——曾實測 `falt` 靜默切佈局並連鎖抹帳本，絕不 fallback。
DOCS_LAYOUTS = ("flat", "per-article")

KNOWN_KEYS = frozenset(DEFAULTS)

AUTONOMY_KNOBS = ("publish",)


def lang_subtag(language: str | None) -> str:
    """BCP-47 語言標籤 → ISO-639 base subtag（`zh-TW` → `zh`、`en-US` → `en`）。
    typst `#set text(lang: …)` 與出版軌（changelog 在地化）吃 base subtag；把整個 `zh-TW`
    直接丟進 typst lang 是錯的（預設 `zh-TW` 本身就不是合法 typst lang）。空/壞 → `zh`（house 預設）。"""
    if not language:
        return "zh"
    base = str(language).replace("_", "-").split("-", 1)[0].strip().lower()
    return base or "zh"


def detect_language(text: str, fallback: str | None = None) -> str:
    """從交付物內容偵測文件語言 base subtag（`zh`/`en`），確定性、無魔術門檻。

    規則：數 CJK 表意字（`一`–`鿿` 區段）vs ASCII 字母（A–Z/a–z）。CJK 多數 → `zh`、
    否則 `en`。中文學術文件即便夾大量英文術語，表意字仍佔多數；英文文件 CJK≈0。
    無可判字元（空/全符號/全數字）→ 回 `lang_subtag(fallback)`（house 預設 zh）。

    用於：publish changelog 在地化、export 的 lang/region——皆「文件語言」而非「專案 config」，
    因為單一專案級 config.language 常忘了改（英文交付物洩中文表頭）。"""
    cjk = 0
    latin = 0
    for ch in text:
        if "一" <= ch <= "鿿":
            cjk += 1
        elif ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            latin += 1
    if cjk == 0 and latin == 0:
        return lang_subtag(fallback)
    return "zh" if cjk >= latin else "en"


def region_for(lang: str, config_language: str | None = None) -> str:
    """文件語言 base subtag → typst region（CJK 標點位置/在地化）。

    `zh` → house Traditional 預設 `tw`，除非 config.language 帶同 base 的明確 region
    （如 `zh-CN` → `cn`）；`en` → `us`；其餘 → base 本身。保留思源宋 Traditional house 預設、
    又尊重明設簡體專案。"""
    if lang == "zh":
        if config_language:
            parts = str(config_language).replace("_", "-").split("-")
            if len(parts) >= 2 and parts[0].strip().lower() == "zh" and parts[1].strip():
                return parts[1].strip().lower()
        return "tw"
    if lang == "en":
        return "us"
    return lang


class ConfigError(Exception):
    """config.yaml 存在但無法解析。"""


def _default_warn(message: str) -> None:
    sys.stderr.write(message + "\n")


def load_config(
    planning_home: Path,
    *,
    verbose: bool = False,
    warn: Callable[[str], None] | None = None,
) -> dict:
    """載入 planning home 的 config.yaml，回傳完整 config（含預設值補齊）。"""
    warn = warn or _default_warn
    path = planning_home / CONFIG_FILE_NAME
    config = copy.deepcopy(DEFAULTS)

    if not path.is_file():
        if verbose:
            warn(f"docspec: {path} not found, using default config")
        return config

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        position = ""
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            position = f" (line {mark.line + 1})"
        raise ConfigError(f"failed to parse config: {path}{position}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"failed to parse config: {path} (top level must be a key-value mapping)")

    for key, value in data.items():
        if key not in KNOWN_KEYS:
            warn(f"docspec: config has unknown key '{key}' (ignored)")
            continue
        if key == "autonomy":
            config[key] = _merge_autonomy(value, path, warn)
        elif key == "docs_layout":
            config[key] = _validate_docs_layout(value, path)
        else:
            config[key] = value
    return config


def _validate_docs_layout(value: object, path: Path) -> str:
    """docs_layout 封閉 enum 驗證：只收精確 `flat`/`per-article`（含大小寫/空白變體皆拒）。"""
    if value in DOCS_LAYOUTS:
        return value  # type: ignore[return-value]
    raise ConfigError(
        f"config error: {path} (docs_layout is \"{value}\" but must be one of: "
        f"{' | '.join(DOCS_LAYOUTS)} — the engine never silently falls back to a layout)"
    )


def _merge_autonomy(value: object, path: Path, warn: Callable[[str], None]) -> dict:
    """autonomy 採逐旋鈕合併（部分指定 → 其餘預設）；publish 鎖定 human。"""
    if not isinstance(value, dict):
        raise ConfigError(f"config error: {path} (autonomy must be a key-value mapping)")
    merged = dict(DEFAULTS["autonomy"])
    for knob, setting in value.items():
        if knob not in AUTONOMY_KNOBS:
            warn(f"docspec: autonomy has unknown knob '{knob}' (ignored)")
            continue
        merged[knob] = setting
    if merged["publish"] != "human":
        raise ConfigError(
            f"config error: {path} (autonomy.publish is locked to human, "
            f"cannot be changed to '{merged['publish']}' — the trigger for "
            f"irreversible operations must stay with the human)"
        )
    return merged
