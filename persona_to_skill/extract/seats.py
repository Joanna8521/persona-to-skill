#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The seats, and what each one owes.

What is extracted is not what the subject concluded. A cited conclusion is
still a conclusion, and an adviser who walks in and says "looks fine" is
useless whether or not the sentence carries a footnote. So the unit of
extraction is a seat in a deliberation, defined by what the subject does in it:
how they carve the problem up, what they argue against, what evidence they
demand before moving, which number they say decides it.

Three things this module enforces, each of them a decision about what the
output is for rather than a detail of its shape.

ADVERSARIAL BY DEFAULT. The first seat that takes a position is oppose;
decompose precedes it only because a problem has to be carved up before
anything can be objected to. The support seat exists and is never volunteered.
The dangerous user is not the one with no view; it is the one who already has
an answer, holding a reconstruction of somebody they admire, because agreement
in that voice does not read as flattery, it reads as confirmation.

AN UNFILLED SEAT IS NOT AN ABSENT TRAIT. A seat with nothing in it means the
corpus had nothing to say, not that the subject does not deliberate that way.
The two are reported differently, and conflating them would let a thin corpus
pass itself off as a finding about a person.

EVERY SEAT ENTRY IS A CLAIM. Entries carry a source and a quote, or are marked
as inference, which is exactly the shape G2 reconciles. The seats are therefore
not a separate honesty system; they feed the one that already exists.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contract import (
    SEAT_ENTRY_ORDER,
    SEAT_OBLIGATIONS,
    SEATS,
    SEATS_ON_REQUEST_ONLY,
)
from ..gates import Verdict

GATE = "B-seats"

# An entry either rests on the corpus or says it does not.
_ANCHORED = ("claim", "source_id", "quote")
_INFERRED = ("claim", "derived_from")


def _is_entry(item: Any) -> bool:
    return isinstance(item, dict) and bool(str(item.get("claim", "")).strip())


def entry_errors(seat: str, field: str, i: int, item: Any) -> List[str]:
    """What is wrong with one entry. Empty list means it is well formed."""
    where = f"{seat}.{field}[{i}]"
    if not isinstance(item, dict):
        return [f"{where}: entries must be objects with a claim"]
    if not str(item.get("claim", "")).strip():
        return [f"{where}: no claim"]

    if item.get("attribution") == "inference":
        missing = [k for k in _INFERRED if not item.get(k)]
        if missing:
            return [f"{where}: marked as inference but missing {', '.join(missing)}"]
        return []

    missing = [k for k in _ANCHORED if not str(item.get(k, "")).strip()]
    if missing:
        return [
            f"{where}: attributed to the subject but missing {', '.join(missing)}. "
            "Either anchor it in the corpus, or mark it "
            '{"attribution": "inference", "derived_from": [...]}'
        ]
    return []


def seat_entries(bundle: Dict[str, Any], seat: str) -> List[Dict[str, Any]]:
    """Every entry in a seat, flattened, for handing to G2."""
    out: List[Dict[str, Any]] = []
    record = (bundle.get("seats") or {}).get(seat) or {}
    for field in SEAT_OBLIGATIONS.get(seat, ()):
        for item in record.get(field) or []:
            if _is_entry(item):
                out.append(item)
    return out


def all_entries(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for seat in SEATS for e in seat_entries(bundle, seat)]


def filled_fields(bundle: Dict[str, Any], seat: str) -> List[str]:
    record = (bundle.get("seats") or {}).get(seat) or {}
    return [f for f in SEAT_OBLIGATIONS.get(seat, ())
            if any(_is_entry(i) for i in (record.get(f) or []))]


def unfilled_seats(bundle: Dict[str, Any]) -> List[str]:
    """Seats the corpus could not fill. Reported, never silently dropped."""
    return [s for s in SEATS if not filled_fields(bundle, s)]


def check(bundle: Dict[str, Any] | None) -> Verdict:
    """Validate a reconstruction bundle's seat structure.

    This does not judge whether a seat's content is true. It judges whether the
    output is the kind of thing the gates can check, and whether it refuses to
    volunteer the support seat.
    """
    if bundle is None:
        return Verdict(GATE, False, ["no bundle supplied"])
    if not isinstance(bundle, dict):
        return Verdict(GATE, False, ["bundle must be a mapping"])

    errors: List[str] = []
    warnings: List[str] = []
    seats = bundle.get("seats")
    if not isinstance(seats, dict) or not seats:
        return Verdict(GATE, False, [
            f"bundle has no seats. Every reconstruction is organised by seat: {list(SEATS)}"])

    unknown = [s for s in seats if s not in SEATS]
    if unknown:
        errors.append(f"unknown seat(s) {unknown}; expected {list(SEATS)}")

    for seat in SEATS:
        record = seats.get(seat)
        if record is None:
            continue
        if not isinstance(record, dict):
            errors.append(f"{seat}: must be an object keyed by "
                          f"{list(SEAT_OBLIGATIONS[seat])}")
            continue
        stray = [f for f in record if f not in SEAT_OBLIGATIONS[seat]]
        if stray:
            errors.append(f"{seat}: unknown field(s) {stray}; "
                          f"this seat owes {list(SEAT_OBLIGATIONS[seat])}")
        for field in SEAT_OBLIGATIONS[seat]:
            items = record.get(field)
            if items is None:
                continue
            if not isinstance(items, (list, tuple)):
                errors.append(f"{seat}.{field}: must be a list of entries")
                continue
            for i, item in enumerate(items):
                errors.extend(entry_errors(seat, field, i, item))

    # An unfilled seat is a finding about the corpus, and has to be stated as
    # one rather than left to look like a finding about the person.
    unfilled = unfilled_seats(bundle)
    if len(unfilled) == len(SEATS):
        errors.append("every seat is empty; there is no reconstruction here")
    elif unfilled:
        declared = bundle.get("unfilled_seats_acknowledged")
        if sorted(declared or []) != sorted(unfilled):
            errors.append(
                f"seat(s) {unfilled} have nothing in them and the bundle does not say so. "
                "List them in unfilled_seats_acknowledged. An empty seat means the corpus "
                "had nothing to say, not that the subject does not deliberate that way, "
                "and a reader cannot tell the difference unless it is written down.")

    # Adversarial by default.
    order = bundle.get("entry_order")
    if order is None:
        errors.append(
            f"bundle declares no entry_order. It must be {list(SEAT_ENTRY_ORDER)}: the "
            "first seat that takes a position is oppose, because the user most at risk "
            "is the one who already has an answer and wants it confirmed by a voice "
            "they trust.")
    elif list(order) != list(SEAT_ENTRY_ORDER):
        errors.append(f"entry_order is {list(order)}, expected {list(SEAT_ENTRY_ORDER)}")

    for seat in SEATS_ON_REQUEST_ONLY:
        if seat in (order or []):
            errors.append(
                f"the {seat} seat is in entry_order. It is reachable on request and never "
                "volunteered: the deliverable is what this subject would object to, not "
                "what they would advise.")

    if filled_fields(bundle, "oppose") == [] and "oppose" not in unfilled:
        warnings.append("the oppose seat is the one the output leads with; check it is the "
                        "best-filled seat, not the thinnest")

    return Verdict(
        GATE, not errors, errors, warnings,
        {
            "seats_filled": {s: filled_fields(bundle, s) for s in SEATS
                             if filled_fields(bundle, s)},
            "unfilled": unfilled,
            "entries": len(all_entries(bundle)),
        },
    )
