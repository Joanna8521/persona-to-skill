# -*- coding: utf-8 -*-
"""B-reconcile, and the two other figures that nothing used to compare.

Three gaps found by review, each the same shape: a number a reader takes as
measured, which no code ever checked against the measurement.
"""
import sys
import tempfile
import zipfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.deliver import package
from persona_to_skill.gates import disclosure, holdout, reconcile

DIV = {"aligned": True, "baseline_aligned": False}
CON = {"aligned": True, "baseline_aligned": True}


def _h(divergent=5, consensus=7):
    return [dict(DIV) for _ in range(divergent)] + [dict(CON) for _ in range(consensus)]


def _seats(divergent=5, consensus=7):
    return {"oppose": [dict(DIV) for _ in range(divergent)],
            "evidence": [dict(CON) for _ in range(consensus)]}


GOOD_DISCLOSURE = {"holdout_alignment": "100% over 5 divergent items"}


def test_a_consistent_bundle_passes():
    v = reconcile.check(_h(), _seats(), GOOD_DISCLOSURE, "PUBLISHED")
    assert v.passed, v.errors


def test_per_seat_totals_that_do_not_match_the_whole_block():
    v = reconcile.check(_h(), _seats(consensus=8), GOOD_DISCLOSURE, "PUBLISHED")
    assert not v.passed
    assert "different runs" in v.errors[0]
    # Both counts are named, so the reader is not left to go and count.
    assert "12 item(s)" in v.errors[0] and "13 item(s)" in v.errors[0]


def test_a_disclosure_figure_the_holdout_does_not_support_blocks():
    v = reconcile.check(_h(), _seats(),
                        {"holdout_alignment": "92% over 12 items"}, "PUBLISHED")
    assert not v.passed
    assert "92% over 12 items" in v.errors[0] and "100%" in v.errors[0]


def test_the_comparison_uses_the_same_spelling_as_the_report():
    """A second way of writing the percentage would let the gate pass text the
    report contradicts, which is the failure it exists to catch."""
    assert holdout.format_alignment(1.0) == "100%"
    assert holdout.format_alignment(0.8) == "80%"
    assert holdout.format_alignment(None) == "not measured"


def test_absence_blocks_on_both_sides():
    assert not reconcile.check(None, _seats(), GOOD_DISCLOSURE, "PUBLISHED").passed
    assert not reconcile.check(_h(), None, GOOD_DISCLOSURE, "PUBLISHED").passed


def test_private_scope_does_not_require_a_disclosure_figure():
    """Nobody is being informed, so there is no published figure to reconcile.
    The per-seat check still applies: that one is about the bundle, not the
    reader."""
    assert reconcile.check(_h(), _seats(), None, "PRIVATE").passed
    assert not reconcile.check(_h(), _seats(consensus=8), None, "PRIVATE").passed


# ── G3 and the inference labels ─────────────────────────

FULL_DISCLOSURE = {"reconstruction_notice": "set", "not_endorsed": "set",
                   "source_count": 2, "holdout_alignment": "100%",
                   "retrieved_date": "2026-11-27"}
CLAIM = "Cost of holding a standard through a partner"


def test_an_unlabelled_inference_claim_blocks():
    """G2 exempts a claim marked `inference` from the quote check because G3
    was said to verify the label. It did not: it warned when the word
    appeared anywhere and said nothing when it was absent, which is the
    unlabelled case."""
    v = disclosure.check(f"# A\n\n- {CLAIM}\n", "A. Example", "PUBLISHED",
                         FULL_DISCLOSURE, [{"claim": CLAIM, "attribution": "inference"}])
    assert not v.passed
    assert CLAIM in v.errors[0]


def test_a_labelled_inference_claim_passes():
    text = f"# A\n\n- {CLAIM} *(inference from s9)*\n"
    v = disclosure.check(text, "A. Example", "PUBLISHED", FULL_DISCLOSURE,
                         [{"claim": CLAIM, "attribution": "inference"}])
    assert v.passed, v.errors


def test_a_label_split_across_lines_still_counts():
    """The renderer does not wrap today, but a reader's eye and a substring
    match disagree about a line break, and the gate should side with the
    reader."""
    text = f"# A\n\n- {CLAIM}\n  *(inference from s9)*\n"
    v = disclosure.check(text, "A. Example", "PUBLISHED", FULL_DISCLOSURE,
                         [{"claim": CLAIM, "attribution": "inference"}])
    assert v.passed, v.errors


def test_g3_blocks_when_it_was_not_given_the_claims():
    v = disclosure.check("# A\n", "A. Example", "PUBLISHED", FULL_DISCLOSURE, None)
    assert not v.passed
    assert "not given" in v.errors[0]


# ── the stale archive ───────────────────────────────────

def test_a_failing_run_names_the_archive_it_did_not_overwrite():
    """`package.run` returns before touching the output directory, so a zip
    from an earlier successful run with the same slug and version stays put
    and looks exactly like a build of this bundle. It is named rather than
    deleted: destroying an artifact the user may still want is a worse
    failure than leaving a stale one they have been warned about."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        stale = out / "a-example-method-v1.0.zip"
        with zipfile.ZipFile(stale, "w") as z:
            z.writestr("old/SKILL.md", "an earlier build")

        broken = {"subject": {"name": "A. Example", "slug": "a-example"},
                  "version": "1.0", "scope": "PUBLISHED"}
        zip_path, _, errors = package.run(broken, Path(tmp), out)

    assert zip_path is None
    assert any("a-example-method-v1.0.zip" in e and "NOT this bundle" in e
               for e in errors), errors


def test_a_failing_run_with_an_empty_directory_says_nothing_about_archives():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        broken = {"subject": {"name": "A. Example", "slug": "a-example"},
                  "version": "1.0", "scope": "PUBLISHED"}
        _, _, errors = package.run(broken, Path(tmp), out)
    assert not any("still in" in e for e in errors), errors


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
