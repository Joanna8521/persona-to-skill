# -*- coding: utf-8 -*-
"""What provenance measurement must and must not claim."""
import _base  # noqa: F401
from persona_to_skill.collect import provenance as pv

HUMAN_EN = ("I walk away from a stalled deal. Discounting to close teaches the "
            "buyer that waiting works. That is the whole of it. We do not "
            "reopen on price. Margin is the point, not the signature.")
HUMAN_ZH = ("停滯超過六十天就放手。打折成交會教買方拖著有用。這一條沒有例外。"
            "我們不在價格上重啟談判。重點是毛利，不是簽名。")
ASR_LIKE = ("i walk away from a stalled deal discounting to close teaches the "
            "buyer that waiting works that is the whole of it we do not reopen "
            "on price margin is the point not the signature")


def test_human_text_is_anchorable():
    for t in (HUMAN_EN, HUMAN_ZH):
        p = pv.measure(t)
        assert p.anchorable, p.why_not_anchorable
        assert p.sentence_density >= pv.MIN_SENTENCE_DENSITY


def test_unpunctuated_text_is_not_anchorable():
    p = pv.measure(ASR_LIKE, kind="transcript")
    assert not p.anchorable
    assert p.sentence_density == 0.0
    assert any("nothing to quote between" in r for r in p.why_not_anchorable)


def test_threshold_sits_well_below_real_human_text():
    """Set from measurement, not judgement: across ~190k characters of real
    human-written text in two languages the lowest value was 1.02 per 100
    characters, and stripped text measured exactly 0.00. The bar is near a
    third of the lowest real value, inside a gap nothing lands in."""
    assert pv.MIN_SENTENCE_DENSITY < 1.02 / 2
    assert pv.MIN_SENTENCE_DENSITY > 0.0


def test_casing_is_not_scored_where_there_is_nothing_to_score():
    """Chinese sentences start with characters that have no case, so a casing
    figure would be meaningless rather than low."""
    p = pv.measure(HUMAN_ZH)
    assert p.sentence_casing is None
    assert p.anchorable


def test_anchorable_does_not_claim_a_human_reviewed_it():
    """Current speech recognition punctuates its own output, so punctuation is
    evidence of a punctuating producer and nothing more. The docstring has to
    keep saying so, because the field name invites the stronger reading."""
    doc = pv.__doc__ or ""
    assert "DOES NOT establish human review" in doc
    fields = pv.measure(HUMAN_EN).to_dict()
    assert "human_reviewed" not in fields and "reviewed" not in fields


def test_declared_track_kind_is_recorded_but_never_read():
    """Whether editing an auto-generated track reclassifies it is undocumented,
    so the label is carried for the record and decides nothing."""
    auto = pv.measure(HUMAN_EN, kind="transcript", declared_track_kind="ASR")
    manual = pv.measure(HUMAN_EN, kind="transcript", declared_track_kind="standard")
    assert auto.anchorable == manual.anchorable is True
    bad = pv.measure(ASR_LIKE, kind="transcript", declared_track_kind="standard")
    assert not bad.anchorable, "a 'standard' label must not rescue unpunctuated text"
    assert auto.to_dict()["declared_track_kind"] == "ASR"


def test_unknown_kind_is_refused():
    for bad in ("video", "", "TEXT", None):
        try:
            pv.measure(HUMAN_EN, kind=bad)
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"kind {bad!r} accepted")


def test_empty_text_is_not_anchorable():
    assert not pv.measure("", kind="transcript").anchorable


def test_dict_explains_a_refusal():
    d = pv.measure(ASR_LIKE, kind="transcript").to_dict()
    assert d["anchorable"] is False
    assert d["why_not_anchorable"]


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
