# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.gates import anchor

BODY = (
    "When a deal stalls past 60 days I walk away rather than discount. "
    "Discounting to close teaches the buyer that waiting works.\n"
    "我從來不在第一次見面就報價，因為那等於放棄了後面所有的談判空間。\n"
)


def _corpus(files=None):
    d = Path(tempfile.mkdtemp())
    for name, text in (files or {"s1": BODY}).items():
        (d / f"{name}.txt").write_text(text, encoding="utf-8")
    return d


# ----------------------------------------------------------------- positive
def test_anchored_claim_passes():
    v = anchor.check([{
        "id": "c1", "text": "Walks away from deals that stall past 60 days.",
        "source_id": "s1", "quote": "I walk away rather than discount",
    }], _corpus())
    assert v.passed, v.errors


def test_chinese_quote_passes():
    v = anchor.check([{
        "id": "c1", "text": "第一次見面不報價。",
        "source_id": "s1", "quote": "我從來不在第一次見面就報價",
    }], _corpus())
    assert v.passed, v.errors


def test_full_width_digits_normalize():
    d = _corpus({"s1": "停滯超過 ６０ 天就放手。"})
    v = anchor.check([{
        "id": "c1", "text": "門檻是 60 天。", "source_id": "s1", "quote": "停滯超過 60 天就放手",
    }], d)
    assert v.passed, v.errors


def test_inference_is_exempt_but_reported():
    v = anchor.check([{"id": "c1", "text": "Probably dislikes discounting.",
                       "attribution": "inference"}], _corpus())
    assert v.passed
    assert v.stats["inferences"] == 1
    assert v.warnings


# ----------------------------------------------------- negative: must go red
def test_fabricated_quote_blocks():
    v = anchor.check([{
        "id": "c1", "text": "Never negotiates.",
        "source_id": "s1", "quote": "I never negotiate under any circumstances",
    }], _corpus())
    assert not v.passed
    assert any("verbatim" in e for e in v.errors)


def test_claim_without_source_blocks():
    v = anchor.check([{"id": "c1", "text": "Walks away from stalled deals."}], _corpus())
    assert not v.passed


def test_source_named_but_nothing_quoted_blocks():
    v = anchor.check([{"id": "c1", "text": "x", "source_id": "s1", "quote": "  "}], _corpus())
    assert not v.passed


def test_source_missing_from_corpus_blocks():
    v = anchor.check([{"id": "c1", "text": "x", "source_id": "ghost", "quote": "anything"}], _corpus())
    assert not v.passed
    assert any("not in the corpus" in e for e in v.errors)


def test_invented_number_blocks_even_with_a_real_quote():
    """The quote checks out but the claim inflates a figure -- the most likely
    real-world failure, and the reason numbers are checked separately."""
    v = anchor.check([{
        "id": "c1", "text": "Walks away after 14 days.",
        "source_id": "s1", "quote": "I walk away rather than discount",
    }], _corpus())
    assert not v.passed
    assert any("14" in e for e in v.errors)


def test_missing_corpus_dir_blocks_rather_than_passing():
    """Fail-closed: no corpus means no independent check, so the gate must not
    report success."""
    v = anchor.check([{"id": "c1", "text": "x", "source_id": "s1", "quote": "y"}],
                     Path("/nonexistent-corpus-dir"))
    assert not v.passed
    assert any("cannot verify" in e for e in v.errors)


def test_no_claims_blocks():
    assert not anchor.check([], _corpus()).passed


def test_case_difference_is_not_folded():
    """Width and whitespace are not substantive; wording is. A quote that
    differs in wording must not pass."""
    v = anchor.check([{
        "id": "c1", "text": "x", "source_id": "s1", "quote": "i WALK away rather than DISCOUNT",
    }], _corpus())
    assert not v.passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
