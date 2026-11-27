# -*- coding: utf-8 -*-
"""Nothing may look verified without being verified.

Two of these got through, both found by auditing rather than by reading:

  * PUNCT_CHECKED_SUFFIXES and PUNCT_CHECKED_DIRS sat in the frozen contract
    from the first commit, asserted by a test for their shape, and read by no
    code at all. There was no validator. On its first real run the gate they
    described found 16 violations in four files;
  * the FROZEN tuple, which claims to enumerate the frozen contract values, was
    missing nine of them.

Both are the same failure: something that reads as a guarantee while nothing
holds it up, made worse by a passing test about its shape. This file is the
audit kept as a gate, because the class comes back otherwise.
"""
import ast
import re
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill import contract

ROOT = Path(__file__).resolve().parent.parent
PKG = sorted((ROOT / "persona_to_skill").rglob("*.py"))
TESTS = sorted((ROOT / "tests").glob("*.py"))


def _contract_names():
    src = (ROOT / "persona_to_skill" / "contract.py").read_text(encoding="utf-8")
    return [t.id for n in ast.parse(src).body if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name) and t.id.isupper()
            and t.id not in ("FROZEN", "PROVISIONAL", "DECLARED",
                             "CONTRACT_VERSION")]


def _refs(name, paths, skip="contract.py"):
    return sum(len(re.findall(rf"\b{name}\b", p.read_text(encoding="utf-8")))
               for p in paths if p.name != skip)


def _tiers():
    return (("FROZEN", contract.FROZEN), ("PROVISIONAL", contract.PROVISIONAL),
            ("DECLARED", contract.DECLARED))


def test_every_contract_value_is_classified():
    """Three tiers, and a value belongs to exactly one.

    FROZEN was measured or argued and changing it needs a version bump.
    PROVISIONAL is read by code and the number is still a guess, so it carries
    what would settle it and changing it needs nothing. DECLARED is prose that
    no code reads. An unclassified value is one nobody has decided about, which
    is how four guessed thresholds came to sit in FROZEN borrowing an authority
    they had not earned."""
    unclassified = [n for n in _contract_names()
                    if not any(n in group for _, group in _tiers())]
    assert not unclassified, f"unclassified contract values: {unclassified}"


def test_no_contract_value_is_in_two_tiers():
    names = _contract_names()
    for n in names:
        where = [label for label, group in _tiers() if n in group]
        assert len(where) <= 1, f"{n} is in {where}; the tiers mean different things"


def test_every_provisional_value_says_what_would_settle_it():
    """A guess is allowed. A guess with no route out of being a guess is how it
    quietly becomes permanent."""
    for name, how in contract.PROVISIONAL.items():
        assert how and len(how) > 20, f"{name} has no account of what would settle it"


def test_provisional_values_are_read_by_production_code():
    """Same rule as FROZEN: a value nothing consults is furniture whatever tier
    it sits in."""
    unwired = [n for n in contract.PROVISIONAL if _refs(n, PKG) == 0]
    assert not unwired, f"provisional value(s) read by no production code: {unwired}"


def _defined_anywhere():
    """Every upper-case module-level name in the package.

    PROVISIONAL covers guesses wherever they live. Restricting the registry to
    contract.py was half the idea: the guesses had simply scattered into the
    modules that used them, which is harder to notice rather than better.
    """
    out = set()
    for path in PKG:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                out.update(t.id for t in node.targets
                           if isinstance(t, ast.Name) and t.id.isupper())
    return out


def test_no_tier_names_a_value_that_does_not_exist():
    defined = _defined_anywhere()
    for label, group in _tiers():
        ghosts = [n for n in group if n not in defined]
        assert not ghosts, f"{label} names values that do not exist: {ghosts}"


def test_no_guessed_number_hides_outside_the_registry():
    """A bare numeric constant in a module is either measured, structural, or a
    guess. The guesses have to be registered; the others say what they are
    where they are defined."""
    exempt = {
        # measured: see the module docstrings for the figures behind them
        "MIN_SENTENCE_DENSITY", "MIN_SENTENCE_CASING",
        # structural, not a judgement call
        "HOLDOUT_MIN_ALIGNMENT", "HOLDOUT_MAX_UNKNOWN_RATIO",
        "CONTRADICTION_MAX_UNRESOLVED_RATIO",
        "CONTRADICTION_UNRESOLVED_RATIO_FLOOR",
        "CONFIDENCE_REQUIRING_NO_GAPS", "CONFIDENCE_REQUIRING_GAPS_NAMED",
        "HOLDOUT_MIN_ITEMS", "HOLDOUT_MIN_DIVERGENT_ITEMS",
    }
    unregistered = []
    for path in PKG:
        src = path.read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if not (isinstance(t, ast.Name) and t.id.isupper()):
                    continue
                if not re.match(r"^(MIN|MAX|DEFAULT|SHORT|LIMIT)_", t.id):
                    continue
                if t.id in exempt or t.id in contract.PROVISIONAL:
                    continue
                unregistered.append(f"{path.name}:{t.id}")
    assert not unregistered, (
        "numeric threshold(s) neither measured nor registered as a guess: "
        f"{unregistered}. Put it in contract.PROVISIONAL with what would "
        "settle it, or say where the measurement came from.")


def test_every_frozen_value_is_read_by_production_code():
    """THE check that was missing. A frozen value only tests read is furniture:
    it implies a gate that is not running, and the test about its shape makes
    it look verified."""
    unwired = []
    for name in contract.FROZEN:
        if _refs(name, PKG) == 0:
            unwired.append((name, _refs(name, TESTS)))
    assert not unwired, (
        "frozen contract value(s) read by no production code "
        f"(name, test references): {unwired}. Either wire it into a gate, or "
        "move it to DECLARED and say it is prose.")


def test_declared_prose_is_not_read_for_a_decision():
    """The reverse: if code starts branching on one of these, it is no longer
    prose and belongs in FROZEN with a gate behind it."""
    for name in contract.DECLARED:
        hits = _refs(name, PKG)
        assert hits == 0, (
            f"{name} is declared as prose but production code reads it "
            f"({hits} references). Move it to FROZEN and give it a gate.")


def test_every_gate_module_is_covered_by_the_teeth_test():
    teeth = (ROOT / "tests" / "test_gates_have_teeth.py").read_text(encoding="utf-8")
    for p in PKG:
        m = re.search(r'^GATE = "([^"]+)"', p.read_text(encoding="utf-8"), re.M)
        if m:
            assert f'"{m.group(1)}"' in teeth, f"{m.group(1)} has no broken-input case"


def test_no_ci_step_swallows_its_own_failure():
    """A step that cannot fail is the CI version of the same problem."""
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        assert "continue-on-error" not in text, f"{wf.name} has continue-on-error"
        for m in re.finditer(r"- name: (.+)", text):
            tail = text[m.end():m.end() + 400]
            nxt = tail.find("- name:")
            body = tail[:nxt if nxt != -1 else len(tail)]
            assert "|| true" not in body, f"{wf.name}: step {m.group(1)!r} swallows failure"


def test_every_source_file_is_tracked_by_git():
    """Source that exists locally and is not in the repository is the same
    family: something looks complete and is not.

    It happened. `.gitignore` carried an unanchored `build/`, which also
    matched `persona_to_skill/build/`, so `git add -A` skipped a whole
    subpackage in silence. The commit described work it did not contain, every
    test passed locally, and CI on four platforms was the only thing that
    noticed, several minutes later. The subpackage is now called `deliver` and
    the pattern is anchored, but the class needs a guard rather than a memory.
    """
    import subprocess

    tracked = set(subprocess.run(
        ["git", "ls-files", "persona_to_skill", "tests", "experiments"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split())
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for d in ("persona_to_skill", "tests", "experiments")
        for p in (ROOT / d).rglob("*.py")
        if "__pycache__" not in p.parts
    }
    untracked = sorted(on_disk - tracked)
    assert not untracked, (
        "Python source present on disk and not in the repository:\n  "
        + "\n  ".join(untracked)
        + "\nCheck .gitignore for an unanchored pattern; `git add -A` skips these "
          "without saying so.")


def test_gitignore_patterns_that_should_be_anchored_are():
    """`build/` matches at every level, not only the root. The same is true of
    `dist/`, and of anything else named after a conventional output directory
    that could also be a legitimate package name."""
    lines = [ln.strip() for ln in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    for pattern in ("build/", "dist/", "docs/", "lib/", "src/", "test/"):
        assert pattern not in lines, (
            f"{pattern!r} in .gitignore is unanchored, so it also matches "
            f"persona_to_skill/{pattern}. Write /{pattern} to mean the root only.")


def test_no_except_clause_swallows_silently():
    """`except ...: pass` with nothing said is the same family as an unwired
    contract value: something is being discarded and the reader cannot tell
    whether that was the intent.

    Swallowing is sometimes right. force_utf8 does it on purpose, because a
    stream that cannot be reconfigured is not a reason to end a run. The rule
    is that the reason has to be written at the except, where someone changing
    it will see it, not only in a docstring they may not read.
    """
    import io
    import tokenize

    bad = []
    for path in PKG + TESTS:
        src = path.read_text(encoding="utf-8")
        lines = src.splitlines()
        comment_lines = set()
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                comment_lines.add(tok.start[0])
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.ExceptHandler):
                continue
            body = node.body
            if not (len(body) == 1 and isinstance(body[0], ast.Pass)):
                continue
            span = range(node.lineno, (body[0].lineno) + 1)
            if not any(ln in comment_lines for ln in span):
                bad.append(f"{path.name}:{node.lineno}: {lines[node.lineno - 1].strip()}")
    assert not bad, ("except clause(s) that pass with no comment saying why:\n  "
                     + "\n  ".join(bad))


def test_the_punctuation_gate_actually_exists_now():
    """Named explicitly because its absence is what prompted this file."""
    from persona_to_skill import validate_punct
    assert callable(validate_punct.check_file)
    assert callable(validate_punct.in_fullwidth_scope)
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "validate_punct" in ci, "the gate exists but CI does not run it"


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
