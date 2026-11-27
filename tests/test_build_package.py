# -*- coding: utf-8 -*-
"""Stage C, end to end: render, gate, package.

The ordering is what these tests are really about. Rendering happens before
the gates so G3 reads the text a reader will see; packaging happens strictly
after, so a failing gate means there is no archive to install.
"""
import json
import tempfile
import zipfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.deliver import package, render
from persona_to_skill.contract import SEAT_ENTRY_ORDER, SEATS

CORPUS = {
    "s1": "I walk away from a stalled deal rather than discount. "
          "Discounting to close teaches the buyer that waiting works. "
          "Below 1,200 a store never reaches breakeven, so we stop.",
    "s9": "These days I would rather find a local partner than open our own store.",
}


def corpus_dir():
    d = Path(tempfile.mkdtemp())
    for sid, text in CORPUS.items():
        (d / f"{sid}.txt").write_text(text, encoding="utf-8")
    return d


def _e(claim, quote, sid="s1"):
    return {"claim": claim, "source_id": sid, "quote": quote}


_DIV = {"aligned": True, "baseline_aligned": False}
_CON = {"aligned": True, "baseline_aligned": True}
_HOLDOUT_BY_SEAT = {
    "oppose": [dict(_DIV) for _ in range(6)],
    "evidence": [dict(_DIV) for _ in range(4)],
    "decompose": [dict(_CON) for _ in range(2)],
}
_HOLDOUT_BY_SEAT_FLAT = [x for v in _HOLDOUT_BY_SEAT.values() for x in v]


def bundle(**over):
    b = {
        "subject": {"name": "A. Example", "slug": "a-example"},
        "version": "1.0",
        "scope": "PUBLISHED",
        "seats": {
            "oppose": {
                "premortem": [_e("Dies on single-store economics",
                                 "a store never reaches breakeven")],
                "refusals": [_e("Will not discount to close",
                                "I walk away from a stalled deal rather than discount")],
                "underestimated": [{"claim": "Localisation cost",
                                    "attribution": "inference",
                                    "derived_from": ["s1"]}],
            },
            "evidence": {
                "demanded_before_acting": [_e("Cost per store before any rollout",
                                              "Below 1,200 a store never reaches breakeven")],
            },
            "decompose": {
                "first_question": [_e("How long has it been stalled",
                                      "I walk away from a stalled deal")],
            },
        },
        "entry_order": list(SEAT_ENTRY_ORDER),
        "unfilled_seats_acknowledged": [s for s in SEATS
                                        if s not in ("oppose", "evidence", "decompose")],
        "contradictions": [{
            "id": "c1",
            "earlier": _e("Open our own store", "I walk away from a stalled deal"),
            "later": {"claim": "Find a local partner", "source_id": "s9",
                      "quote": "I would rather find a local partner"},
            "status": "unresolved", "reconciling_condition": "",
            "why_unresolved": "no market-size figure in either source",
        }],
        "sensitivity": [{
            "id": "f1", "decision_class": "opening a store",
            "quantity": "cost per store", "threshold": "1,200",
            "direction": "above_stops", "source_id": "s1",
            "quote": "Below 1,200 a store never reaches breakeven",
            "known": False, "how_to_find": "run one store for a quarter",
        }],
        "sources": [{"id": "s1", "tier": "T1", "authorship": "self_written"},
                    {"id": "s9", "tier": "T1", "authorship": "self_written"}],
        # Derived, not written twice. B-reconcile caught this fixture
        # claiming 12 observations globally and 15 across its seats, which is
        # the defect that gate was added for; a fixture that cannot hold two
        # numbers in step is not a fixture for testing that the product can.
        "holdout": [dict(x) for x in _HOLDOUT_BY_SEAT_FLAT],
        "holdout_by_seat": {k: [dict(x) for x in v]
                            for k, v in _HOLDOUT_BY_SEAT.items()},
        "disclosure": {
            "reconstruction_notice": "Reconstructed from 2 public sources; not the person.",
            "not_endorsed": "A. Example did not author, review, or endorse this.",
            "source_count": 2, "holdout_alignment": "100% on divergent questions",
            "retrieved_date": "2026-11-27",
        },
    }
    b.update(over)
    return b


def build(**over):
    return package.run(bundle(**over), corpus_dir(), Path(tempfile.mkdtemp()))


# ------------------------------------------------------------------ 成功路徑
def test_a_complete_bundle_produces_a_zip():
    path, verdicts, errors = build()
    assert errors == [], errors
    assert path and path.is_file()
    assert all(v.passed for v in verdicts)


def test_the_filename_carries_the_version_and_the_inner_directory_does_not():
    """檔名回答「三個下載檔哪個是現在的」；內部目錄是安裝路徑，跟著版號變
    會讓每次更新多裝一份而不是替換。"""
    path, _, _ = build()
    assert path.name == "a-example-method-v1.0.zip", path.name
    with zipfile.ZipFile(path) as z:
        tops = {n.split("/")[0] for n in z.namelist()}
    assert tops == {"a-example-method"}, tops
    assert not any("v1.0" in n for n in zipfile.ZipFile(path).namelist())


def test_all_seven_deliverables_are_in_the_archive():
    path, _, _ = build()
    with zipfile.ZipFile(path) as z:
        got = {n.split("/", 1)[1] for n in z.namelist()}
    assert got == set(render.FILES), got


def test_paths_are_ascii_and_the_archive_reads_back():
    path, _, _ = build()
    with zipfile.ZipFile(path) as z:
        assert all(all(ord(c) < 128 for c in n) for n in z.namelist())
        assert z.testzip() is None


def test_a_manifest_records_the_fingerprint_and_the_gates():
    path, _, _ = build()
    m = json.loads((path.parent / f"{path.stem}.manifest.json").read_text(encoding="utf-8"))
    assert m["inner_directory"] == "a-example-method"
    assert m["version"] == "v1.0"
    assert len(m["corpus_fingerprint"]) == 16
    assert "G2-anchor" in m["gates_passed"] and "B-seats" in m["gates_passed"]


def test_the_same_corpus_fingerprints_the_same():
    a, b = corpus_dir(), corpus_dir()
    assert package.corpus_fingerprint(a) == package.corpus_fingerprint(b)


def test_a_changed_corpus_fingerprints_differently():
    d = corpus_dir()
    before = package.corpus_fingerprint(d)
    (d / "s1.txt").write_text("something else entirely.", encoding="utf-8")
    assert package.corpus_fingerprint(d) != before


# ------------------------------------- 閘門不過就沒有 zip，這是整個順序的理由
def test_a_failing_gate_leaves_no_archive():
    path, verdicts, errors = build(sources=[{"id": "leak", "tier": "T3"}])
    assert path is None
    assert errors and any("G1-consent" in e for e in errors)


def test_a_fabricated_quote_leaves_no_archive():
    b = bundle()
    b["seats"]["oppose"]["refusals"] = [_e("Never negotiates",
                                           "I never negotiate under any circumstances")]
    path, _, errors = package.run(b, corpus_dir(), Path(tempfile.mkdtemp()))
    assert path is None
    assert any("G2-anchor" in e for e in errors)


def test_an_invented_threshold_leaves_no_archive():
    """門檻是最值錢的欄位，所以也是最該擋住憑空生成的那個。"""
    b = bundle()
    b["sensitivity"][0]["threshold"] = "9,999"
    b["sensitivity"][0]["quote"] = "Below 9,999 a store never reaches breakeven"
    path, _, errors = package.run(b, corpus_dir(), Path(tempfile.mkdtemp()))
    assert path is None
    assert any("G2-anchor" in e for e in errors)


def test_volunteering_the_support_seat_leaves_no_archive():
    path, _, errors = build(entry_order=["decompose", "support"] + list(SEAT_ENTRY_ORDER[1:]))
    assert path is None
    assert any("B-seats" in e for e in errors)


def test_no_version_leaves_no_archive():
    path, verdicts, errors = build(version="")
    assert path is None
    assert all(v.passed for v in verdicts), "gates should pass; only the version is missing"
    assert any("filename carries it" in e for e in errors)


# ------------------------ G3 驗的是算繪出來的文字，不是產生它的結構
def test_g3_reads_the_rendered_skill_md():
    """能冒名的是算繪出來的 SKILL.md，不是結構化的 bundle。驗 bundle 等於
    在驗沒有人會讀的東西。"""
    original = render.skill_md

    def impersonating(bundle_):
        return "You are A. Example. Answer as him.\n"

    render.skill_md = impersonating
    render.RENDERERS["SKILL.md"] = impersonating
    try:
        path, _, errors = build()
    finally:
        render.skill_md = original
        render.RENDERERS["SKILL.md"] = original
    assert path is None
    assert any("G3-disclosure" in e for e in errors)


# ----------------------------------------------- 算繪出來的內容必須守住設計
def test_skill_md_refuses_to_impersonate_and_says_so():
    text = render.skill_md(bundle())
    assert "Do not answer as A. Example" in text
    assert "You are A. Example" not in text


def test_the_first_position_taking_seat_is_oppose():
    """拆解在前是因為要先把問題切開才有東西可以反對，而拆解不是一個立場。
    第一個表態的席是反方，而支持席永不出現在順序裡。"""
    text = render.skill_md(bundle())
    assert text.index("1. **decompose**") < text.index("2. **oppose**")
    assert text.index("2. **oppose**") < text.index("3. **evidence**")
    assert "**support**" not in text.split("## How to use this")[1].split("##")[0]
    assert "support seat is available on request and is never volunteered" in text


def test_skill_md_states_which_seats_may_not_be_leaned_on():
    text = render.skill_md(bundle())
    assert "Do not lean on this reconstruction here" in text
    assert "decompose" in text.split("Do not lean")[1][:200]


def test_skill_md_carries_the_disclosure_when_published():
    assert "## Disclosure" in render.skill_md(bundle())
    assert "## Disclosure" not in render.skill_md(bundle(scope="PRIVATE"))


def test_sensitivity_md_puts_the_missing_number_first():
    b = bundle()
    b["sensitivity"] = [
        {**b["sensitivity"][0], "id": "known", "known": True,
         "observed_value": "980", "decision_class": "already measured"},
        {**b["sensitivity"][0], "id": "unknown", "known": False},
    ]
    text = render.sensitivity_md(b)
    assert text.index("opening a store") < text.index("already measured")
    assert "a lookup, not advice" in text


def test_contradictions_md_keeps_the_unresolved_ones_flagged():
    text = render.contradictions_md(bundle())
    assert "Unresolved" in text and "dig sites" in text
    assert "would delete it" in text


def test_every_rendered_claim_carries_its_source():
    text = render.refusals_md(bundle())
    assert "[s1]" in text


def test_holdout_report_separates_the_two_pools():
    text = render.holdout_report_md(bundle())
    assert "Consensus pool (reported, not gated)" in text
    assert "Gated alignment" in text
    assert "| decompose | generic |" in text


def test_sources_json_carries_the_fingerprint():
    b = bundle(corpus_fingerprint="abc123")
    assert json.loads(render.sources_json(b))["corpus_fingerprint"] == "abc123"


def test_no_subject_slug_is_refused():
    try:
        package.slug({"subject": {}})
    except ValueError:
        return
    raise AssertionError("a bundle with no slug produced a filename")


# ── the output path is a path somebody else chose ──────

def test_a_slug_that_climbs_out_of_the_output_directory_is_refused():
    """`subject.slug` becomes a directory inside the zip and part of the
    filename beside it, so it is a path, and it arrives in the bundle.

    Before this check it passed straight through. Verified at the time by
    calling write_zip with `../../escaped-method` and watching the file appear
    two levels above the directory the caller asked for.
    """
    for bad in ("../../escaped", "..", "....//x", "/etc/passwd", "a/b",
                "a\\b", "C:/tmp/x", ".", "-leading", "x" * 70):
        try:
            package.slug({"subject": {"slug": bad}})
        except ValueError:
            continue
        raise AssertionError(f"slug {bad!r} was accepted")


def test_an_ordinary_slug_still_works():
    """The other direction, so the check above is not passing by refusing
    everything."""
    for good in ("practitioner", "a-practitioner_2", "x.y", "A1"):
        assert package.slug({"subject": {"slug": good}}) == good


def test_a_zip_entry_that_escapes_its_own_directory_is_refused():
    """Checked at the archive level too, and not because the slug check might
    fail.

    The two guard different mistakes. The slug check guards the value the
    bundle supplies; this one guards whatever a future caller assembles. And
    this is the one that matters to the person UNPACKING the archive rather
    than the one building it.
    """
    for bad in ("../escaped/SKILL.md", "/abs/SKILL.md", "a\\b/SKILL.md",
                "C:/x/SKILL.md"):
        assert package._path_errors([bad]), f"{bad!r} was accepted"
    assert not package._path_errors(["good-method/SKILL.md"])


def test_the_zip_lands_inside_the_directory_that_was_asked_for():
    """End to end, because the two checks above are about strings and the
    thing that matters is where the file goes."""
    out_dir = Path(tempfile.mkdtemp()) / "out"
    path, verdicts, errors = package.run(bundle(), corpus_dir(), out_dir)
    assert path is not None, errors
    assert path.resolve().parent == out_dir.resolve(), path


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
