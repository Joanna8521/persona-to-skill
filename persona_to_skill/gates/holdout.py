#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G4: holdout alignment, scored against a baseline.

The only gate that distinguishes a reconstruction from a costume.

Questions the subject has publicly answered are held back from extraction. The
built skill answers them; the answers are compared with what the subject
actually said. Alignment on held-back material is evidence the method
transferred. Alignment on material the skill was built from is evidence of
nothing, which is why items flagged as seen are excluded rather than scored.

That alone is not enough, and this is the heart of the gate. Most of what any
practitioner says out loud is consensus, so a reconstruction scores well on
those questions whether or not it learned anything. Pooling them with the rest
produces a flattering grade for an empty shell.

So each item carries a BASELINE observation: the same question answered with no
reconstruction loaded. Items split in two:

    consensus pool  the baseline already matches the subject. Reported, never
                    gated: no credit for an answer the default gets right.
    divergent pool  the baseline is wrong, so only judgement that actually
                    carried across can be right. The gate reads this pool.

Alignment therefore means "alignment where the default would have failed",
which is the lift over baseline measured directly rather than subtracted.

UNKNOWN is a first-class state throughout. An item with no recorded observation
is not a pass and not a failure: it leaves the denominator and is reported on
its own. Scoring it either way would invent the measurement: as a failure it
slanders a reconstruction for a thin question set, as a pass it flatters one
for a check that never ran.

Note that `bool` is a subclass of `int` in Python, so a JSON `true` would
satisfy a naive isinstance(x, int) check and then be summed as 1, inventing a
score this module promises never to estimate.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import (
    HOLDOUT_MAX_UNKNOWN_RATIO,
    HOLDOUT_MIN_ALIGNMENT,
    HOLDOUT_MIN_DIVERGENT_ITEMS,
    HOLDOUT_MIN_ITEMS,
)
from . import Verdict

GATE = "G4-holdout"
UNKNOWN = "unknown"


NO_HOLDOUT_SET = (
    "no holdout set supplied. This gate cannot be skipped: without held-back "
    "questions there is no evidence the reconstruction captured a method "
    "rather than a voice."
)

def _observation(value: Any) -> Any:
    """Keep explicit booleans; everything else stays UNKNOWN.

    Absence, null, "yes", 1 and 0 are all UNKNOWN. Coercing any of them would
    manufacture an observation nobody made.
    """
    return value if isinstance(value, bool) else UNKNOWN


def _ratio(aligned: int, scored: int) -> float | None:
    """None, not 0.0: with nothing scored there is no ratio, and 0.0 would read
    as 'measured, and bad'."""
    return (aligned / scored) if scored else None


def score(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score holdout items by pool, deriving nothing that was not recorded.

    Each item may carry:
        aligned            bool: did the reconstruction match the subject
        baseline_aligned   bool: did the no-reconstruction baseline match
        seen_in_extraction bool: was this material used to build the skill
    """
    pools = {
        "divergent": {"aligned": 0, "diverged": 0},
        "consensus": {"aligned": 0, "diverged": 0},
    }
    unknown = no_baseline = seen_flagged = 0

    for item in items:
        if item.get("seen_in_extraction") is True:
            # Not holdout material. Counted and excluded, never scored.
            seen_flagged += 1
            continue

        obs = _observation(item.get("aligned"))
        if obs is UNKNOWN:
            unknown += 1
            continue

        base = _observation(item.get("baseline_aligned"))
        if base is UNKNOWN:
            # Scoreable, but there is no way to tell which pool it belongs to,
            # so it cannot be credited to either.
            no_baseline += 1
            continue

        pool = "consensus" if base else "divergent"
        pools[pool]["aligned" if obs else "diverged"] += 1

    div_scored = pools["divergent"]["aligned"] + pools["divergent"]["diverged"]
    con_scored = pools["consensus"]["aligned"] + pools["consensus"]["diverged"]
    total = div_scored + con_scored + unknown + no_baseline

    return {
        "divergent": dict(pools["divergent"], scored=div_scored,
                          alignment=_ratio(pools["divergent"]["aligned"], div_scored)),
        "consensus": dict(pools["consensus"], scored=con_scored,
                          alignment=_ratio(pools["consensus"]["aligned"], con_scored)),
        "unknown": unknown,
        "no_baseline": no_baseline,
        "seen_excluded": seen_flagged,
        "scored": div_scored + con_scored,
        "total_eligible": total,
        # The gated figure. Named so a report cannot quietly print the
        # consensus-inflated number in its place.
        "gated_alignment": _ratio(pools["divergent"]["aligned"], div_scored),
        "unknown_ratio": _ratio(unknown, total),
    }


def check(items: List[Dict[str, Any]] | None) -> Verdict:
    """Gate on holdout results.

    Fails closed when holdout material is absent, and when baselines are absent.
    Both are the kind of optional input that invites a quiet pass, which would
    leave the one gate that proves the method transferred doing nothing at all.
    """
    if items is None:
        return Verdict(
            GATE, False,
            [NO_HOLDOUT_SET],
        )
    if not items:
        return Verdict(GATE, False, ["holdout set is empty"])

    s = score(items)
    d = s["divergent"]
    errors: List[str] = []
    warnings: List[str] = []

    if s["scored"] < HOLDOUT_MIN_ITEMS:
        errors.append(
            f"only {s['scored']} item(s) scored; at least {HOLDOUT_MIN_ITEMS} are needed "
            "for an alignment ratio to mean anything"
        )

    if d["scored"] < HOLDOUT_MIN_DIVERGENT_ITEMS:
        errors.append(
            f"only {d['scored']} item(s) in the divergent pool; at least "
            f"{HOLDOUT_MIN_DIVERGENT_ITEMS} are needed. These are the questions where a "
            "model with no reconstruction answers wrongly, so they are the only ones "
            "that can show judgement carried across. Where a subject's public positions "
            "are all consensus, this is not a fixable question set: the method cannot be "
            "meaningfully reconstructed, and that is the finding."
        )

    if s["no_baseline"]:
        # Fail closed. Without baselines the two pools cannot be told apart, and
        # falling back to a raw figure over all items is exactly the flattering
        # measurement this gate exists to refuse.
        errors.append(
            f"{s['no_baseline']} scoreable item(s) have no baseline observation. Record "
            "what a model with no reconstruction loaded answers for each question; "
            "without it, consensus answers cannot be separated from real alignment."
        )

    if s["unknown_ratio"] is not None and s["unknown_ratio"] > HOLDOUT_MAX_UNKNOWN_RATIO:
        errors.append(
            f"{s['unknown_ratio']:.0%} of items have no recorded observation "
            f"(limit {HOLDOUT_MAX_UNKNOWN_RATIO:.0%}). This is a defect in the holdout "
            "questions, not a measurement of the skill: the subject's own answer could "
            "not be established. Replace those questions."
        )

    if d["alignment"] is not None and d["alignment"] < HOLDOUT_MIN_ALIGNMENT:
        errors.append(
            f"divergent-pool alignment {d['alignment']:.0%} is below the "
            f"{HOLDOUT_MIN_ALIGNMENT:.0%} threshold. On the questions where the default "
            "answer is wrong, the reconstruction does not reproduce the subject's "
            "judgement."
        )

    if s["seen_excluded"]:
        warnings.append(
            f"{s['seen_excluded']} item(s) were flagged as seen during extraction and "
            "excluded from scoring; they prove nothing either way"
        )

    con = s["consensus"]
    if con["alignment"] is not None:
        warnings.append(
            f"consensus pool: {con['alignment']:.0%} over {con['scored']} item(s), "
            "reported but not gated: a model with no reconstruction also answers these"
        )

    return Verdict(GATE, not errors, errors, warnings, s)
