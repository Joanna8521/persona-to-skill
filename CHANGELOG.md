# Changelog

All notable changes to this project are documented here. Contract changes also
appear in `FROZEN.md` with the reasoning.

## [Unreleased]

### Added
- Frozen contract (`persona_to_skill/contract.py`): source tiers T0–T3, output
  scopes, consent record shape, holdout thresholds, impersonation forms in
  English and Chinese, declared capability limits.
- Four gates: `G1-consent`, `G2-anchor`, `G3-disclosure`, `G4-holdout`.
- `tests/test_gates_have_teeth.py`: every gate must reject a deliberately
  broken input, and a clean input must still pass.
- CI across Python 3.9–3.13 on Linux, plus macOS and Windows runs, because the
  gates compare quoted text against files on disk.
- `gates-intact.yml`: a separate workflow proving the gates still bite.
- CodeQL, Dependabot for actions.

### Changed
- Holdout is scored in two pools against a recorded baseline. A single
  alignment figure over all questions was gameable: five of ten on the
  questions that matter, padded with forty consensus answers, read as 90%.
  `HOLDOUT_MIN_ALIGNMENT` stays 0.80 but now measures the divergent pool only.
- Output scope (`PRIVATE` / `PUBLISHED`) replaced an earlier `SELF` / `PUBLIC`
  mode, which collapsed two orthogonal questions and left the most common real
  use with nowhere to sit.
