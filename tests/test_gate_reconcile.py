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


# ── three ways the first version of this gate was still loose ──

def _mixed(aligned_in_whole, aligned_in_slice):
    whole = [{"aligned": aligned_in_whole, "baseline_aligned": False}
             for _ in range(5)] + [dict(CON) for _ in range(7)]
    slices = {"oppose": [{"aligned": aligned_in_slice, "baseline_aligned": False}
                         for _ in range(5)],
              "evidence": [dict(CON) for _ in range(7)]}
    return whole, slices


def test_an_unknown_observation_is_not_a_failed_one():
    """`bool()` collapsed null into False, so a global list recording
    `aligned: null` and a per-seat list recording `aligned: false` compared
    equal while the scorers read them as 0 divergent scored against 5."""
    whole, slices = _mixed(None, False)
    v = reconcile.check(whole, slices, {"holdout_alignment": "not measured"},
                        "PUBLISHED")
    assert not v.passed
    assert any("different runs" in e for e in v.errors), v.errors
    assert "unknown" in [e for e in v.errors if "different runs" in e][0]


def test_the_same_observation_on_both_sides_still_reconciles():
    whole, slices = _mixed(True, True)
    assert reconcile.check(whole, slices, {"holdout_alignment": "100%"},
                           "PUBLISHED").passed


def _at(alignment):
    """A holdout whose divergent pool scores exactly `alignment`."""
    aligned = round(alignment * 5)
    return ([dict(DIV) for _ in range(aligned)]
            + [{"aligned": False, "baseline_aligned": False}
               for _ in range(5 - aligned)]
            + [dict(CON) for _ in range(7)])


def test_a_longer_number_containing_the_figure_is_not_the_figure():
    """A substring test passed `180% over 5` when the computed figure was
    `80%`: the gate built to stop a disclosure contradicting the computation
    accepted text that contradicted it."""
    whole = _at(0.8)
    slices = {"oppose": whole[:5], "evidence": whole[5:]}
    assert reconcile.check(whole, slices,
                           {"holdout_alignment": "80% over 5 divergent items"},
                           "PUBLISHED").passed
    for wrong in ("180% over 5", "800%", "not 80%", "80% over 5, 92% raw"):
        v = reconcile.check(whole, slices, {"holdout_alignment": wrong},
                            "PUBLISHED")
        assert not v.passed, f"{wrong!r} was accepted"


def test_an_inference_in_the_support_seat_does_not_block():
    """`all_entries` walks SEATS, which includes `support`; `skill_md` walks
    SEAT_ENTRY_ORDER, which does not. Checking the unrendered seat blocked an
    otherwise valid package over a claim no reader ever sees."""
    import test_build_package as fixture  # noqa: PLC0415

    b = fixture.bundle()
    b["seats"]["support"] = {"strongest_case": [
        {"claim": "A claim made only on request", "attribution": "inference",
         "derived_from": ["s1"]}]}
    b["unfilled_seats_acknowledged"] = [
        s for s in b["unfilled_seats_acknowledged"] if s != "support"]

    with tempfile.TemporaryDirectory() as tmp:
        _, verdicts, _ = package.run(b, fixture.corpus_dir(), Path(tmp))
    g3 = next(v for v in verdicts if v.gate == "G3-disclosure")
    assert g3.passed, g3.errors


# ── the seat an observation landed in ──────────────────

def _with_ids():
    whole = ([dict(DIV, id=f"q{i}") for i in range(1, 6)]
             + [dict(CON, id=f"q{i}") for i in range(6, 13)])
    slices = {"oppose": [dict(x) for x in whole[:5]],
              "evidence": [dict(x) for x in whole[5:]]}
    return whole, slices


def test_without_ids_the_gate_says_what_it_did_not_check():
    """Moving an observation between seats leaves the totals unchanged while
    reversing which seat the profile tells a reader to trust. The aggregate
    comparison cannot see it, so the verdict says so instead of letting
    silence imply otherwise."""
    whole = [dict(DIV) for _ in range(5)] + [dict(CON) for _ in range(7)]
    swapped = {"oppose": [dict(CON) for _ in range(5)],
               "evidence": [dict(DIV) for _ in range(5)] + [dict(CON) for _ in range(2)]}
    v = reconcile.check(whole, swapped, {"holdout_alignment": "100%"}, "PUBLISHED")
    assert v.passed
    assert any("carry no ids" in w for w in v.warnings), v.warnings


def test_with_ids_a_swapped_seat_blocks():
    whole, slices = _with_ids()
    assert reconcile.check(whole, slices, GOOD_DISCLOSURE, "PUBLISHED").passed

    swapped = {"oppose": [dict(CON, id=f"q{i}") for i in range(1, 6)],
               "evidence": ([dict(DIV, id=f"q{i}") for i in range(6, 11)]
                            + [dict(CON, id=f"q{i}") for i in range(11, 13)])}
    v = reconcile.check(whole, swapped, GOOD_DISCLOSURE, "PUBLISHED")
    assert not v.passed
    assert any("differ between holdout" in e for e in v.errors), v.errors


def test_with_ids_a_missing_item_blocks():
    whole, slices = _with_ids()
    slices["evidence"] = slices["evidence"][:-1]
    v = reconcile.check(whole, slices, GOOD_DISCLOSURE, "PUBLISHED")
    assert not v.passed
    assert any("cover different items" in e for e in v.errors), v.errors


def test_with_ids_the_same_item_under_two_seats_blocks():
    whole, slices = _with_ids()
    slices["oppose"] = slices["oppose"] + [dict(DIV, id="q1")]
    v = reconcile.check(whole, slices, GOOD_DISCLOSURE, "PUBLISHED")
    assert not v.passed
    assert any("more than one seat" in e for e in v.errors), v.errors


def test_ids_on_one_side_only_fall_back_to_totals():
    """Half-identified data is not identified data; the gate does not pretend
    the assignment was checked."""
    whole, slices = _with_ids()
    bare = {k: [{kk: vv for kk, vv in x.items() if kk != "id"} for x in v]
            for k, v in slices.items()}
    v = reconcile.check(whole, bare, GOOD_DISCLOSURE, "PUBLISHED")
    assert v.passed
    assert any("carry no ids" in w for w in v.warnings), v.warnings


# ── shape, and the numbers beside the percentage ──────

def test_a_malformed_per_seat_input_is_a_verdict_not_a_crash():
    """`holdout_by_seat: []` is not None, so it reached `.values()` and
    raised AttributeError out of package.run. A crash is worse than any
    verdict: it is not a finding anyone can act on, and it loses the errors
    the other gates had already collected."""
    for bad in ([], "x", 7):
        v = reconcile.check(_h(), bad, GOOD_DISCLOSURE, "PUBLISHED")
        assert not v.passed
        assert "mapping" in v.errors[0], v.errors

    v = reconcile.check(_h(), {"oppose": "not a list"}, GOOD_DISCLOSURE,
                        "PUBLISHED")
    assert not v.passed
    assert "oppose" in v.errors[0]

    v = reconcile.check("not a list", _seats(), GOOD_DISCLOSURE, "PUBLISHED")
    assert not v.passed
    assert "list of observations" in v.errors[0]


def test_a_count_the_holdout_does_not_support_blocks():
    """Only the percentage was compared, so a five-item divergent pool
    accepted "100% over 500 divergent items" and "100% from 999 total".
    Those go into SKILL.md verbatim under a label saying they were
    measured."""
    whole, slices = _h(), _seats()
    for good in ("100% over 5 divergent items", "100% over 5 of 12", "100%"):
        assert reconcile.check(whole, slices, {"holdout_alignment": good},
                               "PUBLISHED").passed, good
    for bad in ("100% over 500 divergent items", "100% from 999 total"):
        v = reconcile.check(whole, slices, {"holdout_alignment": bad},
                            "PUBLISHED")
        assert not v.passed, f"{bad!r} was accepted"
        assert "matches no count in the holdout" in v.errors[0]


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
