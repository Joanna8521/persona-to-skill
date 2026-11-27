# -*- coding: utf-8 -*-
import _base  # noqa: F401
from persona_to_skill.gates import holdout


def items(aligned=0, diverged=0, unknown=0, seen=0, consensus=0, no_baseline=0):
    """Build a holdout set.

    `aligned` / `diverged` land in the DIVERGENT pool (baseline_aligned=False:
    a model with no reconstruction answers wrongly, so the item can show
    judgement). `consensus` items the baseline already gets right.
    """
    out = [{"aligned": True, "baseline_aligned": False} for _ in range(aligned)]
    out += [{"aligned": False, "baseline_aligned": False} for _ in range(diverged)]
    out += [{"aligned": True, "baseline_aligned": True} for _ in range(consensus)]
    out += [{"baseline_aligned": False} for _ in range(unknown)]
    out += [{"aligned": True} for _ in range(no_baseline)]
    out += [{"aligned": True, "baseline_aligned": False,
             "seen_in_extraction": True} for _ in range(seen)]
    return out


# ----------------------------------------------------------------- positive
def test_at_threshold_passes():
    v = holdout.check(items(aligned=16, diverged=4))
    assert v.passed, v.errors
    assert v.stats["gated_alignment"] == 0.80


def test_unknowns_leave_the_denominator():
    """10 aligned of 10 scored is 100%, even alongside 4 unobserved items."""
    v = holdout.check(items(aligned=10, unknown=4))
    assert v.passed, v.errors
    assert v.stats["gated_alignment"] == 1.0
    assert v.stats["scored"] == 10
    assert v.stats["unknown"] == 4


def test_consensus_items_are_reported_but_not_gated():
    """A real reconstruction also answers consensus questions; it just gets no
    credit for them. They appear in stats and in a warning, never in the gate."""
    v = holdout.check(items(aligned=10, consensus=30))
    assert v.passed, v.errors
    assert v.stats["consensus"]["scored"] == 30
    assert v.stats["gated_alignment"] == 1.0   # divergent pool only
    assert any("not gated" in w for w in v.warnings)


# ------------------------------------- negative: the consensus-padding attack
def test_consensus_padding_cannot_lift_a_failing_reconstruction():
    """The attack this pool split exists to stop. 5/10 on divergent questions
    plus 40 consensus answers would read as 45/50 = 90% under a single pool.
    Scored by pool it is 50%, and it fails."""
    v = holdout.check(items(aligned=5, diverged=5, consensus=40))
    assert not v.passed
    assert v.stats["gated_alignment"] == 0.5
    assert any("divergent-pool alignment" in e for e in v.errors)


def test_all_consensus_set_blocks_and_says_why():
    """A subject whose public positions are all consensus cannot be
    meaningfully reconstructed. The gate reports that rather than issuing a
    100% grade."""
    v = holdout.check(items(consensus=40))
    assert not v.passed
    assert any("divergent pool" in e for e in v.errors)
    assert any("cannot be meaningfully reconstructed" in e for e in v.errors)


def test_too_few_divergent_items_blocks_even_when_all_aligned():
    v = holdout.check(items(aligned=4, consensus=20))   # 4 < 5 required
    assert not v.passed
    assert any("divergent pool" in e for e in v.errors)


def test_missing_baseline_blocks_rather_than_falling_back():
    """Fail-closed. Without baselines the pools cannot be told apart, and a raw
    figure over all items is exactly the flattering measurement this gate
    refuses."""
    v = holdout.check(items(aligned=20, no_baseline=10))
    assert not v.passed
    assert any("baseline" in e for e in v.errors)


def test_baseline_must_be_a_real_boolean():
    for sneaky in (1, 0, "false", None):
        s = holdout.score([{"aligned": True, "baseline_aligned": sneaky}])
        assert s["no_baseline"] == 1, f"{sneaky!r} coerced into a pool"
        assert s["divergent"]["scored"] == 0 and s["consensus"]["scored"] == 0


# ----------------------------------------------- negative: UNKNOWN semantics
def test_unknown_is_never_counted_as_aligned():
    s = holdout.score(items(unknown=10))
    assert s["divergent"]["aligned"] == 0 and s["unknown"] == 10


def test_unknown_is_never_counted_as_diverged():
    s = holdout.score(items(unknown=10))
    assert s["divergent"]["diverged"] == 0


def test_no_scored_items_yields_none_not_zero():
    """0.0 would read as 'measured, and bad'. None says 'not measured'."""
    s = holdout.score(items(unknown=5))
    assert s["gated_alignment"] is None
    assert s["divergent"]["alignment"] is None


def test_json_true_as_int_is_not_summed():
    """bool is a subclass of int. A truthy non-bool must stay UNKNOWN rather
    than being coerced into a score nobody recorded."""
    for sneaky in (1, 0, "true", "yes", None, 1.0, [], {}):
        s = holdout.score([{"aligned": sneaky, "baseline_aligned": False}])
        assert s["unknown"] == 1, f"{sneaky!r} was coerced into an observation"
        assert s["divergent"]["scored"] == 0 and s["consensus"]["scored"] == 0


def test_only_real_booleans_score():
    assert holdout.score(items(aligned=1))["divergent"]["aligned"] == 1
    assert holdout.score(items(diverged=1))["divergent"]["diverged"] == 1


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
    assert v.stats["gated_alignment"] == 0.5
    assert v.warnings


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
