#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G4 -- holdout alignment.

The only gate that distinguishes a reconstruction from a costume.

Questions the subject has publicly answered are held back from extraction.
The built skill answers them; the answers are compared with what the subject
actually said. Alignment on held-back material is evidence the method
transferred. Alignment on material the skill was built from is evidence of
nothing, which is why this gate refuses to score items flagged as seen.

UNKNOWN is a first-class state, following book-to-skill's tools/evals/score.py.
An item with no recorded observation is not a pass and not a failure: it leaves
the denominator and is reported on its own. Note that `bool` is a subclass of
`int` in Python, so a JSON `true` would satisfy a naive isinstance(x, int)
check and then be summed as 1 -- inventing a score this module promises never
to estimate.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import (
    HOLDOUT_MAX_UNKNOWN_RATIO,
    HOLDOUT_MIN_ALIGNMENT,
    HOLDOUT_MIN_ITEMS,
)
from . import Verdict

GATE = "G4-holdout"
UNKNOWN = "unknown"


def _observation(value: Any) -> Any:
    """Keep explicit booleans; everything else stays UNKNOWN.

    Absence, null, "yes", 1 and 0 are all UNKNOWN. Coercing any of them would
    manufacture an observation nobody made.
    """
    return value if isinstance(value, bool) else UNKNOWN


def score(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score holdout items without deriving anything that was not recorded."""
    aligned = diverged = unknown = seen_flagged = 0

    for item in items:
        if item.get("seen_in_extraction") is True:
            # Not holdout material. Counted and excluded, never scored.
            seen_flagged += 1
            continue
        obs = _observation(item.get("aligned"))
        if obs is UNKNOWN:
            unknown += 1
        elif obs:
            aligned += 1
        else:
            diverged += 1

    scored = aligned + diverged
    total = scored + unknown
    return {
        "aligned": aligned,
        "diverged": diverged,
        "unknown": unknown,
        "seen_excluded": seen_flagged,
        "scored": scored,
        "total_eligible": total,
        # None, not 0.0: with nothing scored there is no ratio, and 0.0 would
        # read as "measured, and bad".
        "alignment": (aligned / scored) if scored else None,
        "unknown_ratio": (unknown / total) if total else None,
    }


def check(items: List[Dict[str, Any]] | None) -> Verdict:
    """Gate on holdout results.

    Fails closed when holdout material is absent. Holdout is the kind of
    optional input that invites a quiet `return Verdict(passed=True)` -- which
    would leave the one gate that proves the method transferred doing nothing
    at all.
    """
    if items is None:
        return Verdict(
            GATE, False,
            ["no holdout set supplied. This gate cannot be skipped: without held-back "
             "questions there is no evidence the reconstruction captured a method "
             "rather than a voice."],
        )
    if not items:
        return Verdict(GATE, False, ["holdout set is empty"])

    s = score(items)
    errors: List[str] = []
    warnings: List[str] = []

    if s["scored"] < HOLDOUT_MIN_ITEMS:
        errors.append(
            f"only {s['scored']} item(s) scored; at least {HOLDOUT_MIN_ITEMS} are needed "
            "for an alignment ratio to mean anything"
        )
    if s["unknown_ratio"] is not None and s["unknown_ratio"] > HOLDOUT_MAX_UNKNOWN_RATIO:
        errors.append(
            f"{s['unknown_ratio']:.0%} of items have no recorded observation "
            f"(limit {HOLDOUT_MAX_UNKNOWN_RATIO:.0%}). This is a defect in the holdout "
            "questions, not a measurement of the skill: the subject's own answer could "
            "not be established. Replace those questions."
        )
    if s["alignment"] is not None and s["alignment"] < HOLDOUT_MIN_ALIGNMENT:
        errors.append(
            f"alignment {s['alignment']:.0%} is below the {HOLDOUT_MIN_ALIGNMENT:.0%} "
            "threshold. The reconstruction does not reproduce the subject's judgement "
            "on held-back questions."
        )
    if s["seen_excluded"]:
        warnings.append(
            f"{s['seen_excluded']} item(s) were flagged as seen during extraction and "
            "excluded from scoring; they prove nothing either way"
        )

    return Verdict(GATE, not errors, errors, warnings, s)
