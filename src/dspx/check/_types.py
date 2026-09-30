"""check：資料形狀（dataclasses）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IdRecord:
    """一個 id 的歸屬。"""

    id: str
    section: str
    kind: str        # concept | decision | history
    status: str | None = None


@dataclass
class Index:
    """check 全綠時產出的索引脊椎。"""

    ids: dict[str, IdRecord] = field(default_factory=dict)        # id -> 歸屬
    sections: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    index: Index
    warnings: list[str] = field(default_factory=list)   # 非阻塞提示（不影響 ok / exit code）
    # 軟體領域（software/）的錯誤另列：文件管文件、軟體管軟體（2026/09/30 裁定）。
    # 不影響 ok（文件的狀態與定版不被軟體擋）；`docspec check` 照樣回報並反映在結束碼。
    software_errors: list[str] = field(default_factory=list)
