# -*- coding: utf-8 -*-
import _base  # noqa: F401
from persona_to_skill.gates import holdout


def items(aligned=0, diverged=0, unknown=0, seen=0):
    out = [{"aligned": True} for _ in range(aligned)]
    out += [{"aligned": False} for _ in range(diverged)]
    out += [{} for _ in range(unknown)]
    out += [{"aligned": True, "seen_in_extraction": True} for _ in range(seen)]
    return out


# ----------------------------------------------------------------- positive
def test_at_threshold_passes():
    v = holdout.check(items(aligned=16, diverged=4))
    assert v.passed, v.errors
    assert v.stats["alignment"] == 0.80


def test_unknowns_leave_the_denominator():
    """The whole point: 10 aligned of 10 scored is 100%, even alongside 4
    unobserved items."""
    v = holdout.check(items(aligned=10, unknown=4))
    assert v.passed, v.errors
    assert v.stats["alignment"] == 1.0
    assert v.stats["scored"] == 10
    assert v.stats["unknown"] == 4


# ----------------------------------------------- negative: UNKNOWN semantics
def test_unknown_is_never_counted_as_aligned():
    s = holdout.score(items(unknown=10))
    assert s["aligned"] == 0 and s["unknown"] == 10


def test_unknown_is_never_counted_as_diverged():
    s = holdout.score(items(unknown=10))
    assert s["diverged"] == 0


def test_no_scored_items_yields_none_not_zero():
    """0.0 would read as 'measured, and bad'. None says 'not measured'."""
    s = holdout.score(items(unknown=5))
    assert s["alignment"] is None


def test_json_true_as_int_is_not_summed():
    """bool is a subclass of int. A truthy non-bool must stay UNKNOWN rather
    than being coerced into a score nobody recorded."""
    for sneaky in (1, 0, "true", "yes", None, 1.0, [], {}):
        s = holdout.score([{"aligned": sneaky}])
        assert s["unknown"] == 1, f"{sneaky!r} was coerced into an observation"
        assert s["aligned"] == 0 and s["diverged"] == 0


def test_only_real_booleans_score():
    assert holdout.score([{"aligned": True}])["aligned"] == 1
    assert holdout.score([{"aligned": False}])["diverged"] == 1


# ------------------------------------------------- negative: must go red
def test_absent_holdout_blocks_rather_than_passing():
    """The fail-open shape this exists to prevent: holdout is an optional
    input, so a quiet pass here would disable the only gate that proves the
    method transferred."""
    v = holdout.check(None)
    assert not v.passed
    assert any("cannot be skipped" in e for e in v.errors)


def test_empty_holdout_blocks():
    assert not holdout.check([]).passed


def test_below_threshold_blocks():
    v = holdout.check(items(aligned=15, diverged=5))   # 75%
    assert not v.passed
    assert any("below" in e for e in v.errors)


def test_too_few_scored_items_blocks_even_at_100_percent():
    """Nine for nine is not evidence; it is a small sample."""
    v = holdout.check(items(aligned=9))
    assert not v.passed
    assert any("at least" in e for e in v.errors)


def test_excessive_unknowns_block_and_blame_the_questions():
    v = holdout.check(items(aligned=10, unknown=10))   # 50% unknown
    assert not v.passed
    assert any("holdout questions" in e for e in v.errors)


def test_seen_items_are_excluded_not_scored():
    """Items the extraction already saw prove nothing. Padding the set with
    them must not lift the score past the gate."""
    v = holdout.check(items(aligned=5, diverged=5, seen=50))   # 50% on real holdout
    assert not v.passed
    assert v.stats["seen_excluded"] == 50
    assert v.stats["scored"] == 10
    assert v.stats["alignment"] == 0.5
    assert v.warnings


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
