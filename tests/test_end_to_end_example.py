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
    for name in ("README.md", "records.json", "bundle.json",
                 "eval-manifest.json", "eval-run.json"):
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


def test_the_commands_in_the_readme_work():
    """import, eval, gates, package, exactly as the README types them."""
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        out = Path(tmp) / "out"

        imported = _cli("import", "examples/end-to-end/records.json",
                        "--subject", "A. Example", "--tier", "T1",
                        "--corpus", str(corpus), cwd=ROOT)
        assert imported.returncode == 0, imported.stdout + imported.stderr
        # Derived from the records, not listed here. The first version named
        # two files and broke the moment the example gained a third source.
        records = json.loads(
            (EXAMPLE / "records.json").read_text(encoding="utf-8"))
        expected = sorted(f"{r['id']}.txt" for r in records)
        written = sorted(p.name for p in corpus.glob("*.txt"))
        assert written == expected, f"{written} != {expected}"

        evaluated = _cli("eval", "examples/end-to-end/eval-manifest.json",
                         "--run", "examples/end-to-end/eval-run.json",
                         "--corpus", str(corpus), "--subject", "A. Example",
                         cwd=ROOT)
        assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr

        gated = _cli("gates", "--corpus", str(corpus),
                     "examples/end-to-end/bundle.json", cwd=ROOT)
        assert gated.returncode == 0, gated.stdout + gated.stderr
        assert "9/9 gates passed" in gated.stdout, gated.stdout

        packaged = _cli("package", "--corpus", str(corpus), "--out", str(out),
                        "examples/end-to-end/bundle.json", cwd=ROOT)
        assert packaged.returncode == 0, packaged.stdout + packaged.stderr
        zips = list(out.glob("*.zip"))
        assert len(zips) == 1, [p.name for p in zips]


def _documented_archive_listing():
    """The fenced block of archive paths in the example README."""
    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8").splitlines()
    listed, inside = [], False
    for line in readme:
        if line.strip() == "```":
            if inside:
                if listed:
                    return listed
                inside = False
            continue
        if line.startswith("a-example-method/"):
            inside = True
            listed.append(line.strip())
    return listed


def test_the_readme_archive_listing_matches_the_archive_exactly():
    """Compared in both directions.

    The first version of this test only checked that every archived file
    appeared somewhere in the README. A file renamed or dropped by packaging
    would leave its old line sitting in the README while every remaining name
    still matched, so the test stayed green while the documented listing was
    wrong. That is the same one-way check that lets a stale figure survive.
    """
    import zipfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        out = Path(tmp) / "out"
        _cli("import", "examples/end-to-end/records.json",
             "--subject", "A. Example", "--tier", "T1",
             "--corpus", str(corpus), cwd=ROOT)
        _cli("package", "--corpus", str(corpus), "--out", str(out),
             "examples/end-to-end/bundle.json", cwd=ROOT)
        archive = next(iter(out.glob("*.zip")))
        packaged = sorted(zipfile.ZipFile(archive).namelist())

    documented = sorted(_documented_archive_listing())
    assert documented, "no archive listing found in the example README"
    assert documented == packaged, (
        f"\n  in the archive but not the README: {sorted(set(packaged) - set(documented))}"
        f"\n  in the README but not the archive: {sorted(set(documented) - set(packaged))}")


def test_the_holdout_in_the_bundle_is_the_eval_run():
    """`bundle.json`'s observations and `eval-run.json`'s are the same twelve.

    Before this they were written separately: the per-seat lists totalled
    fifteen observations against a global set of twelve, and both numbers
    shipped inside one archive. Nothing in the product reconciles them, which
    is a gap being fixed separately; here they are derived from one list and
    this keeps them that way.
    """
    from collections import Counter  # noqa: PLC0415

    bundle = json.loads((EXAMPLE / "bundle.json").read_text(encoding="utf-8"))
    run = json.loads((EXAMPLE / "eval-run.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (EXAMPLE / "eval-manifest.json").read_text(encoding="utf-8"))

    def key(item):
        return (bool(item["aligned"]), bool(item["baseline_aligned"]))

    from_run = Counter(key(i) for i in run["items"])
    from_global = Counter(key(i) for i in bundle["holdout"])
    assert from_global == from_run, (
        f"bundle holdout {dict(from_global)} vs eval run {dict(from_run)}")

    # Per seat, joined on the item id. Flattening holdout_by_seat and
    # comparing totals passed when five divergent observations were moved
    # from oppose to evidence, which is the swap that changes which seat the
    # packaged profile tells a reader to trust.
    seat_of = {i["id"]: i["seat"] for i in manifest["items"]}
    expected = {}
    for item in run["items"]:
        expected.setdefault(seat_of[item["id"]], Counter())[key(item)] += 1
    actual = {seat: Counter(key(i) for i in items)
              for seat, items in bundle["holdout_by_seat"].items()}
    assert actual == expected, (
        f"\n  bundle per seat: { {k: dict(v) for k, v in actual.items()} }"
        f"\n  eval run per seat: { {k: dict(v) for k, v in expected.items()} }")


def test_the_readme_reports_every_warning_the_run_produced():
    """The README says how many gates passed with a warning and tables them.

    It said four when there were five, and the table left out G3's. A
    transcript that quietly drops a warning is not a transcript, and the
    number in the prose was not recomputed from anything.
    """
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        _cli("import", "examples/end-to-end/records.json",
             "--subject", "A. Example", "--tier", "T1",
             "--corpus", str(corpus), cwd=ROOT)
        gated = _cli("gates", "--corpus", str(corpus),
                     "examples/end-to-end/bundle.json", cwd=ROOT)

    warned = sorted(_warned_gates(gated.stdout))
    readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")

    # Searched inside the table, not the whole file. Looking anywhere in the
    # README passed with the G2-anchor row deleted, because that gate is
    # named several times in the prose above it.
    tabled = "\n".join(line for line in readme.splitlines()
                        if line.startswith("| `"))
    assert tabled, "no warning table found in the example README"
    missing = [g for g in warned if f"| `{g}` |" not in tabled]
    assert not missing, f"the README table does not list these warnings: {missing}"

    spelled = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
               "six": 6, "seven": 7, "eight": 8, "nine": 9}
    import re as _re  # noqa: PLC0415
    match = _re.search(r"and (\w+) of them passed while saying", readme)
    assert match, "the README does not state how many gates warned"
    assert spelled.get(match.group(1)) == len(warned), (
        f"the README says {match.group(1)}, the run produced {len(warned)}: "
        f"{warned}")


def _warned_gates(stdout):
    """Gate names whose block contains a (warning) line."""
    current, warned = None, set()
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith(("PASS", "FAIL")):
            current = stripped.split()[1]
        elif "(warning)" in stripped and current:
            warned.add(current)
    return warned


def test_no_holdout_question_reuses_material_the_bundle_cites():
    """Held back means held back.

    Four of the twelve questions once had ground truths that were, verbatim,
    quotes the reconstruction itself was built from: a holdout item whose
    answer is in the bundle is not a holdout item. Two of those four were in
    the divergent pool, so excluding them would have left three against G4's
    minimum of five, and the archive's "100% over 5 divergent items" rested on
    contaminated material.

    The harness cannot catch this. `anchor_manifest` says so in as many
    words: nothing in the files shows whether a question was held back, and
    `seen_in_extraction` is the author's declaration. So it is checked here,
    for this example, and the limit is the product's to close.
    """
    bundle = json.loads((EXAMPLE / "bundle.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (EXAMPLE / "eval-manifest.json").read_text(encoding="utf-8"))

    cited = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("quote"):
                cited.add(node["quote"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(bundle)
    assert cited, "the bundle cites no quotes at all, so this proves nothing"

    overlapping = []
    for item in manifest["items"]:
        said = item["subject_said"]
        if any(q in said or said in q for q in cited):
            overlapping.append(f"{item['id']}: {said}")
    assert not overlapping, (
        "these holdout answers are material the reconstruction was built "
        "from:\n  " + "\n  ".join(overlapping))


def test_the_eval_run_and_the_package_agree():
    """Both read the same observations and both state a figure, and nothing
    in the product compares them.

    With `blind: false` on every item the harness refused to score at all and
    exited 1, while `package` produced an archive publishing 100% from the
    same twelve observations. An example that shipped that contradiction
    would be demonstrating the defect rather than the tool.
    """
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        out = Path(tmp) / "out"
        _cli("import", "examples/end-to-end/records.json",
             "--subject", "A. Example", "--tier", "T1",
             "--corpus", str(corpus), cwd=ROOT)
        evaluated = _cli("eval", "examples/end-to-end/eval-manifest.json",
                         "--run", "examples/end-to-end/eval-run.json",
                         "--corpus", str(corpus), "--subject", "A. Example",
                         cwd=ROOT)
        packaged = _cli("package", "--corpus", str(corpus), "--out", str(out),
                        "examples/end-to-end/bundle.json", cwd=ROOT)

    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    assert packaged.returncode == 0, packaged.stdout + packaged.stderr

    bundle = json.loads((EXAMPLE / "bundle.json").read_text(encoding="utf-8"))
    stated = bundle["disclosure"]["holdout_alignment"]
    figure = stated.split("%")[0].strip() + "%"
    assert figure in evaluated.stdout, (
        f"the disclosure says {stated!r} and the harness did not print "
        f"{figure}")

    # The denominator too. Checking only the percentage let "100% over 5"
    # stand while an excluded item made the harness report 100% over four:
    # the same figure over a sample size nothing supports.
    divergent = sum(1 for i in bundle["holdout"] if not i["baseline_aligned"])
    assert f"| Divergent | {divergent} |" in evaluated.stdout.replace("  ", " "), (
        f"the bundle has {divergent} divergent observations and the harness "
        f"did not report that many")
    import re as _re  # noqa: PLC0415
    stated_counts = {int(n) for n in _re.findall(r"\d+", stated.split("%", 1)[1])}
    assert stated_counts <= {divergent, len(bundle["holdout"])}, (
        f"the disclosure states {stated_counts}, and the holdout has "
        f"{divergent} divergent of {len(bundle['holdout'])}")


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
