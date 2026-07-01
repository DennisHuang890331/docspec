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
