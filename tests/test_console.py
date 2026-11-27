# -*- coding: utf-8 -*-
"""A legacy console encoding must never decide an exit code.

Three times in this project, and once in the house-rules package it borrows
from, a run failed because something printed a character the console could not
encode. Each time the symptom was the same and the diagnosis was wrong at
first: the process exits non-zero either way, so a clean run and a genuinely
broken one look identical.

  * the punctuation gate quotes the offending line, and the lines it is most
    needed for are in Chinese;
  * the standalone test runner prints test names, and several here are named in
    Chinese;
  * the canonical validate_punct.py printed a tick, and that reached 34
    packages before anyone noticed.

cp1252 is used below because it is what the Windows runner handed us, and it
cannot encode any of this.
"""
import io
import sys

import _base  # noqa: F401
from persona_to_skill._console import force_utf8


def _legacy_streams(encoding="cp1252"):
    return (io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict"),
            io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict"))


def test_a_legacy_stream_raises_without_the_fix():
    """The test only means something if the failure is real."""
    out, _ = _legacy_streams()
    try:
        out.write("停滯超過六十天就放手")
        out.flush()
    except UnicodeEncodeError:
        return
    raise AssertionError("cp1252 accepted Chinese; this test proves nothing")


def test_force_utf8_makes_a_legacy_stream_take_chinese():
    out, err = _legacy_streams()
    force_utf8(out, err)
    out.write("停滯超過六十天就放手。")
    err.write("⚠️ 警告")
    out.flush()
    err.flush()


def test_force_utf8_leaves_an_unreconfigurable_stream_alone():
    """Guarded rather than raising: a closed or wrapped stream is not a reason
    to fail a run."""
    class NoReconfigure:
        def reconfigure(self, **kw):
            raise OSError("not a real stream")

    force_utf8(NoReconfigure())          # must not raise

    class NoMethod:
        pass

    force_utf8(NoMethod())


def test_the_standalone_runner_survives_a_chinese_test_name():
    """This is what broke on windows-latest: the runner prints each test's
    name, and several of this project's tests are named in Chinese."""
    def test_停滯超過六十天就放手():
        pass

    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _legacy_streams()
    try:
        code = _base.run_module({"test_停滯超過六十天就放手": test_停滯超過六十天就放手})
    finally:
        sys.stdout, sys.stderr = saved
    assert code == 0, "a passing test with a Chinese name must still exit 0"


def test_the_runner_still_reports_a_failure_under_a_legacy_console():
    """The dangerous half: the fix must not make everything pass."""
    def test_會失敗的():
        raise AssertionError("故意失敗")

    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _legacy_streams()
    try:
        code = _base.run_module({"test_會失敗的": test_會失敗的})
    finally:
        sys.stdout, sys.stderr = saved
    assert code == 1, "a failing test must still exit 1"


def test_every_entry_point_that_prints_forces_utf8():
    """Anything that can print non-ASCII and set an exit code has to call it.

    This used to be a hardcoded list of two files, and its own docstring said
    keeping the list here was cheaper than finding the fourth instance on a
    Windows runner. The fourth instance then happened on a Windows runner,
    because tools/build_docs.py was written after the list and nothing added
    it: the script printed ✅, cp1252 could not encode it, the process exited
    non-zero, and the test that ran it reported "docs/ is out of date" when
    the pages were perfectly current.

    A guard that is a fixed list is a guard that stops being true the moment
    someone adds a file. So this one discovers its own subjects: any module
    with a __main__ block that contains a non-ASCII string literal can print
    one, and must force UTF-8 first.
    """
    import ast as _ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    files = []
    for folder in ("persona_to_skill", "tools", "tests"):
        files += [f for f in sorted((root / folder).rglob("*.py"))
                  if "__pycache__" not in f.parts]

    missing = []
    for f in files:
        src = f.read_text(encoding="utf-8")
        if '__name__ == "__main__"' not in src and "__name__ == '__main__'" not in src:
            continue
        # Does it have a non-ASCII string literal anywhere? That is what a
        # legacy console cannot encode.
        tree = _ast.parse(src)
        risky = any(
            isinstance(n, _ast.Constant) and isinstance(n.value, str)
            and not n.value.isascii()
            for n in _ast.walk(tree)
        )
        if not risky:
            continue
        # `_base` calls it for every test file that runs through run_module.
        if "force_utf8" in src or "_base.run_module" in src:
            continue
        missing.append(str(f.relative_to(root)))

    assert not missing, (
        f"these can print non-ASCII and set an exit code, and do not force "
        f"UTF-8: {missing}. On a Windows console the print raises, the process "
        f"exits non-zero, and a clean run becomes indistinguishable from a "
        f"broken one."
    )


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
