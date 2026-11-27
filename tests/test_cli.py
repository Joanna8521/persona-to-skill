# -*- coding: utf-8 -*-
"""The CLI, invoked rather than imported.

tests/test_entry_points.py resolves the declared entry point, which catches the
module not existing at all. It does not catch anything inside it, and the first
version of cli.py proved that: it compared a verdict against `fetch.FETCH_OK`,
a constant that does not exist (they are `FETCH` and `IMPORT_ONLY`). Importing
cli.py succeeded, the guard went green, and every fetch invocation ended in an
AttributeError traceback.

Same class of bug, one level down. So this file calls `main(argv)` and asserts
on the exit code, because the exit code is the whole reason it is a command: a
gate that prints a verdict and exits 0 cannot be put in a CI job, which is the
same as not having one.
"""
import contextlib
import io
import json
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill import cli

# Every other test file in here runs both under pytest and as a script, via
# _base.run_module. That exists because pytest is an optional dependency and
# because a Windows console once failed a whole run on a test NAME. Using
# capsys and pytest.raises would have quietly made this one file pytest-only,
# so stdout is captured by hand and SystemExit is caught by hand.


def tmp_dir():
    return tempfile.mkdtemp()


def run(argv):
    """Call main(argv) and return (exit_code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


def exits_non_zero(argv):
    """Call main(argv) expecting SystemExit, and return its code."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            cli.main(argv)
    except SystemExit as exc:
        return exc.code
    raise AssertionError(f"{argv} did not raise SystemExit")

ALLOW = "User-agent: *\nAllow: /\n"
DENY = "User-agent: *\nDisallow: /\n"


# ── the shape of the command itself ─────────────────────

def test_no_subcommand_exits_non_zero():
    """A bare invocation must not exit 0 having done nothing.

    argparse raises SystemExit(2) for a missing required argument, which is the
    behaviour wanted; `required=True` on the subparsers is what produces it.
    Without that flag argparse exits 0 with no output, and a command that
    succeeds without doing anything is this file's whole subject.
    """
    assert exits_non_zero([]) != 0


def test_every_subcommand_is_reachable():
    """Each declared subcommand parses and binds a function.

    A subparser added without set_defaults(func=...) raises AttributeError at
    call time, not at parse time, so it stays invisible until someone runs it.
    """
    parser = cli.build_parser()
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    names = sorted(set().union(*(set(a.choices) for a in actions)))
    assert names == ["fetch", "gates", "import", "package", "punct"]


# ── fetch ───────────────────────────────────────────────

def test_fetch_allowed_exits_zero():
    robots = Path(tmp_dir()) / "robots.txt"
    robots.write_text(ALLOW, encoding="utf-8")
    code, out = run(["fetch", "https://example.com/post/1",
                     "--robots", str(robots)])
    assert code == 0, out
    assert "fetch" in out


def test_fetch_disallowed_exits_non_zero_and_names_the_routes():
    """Refused is exit 1, and it must say what to do instead.

    A refusal that only says no sends the user looking for a way around it. The
    import routes are the answer, so the refusal carries them.
    """
    robots = Path(tmp_dir()) / "robots.txt"
    robots.write_text(DENY, encoding="utf-8")
    code, out = run(["fetch", "https://example.com/post/1",
                     "--robots", str(robots)])
    assert code == 1, out
    assert "import_only" in out
    assert "Export your data" in out


def test_fetch_non_http_scheme_is_refused():
    code, out = run(["fetch", "ftp://example.com/x"])
    assert code == 1, out


def test_fetch_without_robots_is_permitted():
    """No robots.txt means the site has stated no restriction.

    Treating absence as refusal would be the safe-looking choice and the wrong
    one: it is not what any crawler does, and it would make the command useless
    for the ordinary case.
    """
    code, out = run(["fetch", "https://example.com/post/1"])
    assert code == 0, out


# ── import ──────────────────────────────────────────────

def _postsync_file(tmp, records):
    p = Path(tmp) / "export.json"
    p.write_text(json.dumps({
        "contract": "persona-to-skill/import/v1",
        "exported_by": "post-sync 1.6.0",
        "records": records,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_import_writes_a_corpus_and_a_manifest():
    tmp = tmp_dir()
    src = _postsync_file(tmp, [{
        "text": "Pricing is not cost plus a margin. It is what the buyer is "
                "comparing you against, and that is rarely your cost sheet.",
        "author": "A Practitioner",
        "author_guessed": False,
        "platform": "linkedin",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:1/",
        "retrieved_at": "2026-11-27T01:45:00.000Z",
        "published": "3 days",
        "embedded_other_party": "",
        "image_count": 0,
        "kind": "text",
    }])
    corpus = Path(tmp) / "corpus"
    code, out = run(["import", str(src), "--subject", "A Practitioner",
                     "--tier", "T2", "--corpus", str(corpus)])
    assert code == 0, out
    assert "accepted 1" in out
    assert (corpus / "manifest.json").exists()
    files = [p for p in corpus.iterdir() if p.name != "manifest.json"]
    assert len(files) == 1, [p.name for p in corpus.iterdir()]


def test_import_accepting_nothing_exits_non_zero_and_writes_nothing():
    """Zero accepted is a failure, not a quiet success.

    Exiting 0 here would let a pipeline carry on with an empty corpus, and the
    gates downstream would then report on nothing.
    """
    tmp = tmp_dir()
    src = _postsync_file(tmp, [{"text": "   ", "platform": "x", "url": ""}])
    corpus = Path(tmp) / "corpus"
    code, out = run(["import", str(src), "--subject", "Someone",
                     "--tier", "T2", "--corpus", str(corpus)])
    assert code == 1, out
    assert not corpus.exists() or not list(corpus.glob("*.txt"))


def test_import_rejects_an_unknown_tier():
    """argparse chokes on it, which is the right place: the tier is a closed
    set from the frozen contract, and a typo must not reach the importer."""
    assert exits_non_zero(["import", "x.json", "--subject", "S",
                           "--tier", "T9", "--corpus", "c"]) != 0


def test_import_of_a_plain_list_also_works():
    """Not everything that produces the contract shape wraps it in an object."""
    tmp = tmp_dir()
    src = Path(tmp) / "list.json"
    src.write_text(json.dumps([{
        "text": "A claim long enough to be a source on its own, stated plainly "
                "so that it can be anchored later.",
        "author": "A Practitioner",
        "platform": "blog",
        "url": "https://example.com/post/1",
    }], ensure_ascii=False), encoding="utf-8")
    corpus = Path(tmp) / "corpus"
    code, out = run(["import", str(src), "--subject", "A Practitioner",
                     "--tier", "T1", "--corpus", str(corpus)])
    assert code == 0, out


def test_import_of_something_that_is_not_records_is_refused():
    tmp = tmp_dir()
    src = Path(tmp) / "bad.json"
    src.write_text('{"hello": "world"}', encoding="utf-8")
    assert exits_non_zero(["import", str(src), "--subject", "S", "--tier", "T2",
                           "--corpus", str(Path(tmp) / "c")]) != 0


def test_a_missing_file_is_a_clean_error_not_a_traceback():
    assert "no such file" in str(
        exits_non_zero(["gates", "/nonexistent/bundle.json", "--corpus", "/tmp"]))


def test_invalid_json_is_a_clean_error_not_a_traceback():
    tmp = tmp_dir()
    bad = Path(tmp) / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert "not valid JSON" in str(
        exits_non_zero(["gates", str(bad), "--corpus", tmp]))


# ── gates ───────────────────────────────────────────────

def test_gates_on_an_empty_bundle_exits_non_zero():
    """Every gate fails closed on nothing, and the command says so.

    This is the single most important exit code in the file: an empty bundle is
    what a half-finished pipeline produces, and reporting it as a pass is how a
    reconstruction with no evidence behind it gets shipped.
    """
    tmp = tmp_dir()
    bundle = Path(tmp) / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")
    code, out = run(["gates", str(bundle), "--corpus", tmp])
    assert code == 1, out
    assert "FAIL" in out
    assert "gates passed" in out


def test_package_on_an_empty_bundle_writes_nothing():
    tmp = tmp_dir()
    bundle = Path(tmp) / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")
    out_dir = Path(tmp) / "out"
    code, out = run(["package", str(bundle), "--corpus", tmp,
                     "--out", str(out_dir)])
    assert code == 1, out
    assert "nothing was written" in out
    assert not list(out_dir.glob("*.zip"))


# ── punct ───────────────────────────────────────────────

def test_punct_passes_on_clean_markdown():
    tmp = tmp_dir()
    (Path(tmp) / "ok.md").write_text("# Title\n\nPlain English prose.\n",
                                     encoding="utf-8")
    code, out = run(["punct", tmp])
    assert code == 0, out


def test_punct_fails_on_a_violation():
    """The gate has to be reachable from the command, not only from its own
    module. A validator nothing can invoke is the first shape of a false gate.

    The filename matters: the Chinese typography rule applies only to files
    named by PUNCT_CHECKED_SUFFIXES or living under PUNCT_CHECKED_DIRS. The
    first version of this test wrote `bad.md`, which is out of scope, so the
    gate correctly found nothing and the test was the thing that was wrong.
    """
    tmp = tmp_dir()
    (Path(tmp) / "guide.zh-TW.md").write_text(
        "# 標題\n\n這一句用了半形逗號, 然後結束.\n", encoding="utf-8")
    code, out = run(["punct", tmp])
    assert code == 1, out
    assert "half-width punctuation after Chinese" in out


def test_punct_ignores_english_prose_outside_the_chinese_scope():
    """And the other way round: a .md that is not in scope must stay clean.

    Without this, widening the scope to every Markdown file would pass the test
    above while breaking every English document in the repo.
    """
    tmp = tmp_dir()
    (Path(tmp) / "notes.md").write_text(
        "# Title\n\nHalf-width commas, full stops. All correct here.\n",
        encoding="utf-8")
    code, out = run(["punct", tmp])
    assert code == 0, out
    assert "0 under the Chinese typography rule" in out, out


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
