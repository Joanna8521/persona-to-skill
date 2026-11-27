#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A contradiction is the find, not the problem.

Corpora do not change their minds; people do. A practitioner who argued one
thing in 2021 and the opposite in 2024 has rarely reversed. Usually an unstated
condition changed, and recovering that condition is the most valuable thing in
a whole reconstruction, because it is a criterion the subject has never spelled
out anywhere. Nobody can quote it, because it was never said.

So the earlier design here was wrong. "Use the newest, and record what changed"
treats a contradiction as noise to be resolved, and resolving it discards the
only thing that was worth having. Every record now has to answer one question:
what condition makes both sides true.

Fail-closed, and this is the rule that matters. Where no condition can be
found, the record stays UNRESOLVED and ships as something worth digging into.
Picking the newer side is not an available outcome, because it looks like
progress and is actually a deletion.

One lesser benefit, kept because it is real: a reconstruction that knows what
its subject has abandoned will not quote them on it, which is the fastest way
such an adviser loses credibility.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import (
    CONTRADICTION_MAX_UNRESOLVED_RATIO,
    CONTRADICTION_REQUIRED_FIELDS,
    CONTRADICTION_STATUSES,
    CONTRADICTION_UNRESOLVED_RATIO_FLOOR,
)
from ..gates import Verdict

GATE = "B-contradictions"

_SIDE_FIELDS = ("claim", "source_id", "quote")


# Named rather than written inline. Inside a list a wrapped string and a
# missing comma look identical, and a stray comma here would turn one error
# into two, each half a sentence.
NOT_EVEN_AN_EMPTY_LIST = (
    "no contradiction records supplied, not even an empty list. "
    "Finding none is a result; not having looked is not."
)

def _side_errors(label: str, side: Any) -> List[str]:
    if not isinstance(side, dict):
        return [f"{label}: must be an object with {list(_SIDE_FIELDS)}"]
    missing = [k for k in _SIDE_FIELDS if not str(side.get(k, "")).strip()]
    if missing:
        why = (f"{label}: missing {', '.join(missing)}. Both sides of a "
               f"contradiction are quotes, or there is no contradiction to "
               f"reconcile.")
        return [why]
    return []


def check(records: List[Dict[str, Any]] | None) -> Verdict:
    """Validate contradiction records.

    An empty list is allowed: a corpus may genuinely hold none, and inventing
    one would be worse. `None` is not, because "we did not look" and "we looked
    and found none" are different claims and only one of them is a finding.
    """
    if records is None:
        return Verdict(GATE, False, [
            NOT_EVEN_AN_EMPTY_LIST])
    if not isinstance(records, (list, tuple)):
        return Verdict(GATE, False, ["contradiction records must be a list"])

    errors: List[str] = []
    warnings: List[str] = []
    reconciled = unresolved = 0

    for i, rec in enumerate(records):
        label = rec.get("id") if isinstance(rec, dict) else None
        label = label or f"<contradiction #{i}>"
        if not isinstance(rec, dict):
            errors.append(f"{label}: must be an object")
            continue

        for field in CONTRADICTION_REQUIRED_FIELDS:
            if field not in rec:
                errors.append(f"{label}: missing {field!r}")

        errors.extend(_side_errors(f"{label}.earlier", rec.get("earlier")))
        errors.extend(_side_errors(f"{label}.later", rec.get("later")))

        status = rec.get("status")
        if status not in CONTRADICTION_STATUSES:
            errors.append(f"{label}: status {status!r} must be one of "
                          f"{list(CONTRADICTION_STATUSES)}")
            continue

        condition = str(rec.get("reconciling_condition") or "").strip()
        if status == "reconciled":
            reconciled += 1
            if not condition:
                errors.append(
                    f"{label}: marked reconciled with no reconciling_condition. "
                    "The condition IS the finding; without it this is just two quotes.")
        else:
            unresolved += 1
            if condition:
                errors.append(
                    f"{label}: marked unresolved but names a reconciling_condition. "
                    "If the condition holds, the record is reconciled; if it does not, "
                    "remove it.")
            if not str(rec.get("why_unresolved") or "").strip():
                warnings.append(
                    f"{label}: unresolved without saying what was tried. A reader "
                    "digging into this needs to know where you stopped.")

        # The shape the fail-closed rule exists to refuse.
        if rec.get("resolution") in ("latest", "newest", "later"):
            errors.append(
                f"{label}: resolved by taking the later side. That is not a resolution, "
                "it is a deletion: the unstated condition that changed is the most "
                "valuable thing here, and it has just been thrown away. Mark the record "
                "unresolved instead and say what you tried.")

    total = reconciled + unresolved
    ratio = (unresolved / total) if total else None

    # "Unresolved is the intended outcome" is true at three and false at three
    # hundred. A corpus full of positions no condition reconciles is itself the
    # finding: the stance moves as a tactic rather than with circumstances, and
    # there may be no reconstructible method here. Producing hundreds of "worth
    # digging into" entries and calling that normal is the failure.
    #
    # The floor is there because the ratio is meaningless on a handful: two of
    # three unresolved is 67% and says nothing.
    if (total >= CONTRADICTION_UNRESOLVED_RATIO_FLOOR
            and ratio is not None and ratio > CONTRADICTION_MAX_UNRESOLVED_RATIO):
        errors.append(
            f"{unresolved} of {total} contradictions ({ratio:.0%}) have no reconciling "
            f"condition, above {CONTRADICTION_MAX_UNRESOLVED_RATIO:.0%}. At this rate the "
            "unresolved ones are not dig sites, they are the result: positions that no "
            "condition reconciles suggest a stance that moves as a tactic rather than "
            "with circumstances, and there may be no reconstructible method here. Report "
            "that rather than shipping a list of things to look into.")
    elif unresolved:
        warnings.append(
            f"{unresolved} of {total} contradiction(s) unresolved and flagged for "
            "digging. At this rate that is the intended outcome when no condition can be "
            "found, not a failure.")

    return Verdict(GATE, not errors, errors, warnings,
                   {"records": len(records), "reconciled": reconciled,
                    "unresolved": unresolved,
                    "unresolved_ratio": None if ratio is None else round(ratio, 3)})
