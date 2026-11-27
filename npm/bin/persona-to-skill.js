#!/usr/bin/env node
// A pointer, not a port.
//
// This package exists so that `persona-to-skill` on npm resolves to the real
// project instead of to nothing. The tool itself is Python, and shipping a
// JavaScript wrapper that shelled out to pip would be a second install path
// to keep working, with its own failure modes, for no gain over saying where
// the tool is.
//
// It exits non-zero on purpose: nothing was installed and nothing ran, and a
// command that does nothing should not report success.
const pkg = require("../package.json");

process.stdout.write(
  `persona-to-skill ${pkg.version} (npm pointer package)\n` +
  `\n` +
  `This is a Python tool. Nothing was installed by running this.\n` +
  `\n` +
  `  pip install persona-to-skill\n` +
  `  persona-to-skill --help\n` +
  `\n` +
  `Documentation  ${pkg.homepage}\n` +
  `Source         https://github.com/Joanna8521/persona-to-skill\n`
);
process.exit(1);
