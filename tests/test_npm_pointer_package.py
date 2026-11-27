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


def _executable_js(name="bin/persona-to-skill.js"):
    """The bin with its `//` comments removed.

    Scanning the raw text made the first version of
    test_the_bin_does_not_truncate_its_own_output fail on the comment that
    EXPLAINS why process.exit() is avoided. A guard its own prose can trip is
    as useless as one its own prose can satisfy; this repository has now hit
    both directions of that.

    Whole-line comments only. Cutting at the first `//` anywhere also cut
    `https://github.com/...` out of the install command, and the next test
    then reported that the bin had no INSTALL constant at all. Stripping
    comments from source with string handling is a parser's job, and this
    file does not need one: every comment in the bin is a whole line.
    """
    kept = []
    for line in (NPM / name).read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("//"):
            kept.append(line)
    return "\n".join(kept)


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
    source = _executable_js()
    assert "process.exitCode = 1" in source
    assert "pip install" in source

    readme = (NPM / "README.md").read_text(encoding="utf-8")
    assert "This is not the tool" in readme


def test_the_license_ships_with_the_package():
    """`files` is an allowlist and the root LICENSE is outside the package
    root, so a declared licence does not reach anyone unless a copy sits in
    npm/ and is listed. `npm pack --dry-run` had three files in it while the
    manifest said Apache-2.0."""
    manifest = _manifest()
    assert "LICENSE" in manifest["files"], manifest["files"]
    shipped = NPM / "LICENSE"
    assert shipped.is_file(), "npm/LICENSE does not exist"
    assert shipped.read_bytes() == (ROOT / "LICENSE").read_bytes(), (
        "npm/LICENSE has drifted from the repository's LICENSE")


def test_the_bin_does_not_truncate_its_own_output():
    """Node's documentation says process.exit() forces termination with
    stdout writes still pending, which can truncate them. Printing the
    install line is the only thing this package does, so losing it to a
    truncated pipe would leave the package doing nothing at all."""
    source = _executable_js()
    assert "process.exitCode" in source
    assert "process.exit(" not in source, (
        "use process.exitCode; process.exit() can truncate pending stdout")


def test_the_install_command_is_one_that_exists():
    """The bin and the README print an install command, and they must print
    the SAME one.

    `pip install persona-to-skill` is not it: the project is not on PyPI, so
    that command fails for everyone and would silently start installing an
    unrelated package if someone else claims the name. When the PyPI release
    exists, both files change together or this fails.
    """
    import re as _re  # noqa: PLC0415

    source = _executable_js()
    match = _re.search(r'const INSTALL = "([^"]+)"', source)
    assert match, "the bin has no INSTALL constant to check"
    command = match.group(1)

    readme = (NPM / "README.md").read_text(encoding="utf-8")
    assert command in readme, (
        f"the bin prints {command!r} and the README does not mention it")

    assert command != "pip install persona-to-skill", (
        "that command does not work until the project is published to PyPI")


if __name__ == "__main__":
    sys.exit(_base.run_module(dict(globals())))
