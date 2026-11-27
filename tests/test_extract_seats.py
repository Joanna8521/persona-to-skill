# -*- coding: utf-8 -*-
"""The seats, and the three decisions about what the output is for."""
import copy

import _base  # noqa: F401
from persona_to_skill.contract import SEAT_ENTRY_ORDER, SEAT_OBLIGATIONS, SEATS
from persona_to_skill.extract import seats

ANCHORED = {"claim": "停滯超過六十天就放手", "source_id": "s1",
            "quote": "I walk away rather than discount"}


def bundle(**over):
    b = {
        "seats": {
            "oppose": {"premortem": [copy.deepcopy(ANCHORED)],
                       "refusals": [copy.deepcopy(ANCHORED)]},
            "evidence": {"demanded_before_acting": [copy.deepcopy(ANCHORED)]},
        },
        "entry_order": list(SEAT_ENTRY_ORDER),
        "unfilled_seats_acknowledged": [s for s in SEATS
                                        if s not in ("oppose", "evidence")],
    }
    b.update(over)
    return b


# ----------------------------------------------------------------- positive
def test_a_well_formed_bundle_passes():
    v = seats.check(bundle())
    assert v.passed, v.errors
    assert v.stats["entries"] == 3


def test_an_inference_entry_is_allowed_when_it_says_so():
    b = bundle()
    b["seats"]["oppose"]["underestimated"] = [
        {"claim": "大概會低估在地化成本", "attribution": "inference",
         "derived_from": ["s1"]}]
    assert seats.check(b).passed


# ---------------------------------------- 對抗預設：反方席先跑，支持席不主動給
def test_entry_order_must_lead_with_oppose():
    assert SEAT_ENTRY_ORDER[1] == "oppose", "進場順序改了，這個設計決定被動到了"
    assert not seats.check(bundle(entry_order=["decompose", "support", "oppose"])).passed


def test_the_support_seat_may_not_be_volunteered():
    """最危險的使用者不是沒有立場的人，是已經有答案、拿著他佩服的人的重建、
    然後得到那個聲音的同意。"""
    bad = bundle(entry_order=["decompose", "support"] + list(SEAT_ENTRY_ORDER[1:]))
    v = seats.check(bad)
    assert not v.passed
    assert any("never volunteered" in e for e in v.errors)


def test_a_missing_entry_order_blocks():
    b = bundle()
    del b["entry_order"]
    assert not seats.check(b).passed


# -------------------------------- 空席是語料的發現，不是那個人的特質
def test_an_unfilled_seat_must_be_acknowledged():
    b = bundle()
    del b["unfilled_seats_acknowledged"]
    v = seats.check(b)
    assert not v.passed
    assert any("had nothing to say" in e for e in v.errors)


def test_acknowledging_the_wrong_seats_blocks():
    assert not seats.check(bundle(unfilled_seats_acknowledged=["support"])).passed


def test_every_seat_empty_blocks():
    assert not seats.check(bundle(seats={"oppose": {}})).passed


def test_unfilled_seats_are_listed_in_stats():
    v = seats.check(bundle())
    assert set(v.stats["unfilled"]) == set(SEATS) - {"oppose", "evidence"}


# ------------------------------- 每一筆都是 claim，直接餵給 G2
def test_an_entry_without_a_source_blocks():
    b = bundle()
    b["seats"]["oppose"]["premortem"] = [{"claim": "死在單店經濟"}]
    v = seats.check(b)
    assert not v.passed
    assert any("attribution" in e for e in v.errors)


def test_an_entry_with_no_claim_blocks():
    b = bundle()
    b["seats"]["oppose"]["premortem"] = [{"source_id": "s1", "quote": "q"}]
    assert not seats.check(b).passed


def test_an_inference_with_no_derivation_blocks():
    b = bundle()
    b["seats"]["oppose"]["premortem"] = [
        {"claim": "x", "attribution": "inference"}]
    assert not seats.check(b).passed


def test_entries_are_handed_to_g2_in_the_shape_it_takes():
    """七席不是另一套誠實機制，它餵的是已經存在的那一套。"""
    from persona_to_skill.gates import anchor
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("I walk away rather than discount.", encoding="utf-8")
    entries = seats.all_entries(bundle())
    assert entries
    for e in entries:
        e.setdefault("text", e["claim"])
    assert anchor.check(entries, d).passed


# ------------------------------------------------------------- 結構
def test_unknown_seat_blocks():
    assert not seats.check(bundle(seats={"vibes": {}})).passed


def test_unknown_field_in_a_seat_blocks():
    b = bundle()
    b["seats"]["oppose"]["mood"] = [copy.deepcopy(ANCHORED)]
    assert not seats.check(b).passed


def test_every_seat_declares_what_it_owes():
    assert set(SEAT_OBLIGATIONS) == set(SEATS)
    for seat, fields in SEAT_OBLIGATIONS.items():
        assert fields, f"{seat} owes nothing"


def test_no_bundle_blocks():
    assert not seats.check(None).passed
    assert not seats.check({}).passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
