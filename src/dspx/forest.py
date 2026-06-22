"""森林地圖（derive，不另存）：把多棵樹的 root 文件＋跨樹 governed-by 關係攤成一張地圖。

關係只活一處＝`concept.governed-by`（單向、子→父）。這裡的階層/平行/一句話**全 derive**：
- documents：每個 root（section == article）的一句話＋狀態。
- hierarchy：doc-level rollup——childDoc 治於 parentDoc ⟺ childDoc 樹內某 concept 的
  governed-by 指到 parentDoc 樹內某 concept。
- parallel：任兩 root 之間「hierarchy 無邊（任一方向）」即同層平行。

刪掉 governed-by → hierarchy 立刻消失（證明 derive 自它、無第二份）。只投 develop。
"""

from __future__ import annotations

from itertools import combinations

from dspx.model import Leaf


def forest_view(leaves: list[Leaf]) -> dict:
    # concept.id → 擁有它的 leaf 的 article（rollup 用：governed-by 目標 → parentDoc）
    cid_to_article: dict[str, str] = {}
    for lf in leaves:
        if lf.concept and lf.concept.get("id"):
            cid_to_article[str(lf.concept["id"])] = lf.article

    # documents：每個 root（section == article）且有 concept
    documents = []
    for lf in leaves:
        if lf.section == lf.article and lf.concept:
            documents.append({
                "article": lf.article,
                "conceptId": lf.concept.get("id"),
                "oneLiner": lf.concept.get("concept"),
                "status": lf.concept.get("status"),
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

    hierarchy = [
        {"childDoc": cd, "parentDoc": pd, "via": sorted(via)}
        for (cd, pd), via in sorted(edges.items())
    ]

    # parallel：任兩個 root article（去重）之間 hierarchy 無邊（任一方向）
    root_articles = sorted({lf.article for lf in leaves if lf.section == lf.article and lf.concept})
    edge_pairs = {(cd, pd) for (cd, pd) in edges}
    parallel = [
        [a, b]
        for a, b in combinations(root_articles, 2)
        if (a, b) not in edge_pairs and (b, a) not in edge_pairs
    ]

    return {"documents": documents, "hierarchy": hierarchy, "parallel": parallel}
