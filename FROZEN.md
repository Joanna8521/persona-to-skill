# Frozen contracts

Values in `persona_to_skill/contract.py` are frozen. Changing one changes what
the tool is allowed to produce, so a change needs a new version and an entry
here, never an in-place edit. `tests/test_contract_frozen.py` asserts them.

## v0.1.0 (unreleased)

### Amendment: three corrections to G5, before it ever shipped

**`conflicts` is no longer emptiable.** It was listed alongside `evidence_gaps`
without being thought about. The two are not alike: "no evidence gaps" can be
true, but the seats that produce a memo are set against each other on purpose,
so a run that surfaces no conflict has not found agreement, it has found that a
seat did not hold its position. Where opposed positions genuinely converge,
saying why is content, so the field is non-empty either way. Conflict is also
where the value is: it marks the spot where two models of the world differ,
which is the thing worth digging into.

**Confidence now conflicts only with a gap that bears on the decision.** The
first version forbade any open gap above `CONFIDENCE_REQUIRING_NO_GAPS`, which
was wrong twice. It blocked a reasonable memo, high confidence with a minor
gap noted, and the cheapest way to satisfy it was to delete the gap, so the
rule paid people to do the one thing the schema exists to prevent. The
combination is now explicit rather than forbidden: a gap is either marked
`{"bears_on_decision": false}` or it counts against the confidence. An unmarked
gap counts as bearing, so marking is the cheap path and deleting still hits the
opposite rule. Added `GAP_PERIPHERAL_KEY`.

**The evasion word list is a floor, not a gate.** It is lexical, so it is
gameable, since the list is public and "整體來看需要權衡各方面因素" is the same
dodge in words it does not hold, and it trips on mention as well as use
("不能用綜合評估帶過" is a correct sentence). It now blocks only where a field's whole
content is the phrase, and warns otherwise, saying in the warning that it
cannot tell a dodge from a mention.

A structural replacement was considered and rejected rather than invented: no
reliable test separates a dodge from a specific statement, because "the unit
economics never reach breakeven" has neither a condition nor a number and is
not evasive at all. One structural check was added where it *is* sound:
`THRESHOLD_NUMBER` requires a flip-condition threshold to contain a number,
since a threshold is the value a quantity is compared against and without one
there is nothing to go and find out.

`CONDITIONAL_MARKERS` was removed. R2 no longer uses it, and an unused frozen
value is false furniture: it suggests a check that is not running.

### Amendment: holdout is scored in two pools

`HOLDOUT_MIN_ALIGNMENT` is unchanged at `0.80`, but **what it is measured over
has changed**, so the number means something different and the entry is
recorded here rather than edited in place.

Added: `HOLDOUT_MIN_DIVERGENT_ITEMS = 5`.

A single alignment figure over all holdout questions measures almost nothing,
because most of what any practitioner says out loud is consensus. A
reconstruction answers those questions correctly whether or not it learned
anything, so a question set drawn from them issues a flattering grade to an
empty shell. Worse, it is trivially gamed: 5 of 10 on questions that matter,
padded with 40 consensus answers, reads as 90% under a single pool.

Each item now carries a recorded **baseline**: the same question answered with
no reconstruction loaded at all.

| Pool | Baseline | Gated |
|---|---|---|
| consensus | already matches the subject | no, the default gets these right too |
| divergent | wrong | **yes**, only judgement that carried across can be right |

So `0.80` now means *alignment where the default answer would have failed*,
which is the lift over baseline measured directly rather than subtracted.
`stats["gated_alignment"]` is named so a report cannot quietly print the
consensus-inflated figure in its place.

Missing baselines **fail closed**: without them the pools cannot be told apart,
and falling back to a raw figure over all items is the exact measurement this
gate exists to refuse.

The honest consequence, stated by the gate rather than hidden: a subject whose
public positions are all consensus cannot be meaningfully reconstructed. That
is a finding, not a fixable question set.

Tests: 68, with the consensus-padding attack as an explicit negative case.

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

* **whose material is this**, already answered per-source by the tier system,
  so a mode for it was redundant;
* **where does the output go**, the only question that needs a mode.

The collapse left the most common real use with nowhere to sit: *build an
advisor from a public figure's public material, for your own private use*. It
is lawful (US publicity rights and Taiwan's Fair Trade Act both turn on
commercial use) and it is most of what this tool will be used for.

So scope is the axis, and the gates divide by what they are actually for:

| Gate | About | Scope-dependent |
|---|---|---|
| G1 source tiers | lawfulness of the material | no |
| G2 source anchors | quality, protects the **builder** | no |
| G4 holdout | quality, protects the **builder** | no |
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
