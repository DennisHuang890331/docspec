"""Slot contract — build/validate slot values + render-time validation against a template."""

from __future__ import annotations

import pytest

from dspx.typeset import slots as S


def test_build_slots_derived_and_text():
    out = S.build_slots("My Title", "body prose", {"abstract": "an abstract"})
    assert out["title"] == "My Title"
    assert out["body"] == "body prose"
    assert out["abstract"] == "an abstract"


def test_build_slots_unknown_key_raises():
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"not_a_slot": "x"})


def test_build_slots_rejects_body_override():
    # body is derived, not user-settable
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"body": "hijack"})


def test_build_slots_list_kind_validation():
    assert S.build_slots("T", "b", {"keywords": ["a", "b"]})["keywords"] == ["a", "b"]
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"keywords": "not-a-list"})
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"keywords": [1, 2]})


def test_build_slots_people_kind_validation():
    ppl = [{"name": "Ada", "affiliation": "Lab"}]
    assert S.build_slots("T", "b", {"authors": ppl})["authors"] == ppl
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"authors": [{"affiliation": "no name"}]})
    with pytest.raises(S.SlotError):
        S.build_slots("T", "b", {"authors": "Ada"})


def test_build_slots_none_value_skipped():
    out = S.build_slots("T", "b", {"abstract": None})
    assert "abstract" not in out


def test_template_referenced_slots():
    tmpl = r"\title{$title$}$for(authors)$$authors.name$$endfor$$if(abstract)$$abstract$$endif$"
    refs = S.template_referenced_slots(tmpl)
    assert refs == {"title", "authors", "abstract"}


def test_validate_against_template_reports_unknown_and_unused():
    # template wants `funding` (not in contract) and uses title/abstract; doc provides keywords (unused)
    tmpl = r"$title$ $abstract$ $funding$"
    provided = S.build_slots("T", "b", {"abstract": "a", "keywords": ["k"]})
    unknown, unused = S.validate_against_template(provided, tmpl)
    assert unknown == ["funding"]
    assert unused == ["keywords"]


def test_validate_against_template_clean():
    tmpl = r"$title$ $abstract$ $body$"
    provided = S.build_slots("T", "b", {"abstract": "a"})
    unknown, unused = S.validate_against_template(provided, tmpl)
    assert unknown == [] and unused == []
