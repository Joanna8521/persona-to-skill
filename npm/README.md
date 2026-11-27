# persona-to-skill (npm pointer package)

**This is not the tool.** `persona-to-skill` is written in Python:

```bash
pip install git+https://github.com/Joanna8521/persona-to-skill
```

That is the command that works today. The project is not on PyPI yet, and
printing `pip install persona-to-skill` before it is published would send
every reader to a command that fails, or to whatever unrelated package claims
the name first.

This package exists so the name on npm resolves to the real project rather
than to nothing. It installs one command that prints the line above and sets
a non-zero exit code, because nothing was installed and a command that does
nothing should not report success.

A JavaScript wrapper that shelled out to `pip` was the alternative. It would
be a second install path to keep working, with its own failure modes, for no
gain over saying where the tool is.

- Documentation: https://joanna8521.github.io/persona-to-skill/
- Source: https://github.com/Joanna8521/persona-to-skill
