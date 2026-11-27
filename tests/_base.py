# -*- coding: utf-8 -*-
"""Make the package importable whether run under pytest or directly."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    try:
        from _pytest.outcomes import Skipped  # noqa: PLC0415
        skip_types: tuple = (Skipped,)
    except Exception:  # noqa: BLE001  - pytest is optional for a script run
        skip_types = ()

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
