#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G1 -- source tier and consent gate.

Runs before anything is read for content: it decides which material enters the
pipeline at all, so no later stage has to ask.

Scope-independent by design. Whether the result stays on your laptop or ships
to customers, T3 material is material you were not given, and T0 material needs
the record that says you were.

Fails closed in three ways that matter:
  * a source with no tier is not "probably fine", it is an error;
  * T0 with no consent record blocks, rather than being quietly downgraded;
  * an unreadable consent file blocks, rather than being treated as absent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..contract import (
    CONSENT_REQUIRED_FIELDS,
    SOURCE_TIERS,
    TIERS_ALWAYS_FORBIDDEN,
    TIERS_REQUIRING_CONSENT,
)
from . import Verdict

GATE = "G1-consent"


def check(sources: List[Dict[str, Any]], consent_path: Optional[Path] = None) -> Verdict:
    """Validate the source manifest being delivered.

    Each entry needs at least an `id` and a `tier`.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not sources:
        # Fail closed: an empty manifest is a missing input, not a clean run.
        return Verdict(GATE, False, ["source manifest is empty; nothing to check"])

    tier_counts: Dict[str, int] = {}
    needs_consent: List[str] = []

    for i, src in enumerate(sources):
        sid = src.get("id") or f"<source #{i}>"
        tier = src.get("tier")

        if tier is None:
            errors.append(f"{sid}: no tier assigned (assign one of {list(SOURCE_TIERS)})")
            continue
        if tier not in SOURCE_TIERS:
            errors.append(f"{sid}: unknown tier {tier!r}")
            continue

        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if tier in TIERS_ALWAYS_FORBIDDEN:
            errors.append(
                f"{sid}: tier {tier} is never usable. {SOURCE_TIERS[tier]} "
                "Remove it; no consent record and no output scope unlocks it."
            )
        elif tier in TIERS_REQUIRING_CONSENT:
            needs_consent.append(sid)

    if needs_consent:
        if consent_path is None:
            errors.append(
                f"{len(needs_consent)} T0 source(s) present but no consent record given: "
                + ", ".join(needs_consent[:5])
                + (" ..." if len(needs_consent) > 5 else "")
                + ". Private material needs the record that says you may use it, "
                "even for your own private build."
            )
        else:
            record: Any = None
            try:
                record = json.loads(Path(consent_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                # Unreadable is not absent. Block.
                errors.append(f"consent record at {consent_path} could not be read: {exc}")
            if record is not None:
                if not isinstance(record, dict):
                    errors.append("consent record must be a JSON object")
                else:
                    for fld in CONSENT_REQUIRED_FIELDS:
                        val = record.get(fld)
                        if val is None or (isinstance(val, str) and not val.strip()):
                            errors.append(f"consent record missing required field {fld!r}")
                    warnings.append(
                        "consent record structure checked only; this tool cannot verify "
                        "that the signature is genuine"
                    )

    return Verdict(
        GATE, not errors, errors, warnings,
        {"source_count": len(sources), "tier_counts": tier_counts, "t0_count": len(needs_consent)},
    )
