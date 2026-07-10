"""森林地圖（derive，不另存）：把多棵樹的 root 文件＋跨樹 governed-by 關係攤成一張地圖。

關係只活一處＝`concept.governed-by`（單向、子→父）。這裡的階層/平行/一句話**全 derive**：
- documents：每個 root（section == article）的一句話＋狀態；root 未結晶但樹已有帶 concept
  的 leaf 的 article 也列入（`conceptId: null`、oneLiner 取 group.yaml title／humanize slug、
  `rootCrystallized: false`）——否則施工中的樹從 documents 蒸發、其 leaf cid 卻在 hierarchy
  露臉＝地圖自相矛盾。
- hierarchy：doc-level rollup——childDoc 治於 parentDoc ⟺ childDoc 樹內某 concept 的
  governed-by 指到 parentDoc 樹內某 concept。位於 doc-level 環上的邊（parentDoc 遞移可
  反向抵達 childDoc；含 A⇄B 互治與更長的環）帶 additive `cycle: true`——只標不擋，
  governs 成環的硬紅燈仍是 `check` 的。
- parallel：任兩文件在 hierarchy 遞移閉包下**任一方向皆不可達**才同層平行
  （只排除直接邊會把爺孫文件誤標平行）。

刪掉 governed-by → hierarchy 立刻消失（證明 derive 自它、無第二份）。只投 develop。
"""

from __future__ import annotations

from itertools import combinations

from dspx.layout import Layout
from dspx.model import Leaf


def forest_view(leaves: list[Leaf], layout: Layout | None = None) -> dict:
    # concept.id → 擁有它的 leaf 的 article（rollup 用：governed-by 目標 → parentDoc）
    cid_to_article: dict[str, str] = {}
    # concept.id → (title, section)：anchors 投影用（下游作者接 governed-by 時可發現目標 id）
    cid_info: dict[str, tuple] = {}
    for lf in leaves:
        if lf.concept and lf.concept.get("id"):
            cid = str(lf.concept["id"])
            cid_to_article[cid] = lf.article
            cid_info[cid] = (lf.concept.get("title"), lf.section)

    # anchor 候選＝root concept ∪「已被任一 leaf 的 governed-by 列為目標」的 concept（Decision 4）。
    # 不限跨文件邊——被列為治理目標＝定義上就是 anchor；刻意不列全部 concept（round-11 單文件
    # 30 葉＝投影洪水），完整目錄由 `docspec list <article> --json` 提供。
    governed_targets: set[str] = set()
    for lf in leaves:
        if lf.concept:
            for target in (lf.concept.get("governed-by") or []):
                governed_targets.add(str(target))

    def _anchors(article: str, root_cid: object) -> list[dict]:
        anchor_ids = {str(root_cid)} if root_cid else set()
        anchor_ids |= {cid for cid in governed_targets
                       if cid_to_article.get(cid) == article}
        return sorted(
            ({"id": cid, "title": cid_info[cid][0], "section": cid_info[cid][1]}
             for cid in anchor_ids if cid in cid_info),
            key=lambda a: a["section"])

    # documents：(a) 已結晶 root（section == article 且有 concept）；
    # (b) root 未結晶但樹已有帶 concept 的 leaf 的 article（施工中——不蒸發、明確標註）。
    roots = {lf.article: lf for lf in leaves if lf.section == lf.article and lf.concept}
    concept_articles = sorted({lf.article for lf in leaves if lf.concept})
    documents = []
    for article in concept_articles:
        root = roots.get(article)
        if root is not None:
            documents.append({
                "article": article,
                "conceptId": root.concept.get("id"),
                "oneLiner": root.concept.get("concept"),
                "status": root.concept.get("status"),
                "anchors": _anchors(article, root.concept.get("id")),
                "rootCrystallized": True,
            })
        else:
            # oneLiner＝corpus/<article>/group.yaml 的 title（與 render 封面標題同機制）、
            # 缺則 humanize slug；不偽造 concept。
            from dspx.render import _group_title, _humanize_segment
            one_liner = (_group_title(layout, article, article) if layout is not None
                         else _humanize_segment(article))
            documents.append({
                "article": article,
                "conceptId": None,
                "oneLiner": one_liner,
                "status": None,
                "anchors": _anchors(article, None),
                "rootCrystallized": False,
            })

    # hierarchy：doc-level rollup（childDoc, parentDoc）→ via:[(childCid, parentCid)…]
    edges: dict[tuple[str, str], list[list[str]]] = {}
    for lf in leaves:
        if not lf.concept:
            continue
        child_doc = lf.article
        child_cid = lf.concept.get("id")
        for target in (lf.concept.get("governed-by") or []):
            parent_doc = cid_to_article.get(str(target))
            if parent_doc is None or parent_doc == child_doc:
                continue
            edges.setdefault((child_doc, parent_doc), []).append([child_cid, str(target)])

    # 遞移閉包（child→parent 有向圖上的可達集）：parallel 判準＋環偵測共用。
    # 節點＝documents 的 article 全集（root 文件數＝個位數~數十，DFS O(V·E) 可忽略）。
    adj: dict[str, set[str]] = {}
    for cd, pd in edges:
        adj.setdefault(cd, set()).add(pd)

    def _reachable(start: str) -> set[str]:
        seen: set[str] = set()
        stack = list(adj.get(start, ()))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adj.get(node, ()))
        return seen

    reach = {article: _reachable(article) for article in concept_articles}

    # 環上邊（parentDoc 遞移可反向抵達 childDoc）帶 additive cycle 旗標；無環邊不加欄（省噪）。
    # 只標不擋：check 對 governs 成環的硬紅燈不變。
    hierarchy = []
    for (cd, pd), via in sorted(edges.items()):
        edge: dict = {"childDoc": cd, "parentDoc": pd, "via": sorted(via)}
        if cd in reach.get(pd, ()):
            edge["cycle"] = True
        hierarchy.append(edge)

    # parallel：遞移閉包下任一方向皆不可達才同層平行（直接邊是閉包子集——
    # 只排除直接邊會把爺孫文件誤標平行）；未結晶 root 的文件一併參與。
    parallel = [
        [a, b]
        for a, b in combinations(concept_articles, 2)
        if b not in reach[a] and a not in reach[b]
    ]

    return {"documents": documents, "hierarchy": hierarchy, "parallel": parallel}
