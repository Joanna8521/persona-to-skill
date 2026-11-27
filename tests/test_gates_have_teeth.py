# -*- coding: utf-8 -*-
"""Meta-test: every gate must reject a deliberately broken input.

A gate that cannot fail is worse than no gate, because it grants false
confidence. This file is the check that each of the four gates still bites, and
it exists as its own file so CI can run it alone: see
.github/workflows/gates-intact.yml.

That is the point. A fork may change anything about this project, but a fork
that guts a gate while keeping the name goes red here, publicly, on its own
pull requests.

Deliberately written against the gates' public surface only, so it keeps
working as internals change.
"""
import importlib
import json
import pkgutil
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill import contract, gates
from persona_to_skill.gates import anchor, consent, disclosure, holdout, interrogation


def _discovered_gates():
    """Read the gate list off the package rather than hardcoding it.

    A hardcoded list is the fail-open version of this file: add a gate, forget
    to add it here, and the coverage test below goes green while the new gate
    ships unguarded. That happened once, with G5.
    """
    found = {}
    for mod in pkgutil.iter_modules(gates.__path__):
        m = importlib.import_module(f"persona_to_skill.gates.{mod.name}")
        name = getattr(m, "GATE", None)
        if name and callable(getattr(m, "check", None)):
            found[name] = m
    return found


GATE_MODULES = _discovered_gates()
GATES = tuple(sorted(GATE_MODULES))


def _corpus():
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("Nothing quotable lives here.", encoding="utf-8")
    return d


def _consent(data):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return Path(f.name)


GOOD_MEMO = {
    "decision": "d", "options": ["a", "b", "c"], "known_facts": ["f"],
    "consensus": ["c"], "conflicts": ["x"], "key_assumptions": ["a1"],
    "main_risks": ["r"], "evidence_gaps": ["g"],
    "flip_condition": {"quantity": "q", "threshold": "t", "known": True},
    "recommendation": {"verdict": "REVISE", "depends_on": ["f1"]},
    "confidence": {"level": 0.6, "rationale": "why"}, "next_actions": ["n"],
}
GOOD_STATEMENTS = [{"id": "f1", "class": "FACT", "text": "plain", "source_id": "s1"}]


# Each entry: a call that MUST be rejected, and why it must be.
BROKEN = [
    ("G1-consent", "prohibited-tier material",
     lambda: consent.check([{"id": "leak", "tier": "T3"}])),
    ("G1-consent", "private material with no consent record",
     lambda: consent.check([{"id": "s1", "tier": "T0"}])),
    ("G1-consent", "a source with no tier",
     lambda: consent.check([{"id": "mystery"}])),
    ("G2-anchor", "a quote that is not in its source",
     lambda: anchor.check(
         [{"id": "c", "text": "x", "source_id": "s1", "quote": "he definitely said this"}],
         _corpus())),
    ("G2-anchor", "an attributed claim naming no source",
     lambda: anchor.check([{"id": "c", "text": "He always walks away."}], _corpus())),
    ("G2-anchor", "no corpus to verify against",
     lambda: anchor.check([{"id": "c", "text": "x", "source_id": "s1", "quote": "y"}],
                          Path("/nonexistent"))),
    ("G3-disclosure", "an impersonation instruction in published output",
     lambda: disclosure.check("You are A. Example. Answer as him.", "A. Example",
                              "PUBLISHED", {k: "set" for k in contract.DISCLOSURE_REQUIRED_KEYS})),
    ("G3-disclosure", "published output with no disclosure block",
     lambda: disclosure.check("Apply the documented method of A. Example.",
                              "A. Example", "PUBLISHED", None)),
    ("G4-holdout", "no holdout set at all",
     lambda: holdout.check(None)),
    ("G4-holdout", "a consensus-padded holdout set",
     lambda: holdout.check(
         [{"aligned": True, "baseline_aligned": False}] * 5
         + [{"aligned": False, "baseline_aligned": False}] * 5
         + [{"aligned": True, "baseline_aligned": True}] * 40)),
    ("G4-holdout", "holdout items with no baseline recorded",
     lambda: holdout.check([{"aligned": True}] * 20)),
    ("G5-interrogation", "a memo with a field left unanswered",
     lambda: interrogation.check(
         {k: v for k, v in GOOD_MEMO.items() if k != "main_risks"}, GOOD_STATEMENTS)),
    ("G5-interrogation", "a claim classified as fact with no source",
     lambda: interrogation.check(
         GOOD_MEMO, [{"id": "f1", "class": "FACT", "text": "plain"}])),
    ("G5-interrogation", "a fact hedged with 'should be'",
     lambda: interrogation.check(
         GOOD_MEMO,
         [{"id": "f1", "class": "FACT", "text": "it should be around 12%",
           "source_id": "s1"}])),
    ("G5-interrogation", "a committing verdict while the deciding number is unknown",
     lambda: interrogation.check(
         GOOD_MEMO | {"flip_condition": {"quantity": "q", "threshold": "t", "known": False}},
         GOOD_STATEMENTS)),
    ("G5-interrogation", "high confidence alongside open evidence gaps",
     lambda: interrogation.check(
         GOOD_MEMO | {"confidence": {"level": 0.95, "rationale": "feels right"}},
         GOOD_STATEMENTS)),
    ("G5-interrogation", "a memo with no classified statements",
     lambda: interrogation.check(GOOD_MEMO, None)),
]


def test_every_gate_rejects_broken_input():
    for gate, what, call in BROKEN:
        v = call()
        assert not v.passed, f"{gate} accepted {what}"
        assert v.errors, f"{gate} rejected {what} without saying why"
        assert v.gate == gate, f"verdict reports {v.gate!r}, expected {gate!r}"


def test_every_gate_is_covered_by_this_file():
    """A gate added without a broken-input case here would ship unguarded. The
    gate list is discovered from the package, so forgetting to extend it is
    what goes red -- not silently nothing."""
    covered = {g for g, _, _ in BROKEN}
    assert covered == set(GATES), (
        f"gate(s) with no broken-input case: {sorted(set(GATES) - covered)}; "
        f"case(s) for an unknown gate: {sorted(covered - set(GATES))}")


def test_discovery_found_every_gate_module():
    assert len(GATES) >= 5, f"discovered only {GATES}"
    for mod in (consent, anchor, disclosure, holdout, interrogation):
        assert mod.GATE in GATE_MODULES


def test_every_gate_rejects_its_missing_input():
    """Fail-closed, checked per gate. The quiet pass on an absent optional
    input is the failure mode that disables a gate without removing it."""
    assert not consent.check([]).passed
    assert not anchor.check([], _corpus()).passed
    assert not disclosure.check("", "A. Example", "PUBLISHED", {}).passed
    assert not holdout.check(None).passed
    assert not interrogation.check(None, None).passed


def test_a_clean_input_still_passes():
    """The gates must discriminate, not merely refuse everything."""
    d = Path(tempfile.mkdtemp())
    (d / "s1.txt").write_text("I walk away rather than discount.", encoding="utf-8")
    assert consent.check([{"id": "s1", "tier": "T1"}]).passed
    assert anchor.check(
        [{"id": "c", "text": "Walks away.", "source_id": "s1",
          "quote": "I walk away rather than discount"}], d).passed
    assert disclosure.check("Apply the documented method of A. Example.", "A. Example",
                            "PUBLISHED",
                            {k: "set" for k in contract.DISCLOSURE_REQUIRED_KEYS}).passed
    assert holdout.check([{"aligned": True, "baseline_aligned": False}] * 10).passed
    assert interrogation.check(GOOD_MEMO, GOOD_STATEMENTS).passed


def test_frozen_thresholds_are_not_relaxed():
    """A fork may raise these. Lowering them silently is the other way to gut a
    gate while keeping its name."""
    assert contract.HOLDOUT_MIN_ALIGNMENT >= 0.80
    assert contract.HOLDOUT_MIN_ITEMS >= 10
    assert contract.HOLDOUT_MIN_DIVERGENT_ITEMS >= 5
    assert contract.HOLDOUT_MAX_UNKNOWN_RATIO <= 0.30
    assert "T3" in contract.TIERS_ALWAYS_FORBIDDEN
    assert "T0" in contract.TIERS_REQUIRING_CONSENT
    assert len(contract.IMPERSONATION_PATTERNS) >= 11
    assert set(contract.DISCLOSURE_REQUIRED_KEYS) >= {
        "reconstruction_notice", "not_endorsed", "holdout_alignment"}
    # The memo schema is load-bearing in the same way: a field dropped from it
    # is a field nobody is made to face.
    assert set(contract.MEMO_REQUIRED_FIELDS) >= {
        "key_assumptions", "main_risks", "evidence_gaps", "flip_condition",
        "confidence", "recommendation"}
    assert contract.CONFIDENCE_REQUIRING_NO_GAPS <= 0.70
    assert len(contract.EVASION_PHRASES) >= 8
    assert len(contract.HEDGE_MARKERS) >= 12


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
