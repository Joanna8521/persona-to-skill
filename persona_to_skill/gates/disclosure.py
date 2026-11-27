#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G3: disclosure and impersonation.

The one gate that depends on output scope, because it is the only one about
informing a third party. It reads the generated skill text about to be
delivered, not a template, not a fixture.

PUBLISHED scope blocks on:
  * any instruction telling a model to be, act as, or speak as the subject;
  * a missing or incomplete disclosure block.

These encode the test courts actually apply. In the US the 2024-2026
digital-replica statutes reach voice and visual likeness, and first-person
impersonation is the text form nearest that line. In Taiwan the questions are
混淆誤認之虞 (likelihood of confusion) and 攀附知名度 (riding on someone's
reputation); a disclosure block and a non-impersonating voice address both.

PRIVATE scope requires no disclosure, since nobody is being informed, and
downgrades impersonation to a warning about effectiveness rather than law. See
contract.IMPERSONATION_RATIONALE_PRIVATE. A private builder who wants
impersonation anyway gets it; the tool states why it is a worse tool and
proceeds. Deciding that for them is not this gate's job.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ..contract import (
    DISCLOSURE_REQUIRED_KEYS,
    IMPERSONATION_PATTERNS,
    IMPERSONATION_RATIONALE_PRIVATE,
    OUTPUT_SCOPES,
)
from . import Verdict

GATE = "G3-disclosure"


def _name_variants(name: str) -> List[str]:
    """Build the forms a generated file might plausibly use for the subject."""
    name = name.strip()
    out = {name}
    if " " in name:                       # Western given/family name
        out.update(p for p in name.split() if len(p) > 1)
    if len(name) >= 3 and " " not in name and re.search(r"[一-鿿]", name):
        out.add(name[1:])                 # 王小明 -> 小明
    return [re.escape(v) for v in sorted(out, key=len, reverse=True) if v]


def check(skill_text: str, subject_name: str, scope: str,
          disclosure: Dict[str, Any] | None = None) -> Verdict:
    """Check the artifact being delivered.

    `skill_text` is the generated skill, read from the file about to ship.
    `scope` is one of contract.OUTPUT_SCOPES.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if scope not in OUTPUT_SCOPES:
        return Verdict(GATE, False, [f"unknown output scope {scope!r}; "
                                     f"expected one of {list(OUTPUT_SCOPES)}"])
    if not skill_text or not skill_text.strip():
        return Verdict(GATE, False, ["no skill text supplied; nothing to check"])
    if not subject_name or not subject_name.strip():
        # Without a name there is no impersonation check to run. Block.
        return Verdict(GATE, False, ["subject_name is required to check for impersonation"])

    variants = _name_variants(subject_name)
    alternation = "(?:" + "|".join(variants) + ")"
    hits: List[str] = []

    for pattern in IMPERSONATION_PATTERNS:
        compiled = re.compile(pattern.replace("{name}", alternation), re.IGNORECASE)
        for m in compiled.finditer(skill_text):
            line = skill_text[: m.start()].count("\n") + 1
            hits.append(f"line {line}: {m.group(0).strip()!r}")

    if hits:
        listing = ("\n    " + "\n    ".join(hits[:10])
                   + (f"\n    ... and {len(hits) - 10} more" if len(hits) > 10 else ""))
        if scope == "PUBLISHED":
            errors.append(
                "impersonation instruction(s) found. Published output must apply a "
                "documented method, not stand in for the person:" + listing
            )
        else:
            # Private use: the builder's call. Say why it works less well.
            warnings.append(
                "impersonation instruction(s) found:" + listing
                + "\n  " + IMPERSONATION_RATIONALE_PRIVATE
            )

    if scope == "PUBLISHED":
        if not disclosure:
            errors.append(
                "PUBLISHED scope requires a disclosure block; none supplied "
                f"(needs {list(DISCLOSURE_REQUIRED_KEYS)})"
            )
        else:
            for key in DISCLOSURE_REQUIRED_KEYS:
                val = disclosure.get(key)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append(f"disclosure block missing required key {key!r}")
        if "inference" in skill_text.lower() or "推論" in skill_text:
            warnings.append("output contains inference labels; confirm each is attached to a claim")

    return Verdict(
        GATE, not errors, errors, warnings,
        {"scope": scope, "impersonation_hits": len(hits), "name_variants": len(variants)},
    )
