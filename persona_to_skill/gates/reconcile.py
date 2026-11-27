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

import re
from collections import Counter
from typing import Any, Dict, List

from . import Verdict
from .holdout import _observation, format_alignment, score

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
    """Counted as the scorers see them: True, False and UNKNOWN are three
    things, not two.

    `bool()` collapsed a missing or null observation into False, so a global
    list recording `aligned: null` and a per-seat list recording
    `aligned: false` compared equal while the scorers read them as 0
    divergent items scored against 5. The gate reported consistency between
    two genuinely different runs, which is the failure it exists to catch.
    """
    return Counter((_observation(i.get("aligned")),
                    _observation(i.get("baseline_aligned")))
                   for i in items)


_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")


_INTEGER = re.compile(r"\d+")


def _counts_are_supported(stated: str, allowed: set) -> list:
    """Integers in the disclosure that no count in the holdout supports.

    Only the percentage was compared, so a five-item divergent pool accepted
    "100% over 500 divergent items" and "100% from 999 total". Those numbers
    go into SKILL.md verbatim, under a label saying they were measured.

    The two counts that can honestly appear are the size of the divergent
    pool and the size of the holdout. Anything else is a number the holdout
    does not support, whatever word sits next to it.
    """
    without_percentages = _PERCENT.sub(" ", stated)
    found = {int(m.group(0)) for m in _INTEGER.finditer(without_percentages)}
    return sorted(found - allowed)


def _states_exactly(stated: str, gated_text: str) -> bool:
    """Does this disclosure state the computed figure, and only it?

    A substring test passed `180% over 5` and `not 80%` when the computed
    figure was `80%`: the gate built to stop a disclosure contradicting the
    computation accepted text that contradicted it. Two conditions now:

      * the string starts with the figure, so a longer number containing it
        and a negation in front of it both fail;
      * every percentage in the string is that figure, so a second, different
        number cannot ride along behind the first.
    """
    stripped = stated.strip()
    if gated_text == "not measured":
        return stripped.startswith(gated_text)
    if not stripped.startswith(gated_text):
        return False
    rest = stripped[len(gated_text):]
    if rest[:1].isdigit() or rest[:1] == "%":
        return False
    found = {m.group(0).replace(" ", "") for m in _PERCENT.finditer(stripped)}
    return found <= {gated_text}


def _name(value: Any) -> str:
    """UNKNOWN is a sentinel, not a bool, so it has no order against one."""
    return {True: "yes", False: "no"}.get(value, "unknown")


def _describe(counter: Counter) -> str:
    parts = [f"aligned={_name(a)} baseline_aligned={_name(b)}: {n}"
             for (a, b), n in sorted(counter.items(),
                                     key=lambda kv: (_name(kv[0][0]),
                                                     _name(kv[0][1])))]
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

    # Shape before content. A bundle supplying `holdout_by_seat: []` is not
    # None, so it got past the check above and crashed package.run on
    # `.values()`, which is worse than any verdict: a crash is not a finding
    # a reader can act on, and it loses the errors the other gates collected.
    if not isinstance(holdout, list):
        return Verdict(GATE, False, [
            f"holdout must be a list of observations, not {type(holdout).__name__}"])
    if not isinstance(by_seat, dict):
        wrong_shape = ("holdout_by_seat must be a mapping of seat to "
                       f"observations, not {type(by_seat).__name__}")
        return Verdict(GATE, False, [wrong_shape])
    bad_seats = sorted(k for k, v in by_seat.items() if not isinstance(v, list))
    if bad_seats:
        return Verdict(GATE, False, [
            f"these seats do not hold a list of observations: {bad_seats}"])

    # When every observation carries an id, the comparison is exact: which
    # seat each item landed in, not just how many of each kind there are.
    # Without ids the aggregate is all there is, and the gate says so rather
    # than letting silence imply the assignment was checked.
    flat = [i for v in by_seat.values() for i in v]
    ids_everywhere = (bool(holdout) and bool(flat)
                      and all(i.get("id") for i in holdout)
                      and all(i.get("id") for i in flat))

    if ids_everywhere:
        global_ids = {str(i["id"]) for i in holdout}
        seat_ids = {str(i["id"]) for i in flat}
        if len(seat_ids) != len(flat):
            errors.append(
                "the same observation id appears under more than one seat. "
                "Each eval item has exactly one seat.")
        if global_ids != seat_ids:
            only_global = sorted(global_ids - seat_ids)
            only_seats = sorted(seat_ids - global_ids)
            errors.append(
                "holdout and holdout_by_seat cover different items.\n"
                f"    only in holdout:        {only_global or 'none'}\n"
                f"    only in holdout_by_seat: {only_seats or 'none'}")
        by_id = {str(i["id"]): i for i in holdout}
        moved = [str(i["id"]) for i in flat
                 if str(i["id"]) in by_id
                 and _observations([i]) != _observations([by_id[str(i["id"])]])]
        if moved:
            errors.append(
                "these observations differ between holdout and "
                f"holdout_by_seat: {sorted(set(moved))}")
    else:
        warnings.append(
            "observations carry no ids, so only the totals are reconciled. "
            "Moving an observation from one seat to another leaves those "
            "totals unchanged while reversing which seat the profile tells a "
            "reader to trust, and nothing here can see it. Give each "
            "observation the id of its eval item to close that.")

    whole = _observations(holdout)
    slices = _observations(flat)
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
        elif not _states_exactly(stated, gated_text):
            errors.append(
                f"disclosure.holdout_alignment says {stated!r}, and the "
                f"divergent-pool alignment computed from the holdout is "
                f"{gated_text}. The label on that line names the divergent pool, "
                "so the raw figure across both pools is the wrong number "
                "under it.")
        else:
            unsupported = _counts_are_supported(
                stated, {computed["divergent"]["scored"], len(holdout)})
            if unsupported:
                errors.append(
                    f"disclosure.holdout_alignment states {stated!r}, and "
                    f"{unsupported} matches no count in the holdout: the "
                    f"divergent pool has {computed['divergent']['scored']} "
                    f"item(s) and the holdout has {len(holdout)}.")

    return Verdict(GATE, not errors, errors, warnings, {
        "items": sum(whole.values()),
        "gated_alignment": gated,
        "divergent_scored": computed["divergent"]["scored"],
    })
