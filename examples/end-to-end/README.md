# The whole pipeline, on an invented subject

Three commands, from raw records to an installable skill. Every figure below
came from running it; the last section says what the run actually printed.

**A. Example does not exist.** The two sources in `records.json` were written
for this example. That matters more here than in most sample data: this tool
reconstructs a real practitioner's method from their own published words, and
a worked example that read like a real person's words would be the exact
thing the gates exist to prevent.

## Run it

```bash
persona-to-skill import examples/end-to-end/records.json \
  --subject "A. Example" --tier T1 --corpus /tmp/corpus
```

```bash
persona-to-skill gates --corpus /tmp/corpus examples/end-to-end/bundle.json
```

```bash
persona-to-skill package --corpus /tmp/corpus --out /tmp/out \
  examples/end-to-end/bundle.json
```

## What each stage does

**`import`** reads the records, sanitises them, and writes one `.txt` per
source into the corpus directory plus a `manifest.json`. The corpus is what
`G2-anchor` later reads quotes against, so this is the step that decides what
counts as evidence. It accepted 2 and rejected 0.

**`gates`** renders the deliverable, then runs all nine gates against it. It
exits non-zero if any gate fails, which is the shape CI wants. Nothing is
written.

**`package`** runs the same gates and only then writes the archive. A failing
gate means there is no zip, not a zip with a warning in it.

## The archive

```
a-example-method/SKILL.md
a-example-method/contradictions.md
a-example-method/decision-table.md
a-example-method/holdout-report.md
a-example-method/refusals.md
a-example-method/sensitivity.md
a-example-method/sources.json
```

The test compares this list with the archive in both directions. Checking
only that every archived file appears here would leave a renamed or deleted
file as a stale line nobody notices. Sizes are deliberately not listed: they
change on every edit to the bundle, so pinning them would make the test fail
for reasons that are not defects.

## What the gates said, including the warnings

All nine passed, and four of them passed while saying something a reader
should know. The warnings are the interesting part:

| gate | what it said |
|---|---|
| `B-contradictions` | 1 of 1 unresolved and flagged for digging; at this rate that is the intended outcome, not a failure |
| `B-profile` | only the `oppose` seat is claimable, which is a normal result worth stating plainly |
| `G4-holdout` | the consensus pool was 86% over 7 items, reported but not gated: a model with no reconstruction also answers those |
| `G2-anchor` | 1 claim is marked `inference` and exempt from the quote check, "and `G3` verifies that the output labels them" |

That last row quotes `G2-anchor` verbatim, and the quoted clause is not true
today. `G3` does not check each inference claim's label: it warns when the
word `inference` occurs anywhere in the rendered skill, and says nothing at
all when it is absent, so an unlabelled inference passes silently. The claim
appears in `anchor.py` as well as in the gate's output. Both are being fixed
separately; this example states what the tool does now rather than what its
own warning says it does.

The bundle has 12 holdout items, 5 of them divergent from a no-reconstruction
baseline, and one deliberate miss. A set where the reconstruction agrees with
the subject on everything is a set that never asked a hard question.

## Writing this example found a real bug in the example

The first `bundle.json` listed `support` in `entry_order` and left
`interrogate` out of both `entry_order` and
`unfilled_seats_acknowledged`. `B-seats` failed with all three problems named
separately:

```
seat(s) ['support', 'crosscheck', 'synthesise', 'interrogate'] have nothing
  in them and the bundle does not say so
entry_order is [...'support'], expected [...'interrogate']
the support seat is in entry_order. It is reachable on request and never
  volunteered
```

That is the gate doing its job on its own example, which is worth more as a
demonstration than a bundle that passed on the first try. The fix was to read
`SEAT_ENTRY_ORDER` and `SEATS` out of `contract.py` rather than retype them,
and `tests/test_end_to_end_example.py` now builds `entry_order` from the
contract so this example cannot drift from it again.
