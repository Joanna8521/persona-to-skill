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




# ---------------------------------------------------------------------------
# Regression tests from experiments/g2_realcorpus.py
#
# Measured against ~175k characters of real text, not reasoned about. Before
# these foldings existed, exact matching rejected 12 of 12 English passages
# whose contractions had been expanded, 9 of 9 Chinese passages written with
# half-width punctuation, and 8 of 8 with a space added between Chinese and
# Latin text. Those are not fabrications; they are what a model produces when
# it writes a quote field, because it regenerates text rather than copying
# bytes.
#
# Each folding below changes bytes and leaves the token stream identical, so
# two strings that fold together said the same thing and no fabricated quote
# can match by differing only here. Removing any of them re-breaks G2 on real
# material.
# ---------------------------------------------------------------------------

def _src(text):
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text(text, encoding="utf-8")
    return d


def _matches(source_text, quote):
    return anchor.check(
        [{"id": "c", "text": "a claim", "source_id": "s1", "quote": quote}],
        _src(source_text)).passed


def test_expanded_contractions_match():
    """0 of 12 before this folding existed."""
    for src, quote in (
        ("I don't discount to close.", "I do not discount to close"),
        ("It's the buyer who learns.", "It is the buyer who learns"),
        ("They're waiting you out.", "They are waiting you out"),
        ("That won't work twice.", "That will not work twice"),
        ("You can't un-discount.", "You can not un-discount"),
        ("He doesn't negotiate twice.", "He does not negotiate twice"),
    ):
        assert _matches(src, quote), f"{quote!r} did not match {src!r}"


def test_contracted_quote_matches_expanded_source():
    """Folding has to work in both directions; the model may contract too."""
    assert _matches("I do not discount to close.", "I don't discount to close")


def test_capital_is_preserved_through_expansion():
    """Case-insensitive matching with a lowercase replacement quietly
    lowercased the text at every contraction site, so a correctly quoted
    sentence was rejected over its first letter. Found by the experiment, not
    by reading the code."""
    assert _matches("That's what I thought before.", "That is what I thought before")


def test_possessive_is_not_expanded():
    """"Paul's essay" must not become "Paul is essay". Only pronouns and
    determiners take the contraction reading."""
    assert _matches("Paul's essay says so.", "Paul's essay says so")
    assert not _matches("Paul's essay says so.", "Paul is essay says so")


def test_half_width_cjk_punctuation_matches():
    """0 of 9 before this folding. NFKC does not help: 。，、 are characters in
    their own right, not compatibility forms of ASCII."""
    assert _matches("停滯超過六十天，就放手，不打折。",
                    "停滯超過六十天,就放手,不打折.")


def test_cjk_latin_spacing_is_optional():
    """0 of 8 before this folding. Adding the space is a style convention, so a
    model does it unprompted."""
    assert _matches("導入 CRM 之前先把流程寫下來。", "導入CRM之前先把流程寫下來")
    assert _matches("導入CRM之前先把流程寫下來。", "導入 CRM 之前先把流程寫下來")


def test_cjk_quote_marks_fold():
    assert _matches("他說「先別報價」就掛了電話。", '他說"先別報價"就掛了電話')


def test_dropped_ellipsis_is_refused_and_says_why():
    """The one near-miss that stays a failure. An ellipsis marks elided text,
    so removing it asserts two passages are contiguous when the source says
    they are not. That is an integrity problem, not a formatting difference."""
    v = anchor.check(
        [{"id": "c", "text": "a claim", "source_id": "s1",
          "quote": "I walk away from a stalled deal and the buyer learns nothing"}],
        _src("I walk away from a stalled deal ... and the buyer learns nothing."))
    assert not v.passed
    assert any("contiguous" in e for e in v.errors), v.errors


def test_folding_still_cannot_rescue_a_fabricated_quote():
    """The point of every folding above is that it cannot do this."""
    src = "I don't discount to close. 停滯超過六十天就放手。"
    for invented in (
        "I never negotiate under any circumstances",
        "I do not discount because margin is sacred",
        "停滯超過三十天就放手",
        "I don't discount to win",
    ):
        assert not _matches(src, invented), f"fabrication matched: {invented!r}"



# ---------------------------------------------------------------------------
# A source_id reaches a glob pattern, so it reaches the filesystem
# ---------------------------------------------------------------------------

def test_a_source_id_cannot_escape_the_corpus_directory():
    """Shipped, and found by testing rather than by reading. "../secret" is a
    legal relative glob pattern: it read a file outside the corpus and G2 then
    confirmed, correctly, that the quote matched. Anything on disk could be
    quoted as the subject's words."""
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("I walk away rather than discount.", encoding="utf-8")
    (d.parent / "secret.txt").write_text("TOP SECRET CONTENT", encoding="utf-8")
    for sid in ("../secret", "s1/../../secret", "..", ".", "/etc/hostname",
                "..\\secret"):
        v = anchor.check(
            [{"id": "c", "text": "x", "source_id": sid, "quote": "TOP SECRET"}], d)
        assert not v.passed, f"source_id {sid!r} escaped the corpus"


def test_a_symlink_out_of_the_corpus_is_not_a_source():
    """The second half. Rejecting separators stops the pattern escaping; it
    does not stop a link inside the corpus pointing out of it."""
    import os
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("harmless.", encoding="utf-8")
    (d.parent / "secret.txt").write_text("TOP SECRET CONTENT", encoding="utf-8")
    os.symlink(d.parent / "secret.txt", d / "sneaky.txt")
    v = anchor.check(
        [{"id": "c", "text": "x", "source_id": "sneaky", "quote": "TOP SECRET"}], d)
    assert not v.passed


def test_a_dotfile_is_not_a_source():
    d = Path(tempfile.mkdtemp())
    (d / ".hidden.txt").write_text("quiet.", encoding="utf-8")
    v = anchor.check(
        [{"id": "c", "text": "x", "source_id": ".hidden", "quote": "quiet"}], d)
    assert not v.passed


def test_an_ordinary_source_id_still_reads():
    """The fix has to discriminate, not refuse everything."""
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("I walk away rather than discount.", encoding="utf-8")
    assert anchor.check([{"id": "c", "text": "x", "source_id": "s1",
                          "quote": "I walk away rather than discount"}], d).passed



# ---------------------------------------------------------------------------
# A quote can match its source exactly and still not be the subject's words
# ---------------------------------------------------------------------------

GHOST = [{"id": "b1", "tier": "T2", "authorship": "ghostwritten"}]
OWN = [{"id": "b1", "tier": "T2", "authorship": "self_written"}]


def _book():
    d = Path(tempfile.mkdtemp())
    (d / "b1.txt").write_text("The deal is about leverage.", encoding="utf-8")
    return d


def _claim(**over):
    c = {"id": "c1", "text": "Deals are about leverage.", "source_id": "b1",
         "quote": "The deal is about leverage"}
    c.update(over)
    return c


def test_a_ghostwritten_source_cannot_be_quoted_as_the_subjects_words():
    v = anchor.check([_claim()], _book(), GHOST)
    assert not v.passed
    assert any("not the\n" not in e and "own words" in e for e in v.errors)


def test_flagging_it_as_the_sources_words_is_accepted():
    """The honest form stays available: what the book published under their name
    says, rather than what they said."""
    v = anchor.check([_claim(attributed_to_source=True)], _book(), GHOST)
    assert v.passed, v.errors
    assert v.stats["not_the_subjects_own_words"] == 1


def test_every_authorship_that_is_not_their_own_words_requires_the_flag():
    from persona_to_skill.contract import AUTHORSHIP_NOT_OWN_WORDS
    for kind in AUTHORSHIP_NOT_OWN_WORDS:
        srcs = [{"id": "b1", "tier": "T2", "authorship": kind}]
        assert not anchor.check([_claim()], _book(), srcs).passed, kind
        assert anchor.check([_claim(attributed_to_source=True)], _book(), srcs).passed


def test_self_written_and_unknown_need_no_flag():
    assert anchor.check([_claim()], _book(), OWN).passed
    unknown = [{"id": "b1", "tier": "T2", "authorship": "unknown"}]
    assert anchor.check([_claim()], _book(), unknown).passed


def test_omitting_the_source_manifest_keeps_the_old_behaviour():
    """G2 is still callable without it; authorship is then simply not checked
    rather than assumed."""
    assert anchor.check([_claim()], _book()).passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
