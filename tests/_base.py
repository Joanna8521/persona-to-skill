# -*- coding: utf-8 -*-
"""Make the package importable whether run under pytest or directly."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Skipped(Exception):
    """A test declining to run, without needing pytest to say so.

    `pytest.skip` was used directly, and the branch that called it imported
    pytest to do so. In a virtualenv with neither pytest nor mkdocs the
    import raised ModuleNotFoundError, the runner reported an error and the
    script exited 1 for a test that had chosen not to run. The standalone
    mode exists precisely so a contributor without the dev extras can run
    these files.
    """


def skip(reason):
    """Decline to run, under pytest or as a plain script."""
    try:
        import pytest  # noqa: PLC0415
    except ImportError:
        raise Skipped(reason) from None
    pytest.skip(reason)


def run_module(namespace):
    """Run every test_* callable in `namespace` when executed as a script.

    Forces UTF-8 first. Several tests here are named in Chinese, and printing
    those names on a Windows console raised UnicodeEncodeError, which failed
    the run for a reason that had nothing to do with any test.
    """
    from persona_to_skill._console import force_utf8
    force_utf8()

    # pytest.skip raises Skipped, which derives from BaseException, not
    # Exception. Without this the script run of a file containing one skip
    # dies on the traceback and the job fails for a test that chose not to
    # run. It cost a red CI to find, because the skip in question sat after
    # the __main__ block and the script run never reached it.
    skip_types: tuple = (Skipped,)
    try:
        from _pytest.outcomes import Skipped as PytestSkipped  # noqa: PLC0415
        skip_types = (Skipped, PytestSkipped)
    except Exception:  # noqa: BLE001  - pytest is optional for a script run
        pass

    failures, skipped = [], []
    tests = sorted(k for k, v in namespace.items() if k.startswith("test_") and callable(v))
    for name in tests:
        try:
            namespace[name]()
            print(f"  PASS  {name}")
        except skip_types as exc:  # noqa: PERF203
            skipped.append((name, exc))
            print(f"  SKIP  {name}: {exc}")
        except AssertionError as exc:
            failures.append((name, exc))
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    tail = f", {len(skipped)} skipped" if skipped else ""
    print(f"\n{len(tests) - len(failures) - len(skipped)}/{len(tests)} passed{tail}")
    return 1 if failures else 0
