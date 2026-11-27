# The whole pipeline, on an invented subject

Four commands, from raw records to an installable skill. Every figure below
came from running them; the last sections say what the run actually printed.

**A. Example does not exist.** The five sources in `records.json`, the
twelve eval questions and both sides of every answer in `eval-run.json` were
all written for this example. That matters more here than in most sample data:
this tool reconstructs a real practitioner's method from their own published
words, and a worked example that read like a real person's words would be the
exact thing the gates are there to prevent.

## Run it

```bash
persona-to-skill import examples/end-to-end/records.json \
  --subject "A. Example" --tier T1 --corpus /tmp/corpus
```

```bash
persona-to-skill eval examples/end-to-end/eval-manifest.json \
  --run examples/end-to-end/eval-run.json \
  --corpus /tmp/corpus --subject "A. Example"
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
counts as evidence. It accepted 5 and rejected 0.

**`eval`** is where the holdout figure comes from. Twelve questions, each
with the subject's own answer and the source it is in, against a recorded run
that also captured what a model with **no** reconstruction said. Every one of
the twelve ground truths is anchored through `G2-anchor` before anything is
scored: a suite is not exempt from the gate just because it is the thing
doing the measuring.

An earlier version of this example skipped this step and wrote the holdout
observations into `bundle.json` by hand. The gates accepted them and the
archive published "Measured alignment ... 100% over 5 divergent items" from
booleans nobody had checked. That is the shape of defect this project exists
to catch, so the example now runs the harness. `bundle.json`'s `holdout` and
`holdout_by_seat` are the same twelve observations as `eval-run.json`.

The twelve questions are drawn from material the reconstruction does not
cite. That is not a detail: four of them originally had ground truths that
were, word for word, quotes the bundle was built from, two of those in the
divergent pool. A holdout item whose answer is in the bundle is not a
holdout item, and excluding the contaminated ones would have left three
divergent against G4's minimum of five. The harness cannot detect this. It
says so itself, in `anchor_manifest`: nothing in the files shows whether a
question was held back, and `seen_in_extraction` is the author's
declaration. A test in this repository checks it for this example; closing
it properly is the product's job.

Two things this run is not. The answers on both sides were written for the
example, so `judged_by` says so rather than naming a judging pass that never
happened. And setting `blind: false` on every item, which is what an
unjudged run honestly is, makes the harness refuse to score at all: *"not
measured: no divergent item carried a blind, judged observation"*. It
refuses correctly. `package`, reading the same twelve observations, still
produces an archive claiming 100%. Nothing reconciles the two commands, and
that gap is larger than any of the ones this example was written to show.

**`gates`** renders the deliverable, then runs all nine gates against it. It
exits non-zero if any gate fails, which is the shape CI wants. Nothing is
written.

**`package`** runs the same gates and only then writes the archive. A failing
gate means no **new** archive is written. It does not mean the output
directory is empty: `package` returns before touching it, so an archive left
by an earlier successful run with the same slug and version is still sitting
there, and nothing in the failure output mentions it. Package into a fresh
directory, or check the timestamp, before believing a zip is the build you
just ran.

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

## What the gates said, including every warning

All nine passed, and five of them passed while saying something a reader
should know. The warnings are the interesting part, and all five are here: a
transcript that quietly drops one is not a transcript.

| gate | what it said |
|---|---|
| `B-contradictions` | 1 of 1 unresolved and flagged for digging; at this rate that is the intended outcome, not a failure |
| `B-profile` | only the `oppose` seat is claimable, which is a normal result worth stating plainly |
| `G4-holdout` | the consensus pool was 86% over 7 items, reported but not gated: a model with no reconstruction also answers those |
| `G2-anchor` | 1 claim is marked `inference` and exempt from the quote check, "and `G3` verifies that the output labels them" |
| `G3-disclosure` | "output contains inference labels; confirm each is attached to a claim" |

Those last two rows quote the gates verbatim, and the clause quoted from
`G2-anchor` is not true today. `G3` does not check each inference claim's
label: it warns when the word `inference` occurs anywhere in the rendered
skill, and says nothing at all when it is absent, so an unlabelled inference
passes silently. The claim appears in `anchor.py` as well as in the gate's
output. Both are being fixed separately; this example states what the tool
does now rather than what its own warning says it does.

The holdout is twelve items, five of them divergent from a no-reconstruction
baseline, and one deliberate miss in the consensus pool. A set where the
reconstruction agrees with the subject on everything is a set that never
asked a hard question.

## Writing this example found real bugs in the example

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

Three more passed all nine gates and were found in review: a contradiction
whose earlier claim was anchored to a quote that did not support it, a flip
condition encoded `above_stops` where the source says values **below** the
threshold stop the project, and per-seat holdout lists that totalled fifteen
observations against a global set of twelve.

That is worth more as a demonstration than a bundle that passed on the first
try. The gates caught the first; the last three they cannot catch, and saying
which is which is the point of keeping them here.
