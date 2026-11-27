# -*- coding: utf-8 -*-
"""The npm pointer package, checked from Python so CI needs no Node.

`npm/` holds the name on npm and points at the real tool. It is three small
files that nothing else in this repository imports, which is exactly the
shape of thing that rots: a `bin` entry pointing at a file someone renamed
installs fine and fails the first time anyone runs it, and a version left
behind says the wrong thing on a page people read before installing.
"""
import json
import sys
from pathlib import Path

import _base  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
NPM = ROOT / "npm"


def _manifest():
    return json.loads((NPM / "package.json").read_text(encoding="utf-8"))


def test_every_bin_target_exists_and_is_executable():
    """An npm `bin` pointing at a missing file installs without complaint."""
    manifest = _manifest()
    missing = []
    for command, rel in manifest["bin"].items():
        target = NPM / rel
        if not target.is_file():
            missing.append(f"{command} -> {rel} (no such file)")
        elif not target.read_text(encoding="utf-8").startswith("#!"):
            missing.append(f"{command} -> {rel} (no shebang; npm will not run it)")
    assert not missing, missing


def test_the_published_file_list_covers_the_bin_directory():
    """`files` is an allowlist. A bin left out of it is absent from the
    tarball while present in the working tree, so it works locally and 404s
    for everyone else."""
    manifest = _manifest()
    allowed = manifest["files"]
    for rel in manifest["bin"].values():
        top = Path(rel).parts[0]
        assert top in allowed, f"{rel} is not covered by files: {allowed}"


def test_the_npm_version_matches_the_python_package():
    """The pointer tells people which version to expect. Two version numbers
    in one repository drift unless something compares them."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in pyproject.splitlines():
        if line.startswith("version = "):
            python_version = line.split("=", 1)[1].strip().strip('"')
            break
    else:
        raise AssertionError("pyproject.toml has no version")

    assert _manifest()["version"] == python_version, (
        f"npm says {_manifest()['version']}, pyproject says {python_version}")


def test_the_pointer_does_not_claim_to_be_the_tool():
    """It exits non-zero and says nothing was installed. A pointer that
    printed a banner and exited 0 would look like a working install."""
    source = (NPM / "bin" / "persona-to-skill.js").read_text(encoding="utf-8")
    assert "process.exit(1)" in source
    assert "pip install persona-to-skill" in source

    readme = (NPM / "README.md").read_text(encoding="utf-8")
    assert "This is not the tool" in readme


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
