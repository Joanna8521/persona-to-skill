# -*- coding: utf-8 -*-
"""Make the package importable whether run under pytest or directly."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_module(namespace):
    """Run every test_* callable in `namespace` when executed as a script."""
    failures = []
    tests = sorted(k for k, v in namespace.items() if k.startswith("test_") and callable(v))
    for name in tests:
        try:
            namespace[name]()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures.append((name, exc))
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0
