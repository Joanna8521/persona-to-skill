# -*- coding: utf-8 -*-
"""Every declared entry point must exist.

`pyproject.toml` declared a console script for eleven commits:

    [project.scripts]
    persona-to-skill = "persona_to_skill.cli:main"

`persona_to_skill/cli.py` did not exist. `pip install .` succeeded, `pip show`
reported the package as installed, and then:

    $ persona-to-skill --help
    ModuleNotFoundError: No module named 'persona_to_skill.cli'

321 tests and eleven CI checks were green throughout, because not one of them
ran the installed command. The tests import the package; the entry point is
resolved by the generated console script, which only exists after an install.

This is the fourth shape of a gate that is not one, and the purest form of it:
not wrong, not stale, not untested, but DECLARED AND ABSENT. The other three at
least have something to inspect. This one reads as a feature in the packaging
metadata and resolves to nothing at all.

So this file resolves every declared entry point the way the console script
does, and checks the target is there and callable.
"""
import importlib
import re
from pathlib import Path

import _base  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _scripts():
    """Parse [project.scripts] without a TOML dependency.

    tomllib would be cleaner, but this file has to run on 3.10, which is what
    requires-python declares, and tomllib landed in 3.11. Reading the metadata
    with a parser the declared floor does not have would be its own small
    version of the bug this file exists for.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)",
                      text, re.M | re.S)
    if not block:
        return []
    out = []
    for line in block.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, target = (p.strip() for p in line.partition("="))
        out.append((name, target.strip().strip('"').strip("'")))
    return out


def test_pyproject_declares_at_least_one_script():
    """A guard with nothing to guard passes forever.

    Without this, deleting [project.scripts] would make every check below
    vacuous and the file would stay green while guarding nothing.
    """
    assert _scripts(), "[project.scripts] is empty or unparsed"


def test_every_declared_entry_point_resolves():
    """Loops rather than parametrizes, so this file runs as a script too.

    Every other test file here runs both under pytest and via
    _base.run_module, because pytest is an optional dependency.
    """
    for name, target in _scripts():
        _check_one(name, target)


def _check_one(name, target):
    module_path, sep, attr = target.partition(":")
    assert sep and attr, f"{name} = {target!r} is not module:attribute"

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise AssertionError(
            f"{name} points at {target!r} but {module_path} does not import: "
            f"{exc}. `pip install .` would succeed and the command would fail "
            f"at the first run."
        ) from exc

    obj = getattr(module, attr, None)
    assert obj is not None, (
        f"{name} points at {target!r} but {module_path} has no {attr!r}"
    )
    assert callable(obj), f"{name} resolves to {obj!r}, which is not callable"


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
