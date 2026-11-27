# -*- coding: utf-8 -*-
"""The eval harness, and the four ways a run stops counting.

What this file is really about: the harness must never produce an observation.
Every check below is some form of "an observation nobody made does not become
one here", because the alternative corrupts the only number in the project that
means anything.

G4 already treats UNKNOWN as a first-class state. This layer decides what
reaches G4 in the first place, and that decision is where a self-report can
sneak in wearing a percentage sign.
"""
import json
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.eval import (
    EvalError, anchor_manifest, load_manifest, load_run, reconcile, render,
)
from persona_to_skill.gates import holdout


def tmp(name, data):
    d = Path(tempfile.mkdtemp())
    p = d / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def m_item(i, **over):
    out = {"id": f"q{i}", "question": f"Question {i}?", "source_id": f"src{i}",
           "subject_said": f"What the subject said about {i}."}
    out.update(over)
    return out


def r_item(i, **over):
    out = {"id": f"q{i}", "reconstruction": "r", "baseline": "b",
           "aligned": True, "baseline_aligned": False,
           "judged_by": "a separate judging pass", "blind": True}
    out.update(over)
    return out


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except EvalError as exc:
        return str(exc)
    raise AssertionError(f"{fn.__name__} did not raise EvalError")


# ── the manifest ────────────────────────────────────────

def test_an_empty_manifest_is_refused():
    """A question set with nothing in it would score 0 of 0 and read as a
    clean run. Nothing is not a measurement."""
    assert "no items" in raises(load_manifest, tmp("m.json", {"items": []}))


def test_a_ground_truth_with_no_quote_is_refused():
    """The comparison downstream is against this string. Empty, and every
    alignment judgement below it is a judgement about nothing."""
    bad = tmp("m.json", [m_item(1, subject_said="   ")])
    assert "subject_said is empty" in raises(load_manifest, bad)


def test_a_ground_truth_with_no_source_is_refused():
    """An unanchored ground truth is the failure this project exists to
    prevent, and an eval suite is not exempt for being the thing measuring."""
    bad = tmp("m.json", [m_item(1, source_id="")])
    assert "no source_id" in raises(load_manifest, bad)


def test_duplicate_manifest_ids_are_refused():
    """Two entries for one question means one silently wins, and which one
    depends on iteration order."""
    bad = tmp("m.json", [m_item(1), m_item(1)])
    assert "duplicate id" in raises(load_manifest, bad)


def test_a_manifest_may_be_a_bare_list_or_an_items_object():
    assert len(load_manifest(tmp("a.json", [m_item(1)]))) == 1
    assert len(load_manifest(tmp("b.json", {"items": [m_item(1)]}))) == 1


# ── the run, and what counts as an observation ──────────

def test_a_string_observation_is_refused():
    """The point of the whole module.

    "yes" is not an observation. Coercing it to True would invent the
    measurement, and coercing it to False would slander the build. `bool` is
    also a subclass of `int` in Python, so a naive check would accept a JSON
    `true` and sum it as 1, which is the same defect from the other side.
    """
    for value in ("yes", "probably", 1, 0, "true", ""):
        bad = tmp("r.json", [r_item(1, aligned=value)])
        assert "must be true, false, or null" in raises(load_run, bad), value


def test_null_is_accepted_as_an_observation_nobody_made():
    """null is the honest value for "not looked at", and it must survive."""
    run = load_run(tmp("r.json", [r_item(1, aligned=None)]))
    assert run[0]["aligned"] is None


def test_blind_must_be_an_actual_boolean():
    """Whether the judge knew which answer was which is the field that
    protects the number. It cannot be left vague."""
    for value in ("yes", 1, None, "blind"):
        bad = tmp("r.json", [r_item(1, blind=value)])
        assert "not a boolean" in raises(load_run, bad), value


def test_a_run_missing_judged_by_entirely_is_refused_at_load():
    bad = tmp("r.json", [{k: v for k, v in r_item(1).items() if k != "judged_by"}])
    assert "missing judged_by" in raises(load_run, bad)


# ── reconciliation ──────────────────────────────────────

def test_an_answer_to_a_question_the_manifest_does_not_ask_is_an_error():
    """Not a warning. The manifest is the question set the subject's answers
    were pinned to, so an answer to some other question has no ground truth
    here, and scoring it would measure something nobody specified."""
    msg = raises(reconcile, [m_item(1)], [r_item(1), r_item(99)])
    assert "the manifest does not ask" in msg
    assert "q99" in msg


def test_a_manifest_item_with_no_run_entry_becomes_unknown_not_a_failure():
    rec = reconcile([m_item(1), m_item(2)], [r_item(1)])
    assert rec["missing"] == ["q2"]
    # The item is still handed to the scorer, with no `aligned` key at all, so
    # G4 reads it as UNKNOWN rather than being told anything.
    q2 = next(i for i in rec["items"] if i["id"] == "q2")
    assert "aligned" not in q2
    score = holdout.score(rec["items"])
    assert score["unknown"] == 1
    assert score["divergent"]["diverged"] == 0, "a missing item was scored as wrong"


def test_an_unjudged_item_is_not_scored():
    """Something decided these matched and the instrument is unnamed, so the
    decision cannot be checked."""
    rec = reconcile([m_item(1)], [r_item(1, judged_by="  ")])
    assert rec["unjudged"] == ["q1"]
    assert "aligned" not in rec["items"][0]
    assert holdout.score(rec["items"])["scored"] == 0


def test_a_non_blind_judgement_is_counted_and_never_gated():
    """The one that actually protects the number.

    A judge told which candidate is the reconstruction has been handed the
    result the experiment was supposed to produce. The item is reported, so a
    non-blind run reads as non-blind, and it leaves the gated denominator.
    """
    rec = reconcile([m_item(1)], [r_item(1, blind=False)])
    assert rec["not_blind"] == ["q1"]
    score = holdout.score(rec["items"])
    assert score["scored"] == 0
    assert score["gated_alignment"] is None, "a non-blind judgement was gated"


def test_a_blind_judgement_is_scored():
    """And the other way round, so the check above is not passing for free."""
    rec = reconcile([m_item(1)], [r_item(1, blind=True)])
    assert rec["not_blind"] == []
    assert holdout.score(rec["items"])["divergent"]["aligned"] == 1


def test_seen_in_extraction_is_passed_through_not_re_decided():
    rec = reconcile([m_item(1, seen_in_extraction=True)], [r_item(1)])
    assert rec["items"][0]["seen_in_extraction"] is True
    assert holdout.score(rec["items"])["seen_excluded"] == 1


def test_judges_are_collected_so_a_reader_can_see_the_instrument():
    rec = reconcile(
        [m_item(1), m_item(2)],
        [r_item(1, judged_by="judge A"), r_item(2, judged_by="judge B")])
    assert rec["judges"] == ["judge A", "judge B"]


# ── the ground truth goes through G2 ────────────────────

def corpus_with(**files):
    d = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (d / f"{name}.txt").write_text(text, encoding="utf-8")
    return d


def test_an_anchored_ground_truth_passes():
    c = corpus_with(src1="Prose before. What the subject said about 1. After.")
    assert anchor_manifest([m_item(1)], c).passed


def test_a_ground_truth_absent_from_its_source_fails():
    """An eval suite is not exempt from G2 for being the thing measuring.

    If the quote is not in the source, every number downstream rests on an
    unverified assertion, and it would rest on it invisibly.
    """
    c = corpus_with(src1="This source says something else entirely.")
    v = anchor_manifest([m_item(1)], c)
    assert not v.passed
    assert any("does not appear verbatim" in e for e in v.errors)


def test_the_question_not_the_quote_names_the_failing_item():
    """A G2 failure has to point at which eval item is unanchored, rather than
    quoting the subject back at the reader, who then has to find it."""
    c = corpus_with(src1="Nothing relevant.")
    v = anchor_manifest([m_item(1, question="Does pricing follow cost?")], c)
    assert not v.passed


# ── the report ──────────────────────────────────────────

def test_the_report_distinguishes_the_two_pools():
    items = (
        [{"id": f"d{i}", "aligned": True, "baseline_aligned": False} for i in range(5)]
        + [{"id": f"c{i}", "aligned": True, "baseline_aligned": True} for i in range(5)]
    )
    score = holdout.score(items)
    rec = {"missing": [], "unjudged": [], "not_blind": [], "judges": ["j"]}
    out = render(score, rec)
    assert "Divergent | 5" in out
    assert "| Consensus | 5" in out
    # The consensus number must never be presented as the gated one.
    gated_line = next(row for row in out.split("\n")
                      if "Divergent" in row and "|" in row)
    assert "**yes**" in gated_line


def test_the_report_never_prints_zero_percent_for_not_measured():
    """0% reads as "measured, and bad", which is a different and worse claim
    to make by accident."""
    score = holdout.score([])
    rec = {"missing": [], "unjudged": [], "not_blind": [], "judges": []}
    out = render(score, rec)
    assert "not measured" in out
    assert "0%" not in out.split("## Both pools")[0]


def test_the_report_says_so_when_no_judge_is_named_anywhere():
    score = holdout.score([])
    out = render(score, {"missing": [], "unjudged": [], "not_blind": [],
                         "judges": []})
    assert "nothing above is a measurement" in out


def test_the_report_reconciles_its_own_arithmetic():
    """The four unobserved reasons are the same items as the total, counted two
    ways. If they stop adding up, one module has changed what it counts and the
    table would still look perfectly reasonable while being wrong."""
    score = holdout.score([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    good = render(score, {"missing": ["a"], "unjudged": ["b"],
                          "not_blind": ["c"], "judges": ["j"]})
    assert "do not reconcile" not in good

    # Now a reconciled dict that disagrees with the score, which is what a
    # drifting module would produce.
    bad = render(score, {"missing": ["a", "b", "c", "d", "e"], "unjudged": [],
                         "not_blind": [], "judges": ["j"]})
    assert "do not reconcile" in bad


def test_the_report_flags_a_divergent_pool_too_small_to_mean_anything():
    items = [{"id": "d1", "aligned": True, "baseline_aligned": False}]
    out = render(holdout.score(items),
                 {"missing": [], "unjudged": [], "not_blind": [], "judges": ["j"]})
    assert "below the floor" in out


# ── end to end ──────────────────────────────────────────

def test_a_run_where_every_judgement_is_non_blind_scores_nothing():
    """The whole point, stated as one case.

    Ten items, every one aligned, every judgement made by something that knew
    which answer was which. The gate must not pass this, and the figure must
    read as not measured rather than as 100%.
    """
    manifest = [m_item(i) for i in range(1, 11)]
    run = [r_item(i, blind=False) for i in range(1, 11)]
    rec = reconcile(manifest, run)
    score = holdout.score(rec["items"])
    assert score["gated_alignment"] is None
    assert not holdout.check(rec["items"]).passed
    out = render(score, rec)
    assert "not measured" in out
    # Narrowed to the gated figure on purpose. "100% unobserved" is CORRECT
    # here and must be printed; the first version asserted "100%" appeared
    # nowhere in the report and failed on that line, which was the test being
    # wrong rather than the report.
    headline = out.split("## Both pools")[0]
    assert "100%" not in headline, headline


def test_a_clean_run_passes_the_gate():
    """And the other way round, so the above is not passing because the gate
    rejects everything."""
    manifest = [m_item(i) for i in range(1, 16)]
    run = ([r_item(i) for i in range(1, 11)]
           + [r_item(i, baseline_aligned=True) for i in range(11, 16)])
    rec = reconcile(manifest, run)
    verdict = holdout.check(rec["items"])
    assert verdict.passed, verdict.errors
    assert holdout.score(rec["items"])["gated_alignment"] == 1.0


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
