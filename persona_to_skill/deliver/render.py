#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a reconstruction bundle into the files that ship.

Seven files, and the shape of each is a decision already argued for elsewhere
in this package. What this module adds is that the decisions survive into the
text a reader actually sees:

  * the first seat in SKILL.md that takes a position is oppose, because the
    user most at risk is the one who already has an answer;
  * SKILL.md states the per-seat profile, so the skill claims only the seats it
    earned and the reader knows where not to lean;
  * SKILL.md never says "you are <name>". It is written to apply a documented
    method and to cite it;
  * contradictions.md keeps the unresolved ones, flagged, because the
    unresolved ones are the dig sites;
  * sensitivity.md leads with the quantity that is not yet in hand, because
    that is the one the reader can act on alone.

Rendering is deliberately dumb. Everything here is a transcription of a
validated bundle; nothing is decided, inferred or summarised. If a file would
need a judgement to write, that judgement belongs in extraction, where a gate
can see it.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ..contract import SEAT_ENTRY_ORDER, SEAT_OBLIGATIONS, SEATS
from ..extract import profile as profile_mod

FILES = (
    "SKILL.md",
    "decision-table.md",
    "refusals.md",
    "contradictions.md",
    "sensitivity.md",
    "sources.json",
    "holdout-report.md",
)


# ── the prose each rendered file opens with ─────────────
#
# Named rather than written inline. Inside a list a wrapped string and a
# missing comma look identical: a stray comma turns one paragraph into two
# list entries, a missing one merges two into one, and neither raises
# anything. These paragraphs are the first thing a reader of the delivered
# skill sees, so they are also the ones a silent change would most affect.

WHY_REFUSALS = (
    "Anyone can paraphrase a practitioner's positive claims. Almost nobody can "
    "guess the conditions under which they decline, which is why this file "
    "behaves like a fingerprint.\n"
)

WHY_CONTRADICTIONS = (
    "A contradiction is the find, not the problem. Someone who argued one thing "
    "and later the opposite has rarely reversed: usually an unstated condition "
    "changed, and that condition is a criterion they have never spelled out "
    "anywhere, so nobody can quote it.\n"
)

WHY_SENSITIVITY = (
    "Most hesitation is not disagreement, it is a missing number. For each class "
    "of decision below, one quantity decides the answer. Where the number is not "
    "in hand, the next step is to go and find it.\n"
)

WHY_HOLDOUT = (
    "Questions this subject answered in public, held back from extraction, and "
    "split by a recorded baseline: the same question answered with no "
    "reconstruction loaded.\n"
)

def _name(bundle: Dict[str, Any]) -> str:
    return str((bundle.get("subject") or {}).get("name") or "the subject")


def _cite(item: Dict[str, Any]) -> str:
    if item.get("attribution") == "inference":
        derived = ", ".join(str(d) for d in (item.get("derived_from") or []))
        return f" *(inference from {derived})*"
    return f" [{item.get('source_id')}]"


def _entries(bundle: Dict[str, Any], seat: str, field: str) -> List[Dict[str, Any]]:
    return list(((bundle.get("seats") or {}).get(seat) or {}).get(field) or [])


def _bullets(items: List[Dict[str, Any]]) -> str:
    return "\n".join(f"- {i.get('claim')}{_cite(i)}" for i in items) or "- *(nothing in the corpus)*"


# --------------------------------------------------------------------- SKILL.md
def skill_md(bundle: Dict[str, Any]) -> str:
    name = _name(bundle)
    prof = profile_mod.build(bundle.get("holdout_by_seat") or {})
    claimable = prof["claimable_seats"]
    generic = prof["generic_seats"]
    unfilled = prof["unfilled_seats"]

    out: List[str] = []
    out.append(f"# {name}: reconstructed method\n")
    out.append(
        f"Apply the publicly documented method of {name}, citing the source for every "
        f"attributed claim. Do not answer as {name}, and do not present anything here as "
        f"{name} speaking.\n")

    if bundle.get("scope") == "PUBLISHED":
        d = bundle.get("disclosure") or {}
        out.append("## Disclosure\n")
        out.append(f"- {d.get('reconstruction_notice', '')}")
        out.append(f"- {d.get('not_endorsed', '')}")
        out.append(f"- Built from {d.get('source_count', '?')} sources, "
                   f"retrieved {d.get('retrieved_date', '?')}.")
        out.append(f"- Measured alignment where a model with no reconstruction answers "
                   f"wrongly: {d.get('holdout_alignment', '?')}\n")

    out.append("## What this reconstruction may be used for\n")
    if claimable:
        out.append("Distinctive, meaning a model with no reconstruction gets these "
                   "questions wrong and this one gets them right:\n")
        for s in claimable:
            out.append(f"- **{s}** ({SEATS[s]})")
        out.append("")
    if generic:
        out.append("Generic, meaning the default answer is already as good. **Do not lean "
                   "on this reconstruction here:**\n")
        out.append("- " + ", ".join(f"{s} ({SEATS[s]})" for s in generic) + "\n")
    if unfilled:
        out.append("No material. The corpus had nothing for these seats, which is a fact "
                   "about the corpus and not about how "
                   f"{name} thinks:\n")
        out.append("- " + ", ".join(f"{s} ({SEATS[s]})" for s in unfilled) + "\n")

    out.append("## How to use this\n")
    out.append(
        "Answer in the order below. Decompose first, because a problem has to be carved "
        "up before anything can be objected to; then oppose, which is the first seat "
        "that takes a position. That order is deliberate: if you arrive with a "
        "conclusion already, the objections are what you came for, and agreement would "
        "tell you nothing you did not already believe.\n")
    for i, seat in enumerate(SEAT_ENTRY_ORDER, 1):
        out.append(f"{i}. **{seat}** ({SEATS[seat]})")
    out.append("")
    out.append("The support seat is available on request and is never volunteered.\n")
    out.append("Where the deciding quantity in `sensitivity.md` is not in hand, the answer "
               "is to go and find that number. Not advice.\n")

    for seat in SEAT_ENTRY_ORDER:
        fields = [(f, _entries(bundle, seat, f)) for f in SEAT_OBLIGATIONS[seat]]
        if not any(items for _, items in fields):
            continue
        out.append(f"## {seat} ({SEATS[seat]})\n")
        for field, items in fields:
            if not items:
                continue
            out.append(f"### {field.replace('_', ' ')}\n")
            out.append(_bullets(items) + "\n")

    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------- decision-table.md
def decision_table_md(bundle: Dict[str, Any]) -> str:
    name = _name(bundle)
    first = _entries(bundle, "decompose", "first_question")
    criteria = _entries(bundle, "evidence", "demanded_before_acting")
    refuses = _entries(bundle, "oppose", "refusals")
    out = [f"# {name}: decision table\n",
           "| Situation | Asked first | Criteria | Refuses |",
           "|---|---|---|---|"]
    rows = max(len(first), len(criteria), len(refuses), 1)
    for i in range(rows):
        def cell(items, i):
            return (items[i].get("claim") + _cite(items[i])) if i < len(items) else ""
        out.append(f"| {i + 1} | {cell(first, i)} | {cell(criteria, i)} | {cell(refuses, i)} |")
    out.append("\nEvery cell carries its source. An empty cell means the corpus had "
               "nothing, not that there is nothing.\n")
    return "\n".join(out)


# ------------------------------------------------------------------ refusals.md
def refusals_md(bundle: Dict[str, Any]) -> str:
    name = _name(bundle)
    items = _entries(bundle, "oppose", "refusals")
    out = [f"# {name}: what they refuse\n", WHY_REFUSALS,
           _bullets(items), ""]
    pm = _entries(bundle, "oppose", "premortem")
    if pm:
        out += ["## Where they expect it to fail\n", _bullets(pm), ""]
    return "\n".join(out)


# ------------------------------------------------------------ contradictions.md
def contradictions_md(bundle: Dict[str, Any]) -> str:
    name = _name(bundle)
    records = bundle.get("contradictions") or []
    out = [f"# {name}: contradictions\n", WHY_CONTRADICTIONS]
    if not records:
        out.append("None found in this corpus.\n")
        return "\n".join(out)

    unresolved = [r for r in records if r.get("status") == "unresolved"]
    for r in records:
        out.append(f"## {r.get('id', '')}\n")
        out.append(f"- Earlier: {r['earlier'].get('claim')} [{r['earlier'].get('source_id')}]")
        out.append(f"- Later: {r['later'].get('claim')} [{r['later'].get('source_id')}]")
        if r.get("status") == "reconciled":
            out.append(f"- **Both hold when:** {r.get('reconciling_condition')}\n")
        else:
            out.append("- **Unresolved.** No condition found that makes both true.")
            if r.get("why_unresolved"):
                out.append(f"- Tried: {r['why_unresolved']}\n")
            else:
                out.append("")
    if unresolved:
        out.append(f"\n{len(unresolved)} unresolved. These are the dig sites: an unstated "
                   "criterion is in there somewhere. Taking the later side would look "
                   "like progress and would delete it.\n")
    return "\n".join(out)


# -------------------------------------------------------------- sensitivity.md
def sensitivity_md(bundle: Dict[str, Any]) -> str:
    name = _name(bundle)
    records = list(bundle.get("sensitivity") or [])
    # Not in hand first: those are the ones the reader can act on alone.
    records.sort(key=lambda r: bool(r.get("known")))
    out = [f"# {name}: what decides it\n", WHY_SENSITIVITY]
    for r in records:
        out.append(f"## {r.get('decision_class')}\n")
        out.append(f"- Quantity: **{r.get('quantity')}**")
        out.append(f"- Threshold: **{r.get('threshold')}** ({r.get('direction')}) "
                   f"[{r.get('source_id')}]")
        if r.get("known"):
            out.append(f"- Observed: {r.get('observed_value')}\n")
        else:
            out.append("- **Not in hand.** The answer here is a lookup, not advice.")
            if r.get("how_to_find"):
                out.append(f"- How to get it: {r['how_to_find']}\n")
            else:
                out.append("")
    return "\n".join(out)


# ----------------------------------------------------------------- sources.json
def sources_json(bundle: Dict[str, Any]) -> str:
    return json.dumps({
        "subject": bundle.get("subject"),
        "version": bundle.get("version"),
        "corpus_fingerprint": bundle.get("corpus_fingerprint"),
        "sources": bundle.get("sources") or [],
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ------------------------------------------------------------ holdout-report.md
def holdout_report_md(bundle: Dict[str, Any]) -> str:
    from ..gates import holdout as holdout_gate
    name = _name(bundle)
    items = bundle.get("holdout") or []
    s = holdout_gate.score(items)
    prof = profile_mod.build(bundle.get("holdout_by_seat") or {})

    out = [f"# {name}: holdout report\n", WHY_HOLDOUT,
           "| | Count |", "|---|---|",
           f"| Divergent pool, aligned | {s['divergent']['aligned']} |",
           f"| Divergent pool, diverged | {s['divergent']['diverged']} |",
           f"| Consensus pool (reported, not gated) | {s['consensus']['scored']} |",
           f"| No observation recorded | {s['unknown']} |",
           f"| Seen during extraction, excluded | {s['seen_excluded']} |", ""]
    gated = s["gated_alignment"]
    out.append(f"**Gated alignment: "
               f"{'not measured' if gated is None else f'{gated:.0%}'}**, on the questions "
               "where a model with no reconstruction answers wrongly. The consensus pool "
               "is excluded on purpose: a reconstruction answers those correctly whether "
               "or not it learned anything.\n")
    out.append("## Per seat\n")
    out.append("| Seat | Verdict | Divergent scored | Alignment |")
    out.append("|---|---|---|---|")
    for seat, r in prof["seats"].items():
        al = "n/a" if r["alignment"] is None else f"{r['alignment']:.0%}"
        out.append(f"| {seat} | {r['verdict']} | {r['divergent_scored']} | {al} |")
    out.append("\nA single figure would average this away. The reader needs to know which "
               "seats to lean on, which is what the verdict column is for.\n")
    return "\n".join(out)


RENDERERS = {
    "SKILL.md": skill_md,
    "decision-table.md": decision_table_md,
    "refusals.md": refusals_md,
    "contradictions.md": contradictions_md,
    "sensitivity.md": sensitivity_md,
    "sources.json": sources_json,
    "holdout-report.md": holdout_report_md,
}


def render_all(bundle: Dict[str, Any]) -> Dict[str, str]:
    """Every deliverable, as {filename: text}. Nothing written to disk here."""
    return {name: fn(bundle) for name, fn in RENDERERS.items()}
