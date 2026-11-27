#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-reconcile: the figures in the deliverable against the computed ones.

Three places in a bundle state the same measurement, and until this gate
existed nothing compared them:

  * `holdout`, the observations G4 scores;
  * `holdout_by_seat`, the per-seat slices B-profile scores;
  * `disclosure.holdout_alignment`, free text that the rendered SKILL.md
    publishes under the label "Measured alignment where a model with no
    reconstruction answers wrongly".

A worked example in this repository shipped an archive whose holdout-report
said 100% over 5 divergent items while its SKILL.md disclosed 92% over 12,
and whose per-seat lists totalled fifteen observations against a global set
of twelve. Nine gates passed. Every one of those numbers reads as measured,
and a reader has no way to tell which is.

The per-seat lists are slices of one run: the eval manifest gives each item
exactly one seat, so the slices partition the whole. Comparing them as
multisets of (aligned, baseline_aligned) catches a list written twice without
demanding the two be in the same order, which would be a different claim.

Fails closed. A bundle with no holdout cannot be reconciled, and G4 already
refuses that case; saying nothing here would turn the absence into a pass.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from . import Verdict
from .holdout import format_alignment, score

GATE = "B-reconcile"

NO_HOLDOUT = (
    "no holdout set supplied, so nothing can be reconciled against it. "
    "G4 refuses this case too; passing here would let the absence of "
    "the measurement stand in for the measurement."
)

NO_BY_SEAT = (
    "no per-seat holdout supplied. B-profile refuses this case, and "
    "without it the per-seat figures in the report rest on nothing."
)


def _observations(items: List[Dict[str, Any]]) -> Counter:
    return Counter((bool(i.get("aligned")), bool(i.get("baseline_aligned")))
                   for i in items)


def _describe(counter: Counter) -> str:
    parts = [f"aligned={a} baseline_aligned={b}: {n}"
             for (a, b), n in sorted(counter.items())]
    return "; ".join(parts) or "nothing"


def check(holdout: List[Dict[str, Any]] | None,
          by_seat: Dict[str, List[Dict[str, Any]]] | None,
          disclosure: Dict[str, Any] | None,
          scope: str | None) -> Verdict:
    """Reconcile every stated figure against the one the code computes."""
    errors: List[str] = []
    warnings: List[str] = []

    if holdout is None:
        return Verdict(GATE, False, [NO_HOLDOUT])

    if by_seat is None:
        return Verdict(GATE, False, [NO_BY_SEAT])

    whole = _observations(holdout)
    slices = _observations([i for v in by_seat.values() for i in v])
    if whole != slices:
        errors.append(
            "holdout and holdout_by_seat describe different runs. Each eval "
            "item has exactly one seat, so the per-seat lists are slices of "
            "the whole and the two must agree.\n"
            f"    holdout        {sum(whole.values())} item(s): {_describe(whole)}\n"
            f"    holdout_by_seat {sum(slices.values())} item(s): {_describe(slices)}")

    computed = score(holdout)
    gated = computed["gated_alignment"]
    gated_text = format_alignment(gated)

    if scope == "PUBLISHED":
        stated = str((disclosure or {}).get("holdout_alignment") or "").strip()
        if not stated:
            errors.append(
                "PUBLISHED scope publishes disclosure.holdout_alignment under "
                "the label \"Measured alignment where a model with no "
                "reconstruction answers wrongly\", and none was supplied.")
        elif gated is None:
            errors.append(
                "disclosure.holdout_alignment states "
                f"{stated!r} while nothing was scored in the divergent pool, "
                "so there is no measurement for it to be reporting.")
        elif gated_text not in stated:
            errors.append(
                f"disclosure.holdout_alignment says {stated!r}, and the "
                f"divergent-pool alignment computed from the holdout is "
                f"{gated_text}. The label on that line names the divergent pool, "
                "so the raw figure across both pools is the wrong number "
                "under it.")

    return Verdict(GATE, not errors, errors, warnings, {
        "items": sum(whole.values()),
        "gated_alignment": gated,
        "divergent_scored": computed["divergent"]["scored"],
    })
