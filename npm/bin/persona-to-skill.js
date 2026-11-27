#!/usr/bin/env node
// A pointer, not a port.
//
// This package exists so that `persona-to-skill` on npm resolves to the real
// project instead of to nothing. The tool itself is Python.
//
// The install command below is the one that works TODAY. The project is not
// on PyPI yet, and printing `pip install persona-to-skill` before it is
// published would send every user to a command that fails, or worse, to
// whatever unrelated package claims that name first. Change this line when
// the PyPI release exists, and change npm/README.md with it: a test keeps
// the two in step.
const pkg = require("../package.json");

const INSTALL = "pip install git+https://github.com/Joanna8521/persona-to-skill";

process.stdout.write(
  `persona-to-skill ${pkg.version} (npm pointer package)\n` +
  `\n` +
  `This is a Python tool. Nothing was installed by running this.\n` +
  `\n` +
  `  ${INSTALL}\n` +
  `  persona-to-skill --help\n` +
  `\n` +
  `Documentation  ${pkg.homepage}\n` +
  `Source         https://github.com/Joanna8521/persona-to-skill\n`
);

// Not process.exit(1). Node's own documentation says process.exit() forces
// termination with stdout writes still pending and can truncate the output,
// and printing that text is the only thing this package does. Setting the
// code lets the process end on its own once stdout has drained.
process.exitCode = 1;
