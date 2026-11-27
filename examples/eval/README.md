# A worked eval, end to end

Everything here is **invented**. The subject is nobody, the quotes were written
for this directory, and the numbers are whatever makes the run interesting. It
exists so that `persona-to-skill eval` can be run once before anyone writes
their own suite, and so that CI runs it on every commit.

```bash
persona-to-skill eval examples/eval/manifest.json \
    --run examples/eval/run.json \
    --corpus examples/eval/corpus \
    --subject "A Practitioner"
```

Exits 0. The gated figure is 90%: nine of ten divergent items aligned.

## The three files

`corpus/src1.txt` … `src14.txt` are the sources. Each contains its quote
surrounded by other prose, because a quote that is the entire file would not
test anything about anchoring.

`manifest.json` is the question set. Each item carries the question, the
`source_id`, and `subject_said`: what the subject actually said. That last
field is the ground truth, and it goes through **G2** before any number is
printed. An eval suite is not exempt from the gate for being the thing doing
the measuring; a quote that is not in its source would make every figure
downstream rest on an unverified assertion.

`run.json` is the observations, and **this tool did not produce them**. Each
item carries what the reconstruction answered, what a baseline with no
reconstruction answered, whether each matched, who judged, and whether the
judge was blind.

## Try breaking it

Each of these turns the run red or drops items out of the score, which is the
quickest way to see what the harness is actually enforcing.

| Change | What happens |
|---|---|
| Edit a `subject_said` so it no longer matches its source | G2 fails, no score is printed at all |
| Set `blind` to `false` on every item | The gated figure reads "not measured" rather than 100% |
| Set `judged_by` to `""` | Same: an unnamed instrument is not a measurement |
| Change an `aligned` to `"yes"` | Refused at load. A string is not an observation |
| Change an `aligned` to `1` | Also refused. `1 == True` in Python, and that is exactly how an invented score gets in |
| Delete half the run items | Reported as "no entry in the run". They do not count as misses, and the remaining items still read 100%. The run fails anyway, on the floor of 10 scored items: a ratio over 7 is noise however it reads |
| Add `"seen_in_extraction": true` to every manifest item | Nothing is scored, which is the honest outcome |
| Add a run item with an id the manifest does not have | Hard error. There is no ground truth for a question nobody asked |

## What this example cannot show

Whether the questions were genuinely held back from extraction. Nothing in
these files can establish that, and the harness does not pretend otherwise:
`seen_in_extraction` is the author's own declaration. A suite built from
material the skill was trained on will score beautifully and mean nothing, and
no amount of checking inside this directory would catch it.
