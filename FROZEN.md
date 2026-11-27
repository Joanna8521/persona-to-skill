# Frozen contracts

Values in `persona_to_skill/contract.py` are frozen. Changing one changes what
the tool is allowed to produce, so a change needs a new version and an entry
here, never an in-place edit. `tests/test_contract_frozen.py` asserts them.

## v0.1.0 (unreleased)

Frozen in `contract.py`:

| Contract | Value |
|---|---|
| `OUTPUT_SCOPES` | `("PRIVATE", "PUBLISHED")` |
| `SCOPE_DEPENDENT_GATES` | `("G3-disclosure",)` |
| `SOURCE_TIERS` | `T0` private w/ consent, `T1` public citable, `T2` public copyrighted, `T3` prohibited |
| `TIERS_ALWAYS_FORBIDDEN` | `("T3",)` |
| `TIERS_REQUIRING_CONSENT` | `("T0",)` |
| `CONSENT_REQUIRED_FIELDS` | subject_name, granted_to, scope, signed_date, revocable |
| `HOLDOUT_MIN_ALIGNMENT` | `0.80` |
| `HOLDOUT_MAX_UNKNOWN_RATIO` | `0.30` |
| `HOLDOUT_MIN_ITEMS` | `10` |
| `DISCLOSURE_REQUIRED_KEYS` | reconstruction_notice, not_endorsed, source_count, holdout_alignment, retrieved_date |
| `IMPERSONATION_PATTERNS` | 11 forms, English and Chinese |

Gates: `G1-consent`, `G2-anchor`, `G3-disclosure`, `G4-holdout`.
62 tests, every gate with negative cases that must go red.

### Design note: one axis, not two

An earlier draft had `MODES = ("SELF", "PUBLIC")`, collapsing two orthogonal
questions into one switch:

* **whose material is this** -- already answered per-source by the tier system,
  so a mode for it was redundant;
* **where does the output go** -- the only question that needs a mode.

The collapse left the most common real use with nowhere to sit: *build an
advisor from a public figure's public material, for your own private use*. It
is lawful (US publicity rights and Taiwan's Fair Trade Act both turn on
commercial use) and it is most of what this tool will be used for.

So scope is the axis, and the gates divide by what they are actually for:

| Gate | About | Scope-dependent |
|---|---|---|
| G1 source tiers | lawfulness of the material | no |
| G2 source anchors | quality -- protects the **builder** | no |
| G4 holdout | quality -- protects the **builder** | no |
| G3 disclosure | informing a third party | **yes** |

G2 and G4 run on private builds too, and matter more there: an advisor that
invents "he said X" will have you acting on a rule nobody holds, and in private
use no reviewer catches it for you.

Impersonation blocks when PUBLISHED and warns when PRIVATE, and the private
warning is about effectiveness, not law: `you are X` steers a model toward
voice, which it imitates well, and away from judgement, which it does not.

### Punctuation gate scope

House rule: Chinese text uses full-width punctuation. English does not, and the
English README is canonical, so the gate runs only against
`PUNCT_CHECKED_SUFFIXES` and `PUNCT_CHECKED_DIRS`.
