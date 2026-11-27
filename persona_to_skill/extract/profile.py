#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per seat, not one number.

A practitioner is usually distinctive in one or two seats and ordinary in the
rest. Someone who has watched a lot of things fail has a strong oppose seat.
Someone who knows which figures lie has a strong evidence seat. Their
decompose seat may be no better than anyone's. A single alignment figure
averages that away and tells the reader nothing about where to trust the
result.

So the profile is per seat, and it is computed the same way the holdout gate
computes anything: against a recorded baseline, where the baseline is the same
question answered with no reconstruction loaded. A seat is

    distinctive  the baseline gets its questions wrong and the reconstruction
                 gets them right. Judgement carried across here.
    generic      the baseline already answers them. The reconstruction may be
                 correct and is adding nothing: it may not claim this seat.
    unfilled     the corpus had nothing to put in it. Not a finding about the
                 person.

What that buys is the honest claim. Instead of "84% aligned", a reconstruction
says which seats it earned, and the skill it produces claims only those. A
reader who knows the oppose seat is distinctive and the synthesise seat is
generic knows exactly how much to lean on each, which no single score can tell
them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contract import (
    HOLDOUT_MIN_ALIGNMENT,
    SEAT_PROFILE_VERDICTS,
    SEATS,
)
from ..gates import Verdict

GATE = "B-profile"

DISTINCTIVE, GENERIC, UNFILLED = SEAT_PROFILE_VERDICTS

# Below this many divergent items a seat cannot be called distinctive, however
# well it scored. Deliberately lower than the whole-reconstruction floor: a
# seat is a slice of the holdout, so demanding the full count per seat would
# make the profile unreachable rather than honest. The whole-reconstruction
# floor still applies in G4.
MIN_DIVERGENT_PER_SEAT = 3


NO_PER_SEAT_HOLDOUT = (
    "no per-seat holdout supplied. A single figure averages away the thing a "
    "reader needs: which seats this reconstruction earned."
)

def _observation(value: Any) -> Optional[bool]:
    """Explicit booleans only. bool is a subclass of int, so a JSON true would
    pass a naive integer check and be counted."""
    return value if isinstance(value, bool) else None


def score_seat(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Score one seat's holdout slice, deriving nothing unrecorded.

    `seen_in_extraction` is honoured here as G4 honours it. It was not, and
    the two scorers disagreeing was a way to make a seat look distinctive
    with material the reconstruction had already read: flag the items and G4
    drops them from the global figure, while this counted them and the
    profile called the seat distinctive on them. A question the
    reconstruction was built from measures nothing about transfer, in a seat
    or across one.
    """
    aligned = diverged = consensus = unknown = seen = 0
    for item in items or []:
        if item.get("seen_in_extraction") is True:
            seen += 1
            continue
        obs = _observation(item.get("aligned"))
        base = _observation(item.get("baseline_aligned"))
        if obs is None or base is None:
            unknown += 1
            continue
        if base:
            consensus += 1          # the default already gets it right
        elif obs:
            aligned += 1
        else:
            diverged += 1

    scored = aligned + diverged
    if not items or seen == len(items):
        verdict = UNFILLED
    elif scored < MIN_DIVERGENT_PER_SEAT:
        # Nothing the default gets wrong, so nothing this seat can be credited
        # for. Not a failure, just not a claim.
        verdict = GENERIC
    elif aligned / scored >= HOLDOUT_MIN_ALIGNMENT:
        verdict = DISTINCTIVE
    else:
        verdict = GENERIC

    return {
        "verdict": verdict,
        "divergent_scored": scored,
        "divergent_aligned": aligned,
        "consensus": consensus,
        "unknown": unknown,
        "seen_excluded": seen,
        "alignment": (aligned / scored) if scored else None,
    }


def build(holdout_by_seat: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """The profile, plus the claim a reconstruction is entitled to make."""
    per_seat = {seat: score_seat(holdout_by_seat.get(seat) or []) for seat in SEATS}
    claimable = [s for s, r in per_seat.items() if r["verdict"] == DISTINCTIVE]
    return {
        "seats": per_seat,
        "claimable_seats": claimable,
        "generic_seats": [s for s, r in per_seat.items() if r["verdict"] == GENERIC],
        "unfilled_seats": [s for s, r in per_seat.items() if r["verdict"] == UNFILLED],
    }


def check(holdout_by_seat: Dict[str, List[Dict[str, Any]]] | None) -> Verdict:
    """Gate on the profile.

    Fails closed on absence, and fails when no seat is distinctive: a
    reconstruction with nothing to claim is a reconstruction of nothing, and
    saying so is more useful than publishing a shell with a flattering average.
    """
    if holdout_by_seat is None:
        return Verdict(GATE, False, [
            NO_PER_SEAT_HOLDOUT])
    if not isinstance(holdout_by_seat, dict):
        return Verdict(GATE, False, ["per-seat holdout must be a mapping of seat to items"])

    unknown_seats = [s for s in holdout_by_seat if s not in SEATS]
    if unknown_seats:
        return Verdict(GATE, False, [f"unknown seat(s) {unknown_seats}"])

    prof = build(holdout_by_seat)
    errors: List[str] = []
    warnings: List[str] = []

    if not prof["claimable_seats"]:
        errors.append(
            "no seat is distinctive: on every seat, a model with no reconstruction "
            "loaded answers as well. There is nothing here to claim, and publishing it "
            "with an averaged score would hide that.")

    for seat, r in prof["seats"].items():
        if r["unknown"]:
            warnings.append(
                f"{seat}: {r['unknown']} holdout item(s) with no recorded observation or "
                "baseline; excluded rather than guessed")
        if r["verdict"] == GENERIC and r["divergent_scored"] >= MIN_DIVERGENT_PER_SEAT:
            warnings.append(
                f"{seat}: scored {r['alignment']:.0%} on questions the default gets wrong, "
                f"below {HOLDOUT_MIN_ALIGNMENT:.0%}. The skill may not claim this seat.")

    if len(prof["claimable_seats"]) == 1:
        warnings.append(
            f"only the {prof['claimable_seats'][0]} seat is claimable. That is a normal "
            "result and worth stating plainly: most practitioners are distinctive in one "
            "or two seats.")

    return Verdict(GATE, not errors, errors, warnings, prof)
