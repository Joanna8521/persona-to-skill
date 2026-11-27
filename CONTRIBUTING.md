# Contributing

## The rule that matters most

**A gate must be able to fail.** Any check added or changed here is reviewed
against three questions, and a no to any one of them sends it back:

1. **Does it recompute independently?** A check that confirms a value using the
   method that produced it always passes. Reconciling a quote means reopening
   the source file and searching it, not consulting the index the extraction
   wrote.
2. **Does it fail closed?** When an input a check depends on is absent, the
   check must block. The quiet `return passed=True` on a missing optional input
   disables a gate without removing it, which is the hardest failure to notice.
3. **Does it read the artifact being delivered?** Not a fixture, not a template,
   not the previous run.

Then the test: **feed it something deliberately broken and watch it go red.** A
check with no negative test is unverified, and `gates-intact.yml` enforces a
floor of four negative assertions per gate.

## Frozen values

Everything in `persona_to_skill/contract.py` is a frozen contract. Changing one
changes what the tool may produce, so it needs a version bump and an entry in
`FROZEN.md` explaining what changed and why — never an in-place edit.

If a threshold's *meaning* changes while its number stays the same, that still
needs an entry. `HOLDOUT_MIN_ALIGNMENT` stayed at 0.80 when it began measuring
the divergent pool only; `FROZEN.md` records it, because the same number now
makes a different claim.

## Tests

```bash
python -m pytest -q          # all of them
python tests/test_gate_holdout.py   # one file, no pytest needed
```

Every test file must work both ways. A contributor checking one gate should not
have to install anything, so each file ends with a `__main__` block.

## Scope

Pull requests that add voice synthesis, image or avatar generation, or
first-person impersonation of a subject will be closed. These are refused by
design, not yet unimplemented; see `OUT_OF_SCOPE_OUTPUTS` in `contract.py`.

A pull request that removes a gate, lowers a frozen threshold, or makes a
required disclosure optional needs to argue the case in the issue first.

## Before opening a pull request

- `python -m pytest -q` passes
- `python -m ruff check persona_to_skill tests` is clean
- new or changed checks have negative tests
- `FROZEN.md` has an entry if any contract value or its meaning moved
- every file path is ASCII (CI checks this; some skill installers reject an
  archive outright over a non-ASCII path)
