"""軟體領域（第二期，取代 OpenSpec）：能力規格、軟體 change、任務、測試規劃、證據、封存、基線。

設計依據：docs/dev/phase2-design.md、docs/dev/phase2-detail.md。
檔案一律是引擎擁有、各自封條的 YAML，只能透過 `docspec code …` 指令寫入。
"""


def validate_all(layout) -> tuple[list[str], list[str]]:
    """`docspec check` ⑭：全部能力規格與進行中 change 的格式與引用。回 (errors, warnings)。"""
    from dspx.engine.software import changes as chg
    from dspx.engine.software import io
    from dspx.engine.software import specs as sp

    if not io.has_software(layout):
        from dspx.engine import project_baseline as pb
        return pb.validate(layout), []
    errs: list[str] = []
    warns: list[str] = []
    for cap in sp.list_capabilities(layout):
        try:
            spec = sp.load_spec(layout, cap)
        except io.SoftwareError as exc:
            errs.append(str(exc))
            continue
        if spec.get("capability") != cap:
            errs.append(f"spec {cap}: file name and capability \"{spec.get('capability')}\" differ")
        errs += sp.validate_spec(spec)
    for cid in chg.list_active(layout):
        try:
            ch = chg.load_change(layout, cid)
        except io.SoftwareError as exc:
            errs.append(str(exc))
            continue
        e, w = chg.validate_change(layout, ch)
        errs += e
        warns += w
    from dspx.engine.software import evidence as ev
    e, w = ev.validate(layout)
    from dspx.engine.software import archive as arc
    e2, w2 = arc.validate_verified_by(layout)
    from dspx.engine import project_baseline as pb
    return errs + e + e2 + pb.validate(layout), warns + w + w2
