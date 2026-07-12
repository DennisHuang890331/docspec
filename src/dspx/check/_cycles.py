"""check：循環偵測（③，supersedes / governs 鏈各自 DFS）。"""

from __future__ import annotations

from dspx.engine.model import Leaf


def _detect_supersede_cycle(leaves: list[Leaf]) -> list[str]:
    # 圖：decision id -> 它 supersedes 的 id
    graph: dict[str, list[str]] = {}
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            eid = e.get("id")
            if not eid:
                continue
            sup = e.get("supersedes")
            graph.setdefault(str(eid), [])
            if sup:
                graph[str(eid)].append(str(sup))
    return _find_cycle(graph, "supersedes")


def _detect_governs_cycle(leaves: list[Leaf]) -> list[str]:
    # 圖：concept id -> 它 governed-by 解析到的 concept id（跨樹環 A 治 B、B 治 A 要擋）
    graph: dict[str, list[str]] = {}
    for leaf in leaves:
        if leaf.concept is None:
            continue
        cid = leaf.concept.get("id")
        if not cid:
            continue
        targets = leaf.concept.get("governed-by") or []
        if not isinstance(targets, list):
            targets = [targets]
        graph[str(cid)] = [str(t) for t in targets]
    return _find_cycle(graph, "governs")


def _find_cycle(graph: dict[str, list[str]], label: str) -> list[str]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    errors: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        for nxt in graph.get(node, []):
            if nxt not in color:  # 指到圖外（死引用已另報）
                continue
            if color[nxt] == GRAY:
                # 只報真正成環的節點：從 nxt（回邊指向、必在 stack 上）首次出現處起，
                # 砍掉前面那段「進入環的引線」（DFS 從別處走進環的 lead-in，本身不在環裡，
                # 否則深森林裡會把無辜的下游節點印在環路徑最前端、誤導讀者）。
                path = stack + [node]
                start = path.index(nxt)
                cycle = " → ".join(path[start:] + [nxt])
                errors.append(f"{label} cycle: {cycle}")
            elif color[nxt] == WHITE:
                visit(nxt, stack + [node])
        color[node] = BLACK

    for n in graph:
        if color[n] == WHITE:
            visit(n, [])
    return errors
