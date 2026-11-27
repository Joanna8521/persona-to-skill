# -*- coding: utf-8 -*-
"""The worked example in examples/end-to-end/, run as a test.

An example in a README is a claim about what happens when someone types those
commands. This runs them, so the claim is checked rather than asserted.

Writing the example found a real bug in the example: its `entry_order` was
retyped by hand and listed `support`, which is reachable on request and never
volunteered, while leaving `interrogate` out altogether. `B-seats` caught all
three consequences. The fix was to read the order out of the contract, and
`test_the_example_takes_its_seat_order_from_the_contract` keeps it that way,
because a hand-written copy of a frozen constant drifts the moment the
constant moves.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.contract import (SEATS, SEAT_ENTRY_ORDER,
                                       SEATS_ON_REQUEST_ONLY)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "end-to-end"


def _cli(*args, cwd):
    return subprocess.run([sys.executable, "-m", "persona_to_skill.cli", *args],
                          cwd=cwd, capture_output=True, text=True, check=False)


def test_the_example_files_are_all_there():
    for name in ("README.md", "records.json", "bundle.json"):
        assert (EXAMPLE / name).is_file(), name


def test_the_example_takes_its_seat_order_from_the_contract():
    """Not a style preference. `support` in entry_order is a contract
    violation, and `interrogate` missing from both entry_order and
    unfilled_seats_acknowledged is another."""
    bundle = json.loads((EXAMPLE / "bundle.json").read_text(encoding="utf-8"))

    assert bundle["entry_order"] == list(SEAT_ENTRY_ORDER)
    for seat in SEATS_ON_REQUEST_ONLY:
        assert seat not in bundle["entry_order"], (
            f"{seat} is reachable on request and never volunteered")

    filled = set(bundle["seats"])
    expected = [s for s in SEATS if s not in filled]
    assert sorted(bundle["unfilled_seats_acknowledged"]) == sorted(expected)


def test_the_three_commands_in_the_readme_work():
    """import, then gates, then package, exactly as the README types them."""
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        out = Path(tmp) / "out"

        imported = _cli("import", "examples/end-to-end/records.json",
                        "--subject", "A. Example", "--tier", "T1",
                        "--corpus", str(corpus), cwd=ROOT)
        assert imported.returncode == 0, imported.stdout + imported.stderr
        written = sorted(p.name for p in corpus.glob("*.txt"))
        assert written == ["s1.txt", "s9.txt"], written

        gated = _cli("gates", "--corpus", str(corpus),
                     "examples/end-to-end/bundle.json", cwd=ROOT)
        assert gated.returncode == 0, gated.stdout + gated.stderr
        assert "9/9 gates passed" in gated.stdout, gated.stdout

        packaged = _cli("package", "--corpus", str(corpus), "--out", str(out),
                        "examples/end-to-end/bundle.json", cwd=ROOT)
        assert packaged.returncode == 0, packaged.stdout + packaged.stderr
        zips = list(out.glob("*.zip"))
        assert len(zips) == 1, [p.name for p in zips]


def test_the_readme_does_not_claim_a_file_list_the_archive_does_not_have():
    """The README prints the archive's contents. If packaging starts writing a
    different set of files, the README becomes a confident description of
    something that no longer happens."""
    import zipfile  # noqa: PLC0415

    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        out = Path(tmp) / "out"
        _cli("import", "examples/end-to-end/records.json",
             "--subject", "A. Example", "--tier", "T1",
             "--corpus", str(corpus), cwd=ROOT)
        _cli("package", "--corpus", str(corpus), "--out", str(out),
             "examples/end-to-end/bundle.json", cwd=ROOT)
        archive = next(iter(out.glob("*.zip")))
        names = zipfile.ZipFile(archive).namelist()

    missing = [n for n in names if n not in readme]
    assert not missing, f"the README does not list: {missing}"


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
