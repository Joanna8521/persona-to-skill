## What this changes

## Checks

- [ ] `python -m pytest -q` passes
- [ ] `python -m ruff check persona_to_skill tests` is clean
- [ ] each test file still runs standalone (`python tests/test_*.py`)

## If this touches a gate or a check

- [ ] it recomputes independently, rather than confirming a value with the
      method that produced it
- [ ] it fails closed when an input it depends on is absent
- [ ] it reads the artifact being delivered, not a fixture
- [ ] a negative test feeds it something deliberately broken and it goes red

## If this touches `contract.py`

- [ ] `FROZEN.md` has an entry, including when a number stays the same but its
      meaning changes
