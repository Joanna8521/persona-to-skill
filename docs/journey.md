# What using this actually looks like

Written before the collection and packaging stages exist, so the gates that do
exist can be wired into the right place rather than bolted on afterwards.

## The shape

```
A  collect     name a subject, gather public material, tier every source
B  validate    all gates run; the holdout is cut from the corpus itself
C  package     only a green run produces a zip, stamped with a corpus fingerprint
D  install     the user installs it by hand, once
E  correct     fixes go back to B, never straight to D
```

## Why B comes before C

The obvious journey puts validation last: build the skill, install it, use it,
and find out it misattributes something. That is backwards, and the reason is
D. Installing a skill is a manual step, and installing one inside a
conversation lasts only for that conversation. So every correction costs the
user a reinstall.

A pipeline whose trigger for revalidation is *the user noticing a problem* has
put its quality control after its most expensive step. The v1.0 zip has to
arrive already tested. The alternative charges the user for every miss.

Hence E returns to B. A corrected corpus is an unvalidated corpus; the
correction itself has not been checked.

## Two tests, and they are not the same test

A reconstruction can be faithful and useless. If the subject's public material
is all about hiring and the user wants to ask about pricing, a perfectly
accurate reconstruction answers nothing they need. So B runs two things, and
only one of them is a gate.

| | Questions come from | Asks | Status |
|---|---|---|---|
| **Fidelity** (`G4-holdout`) | the **subject**, publicly answered, held back from extraction | does this reproduce their judgement | **gate**: no pass, no zip |
| **Coverage** | the **user**, from what they actually intend to ask | is this useful to me | report |

Coverage is a report rather than a gate because sparse coverage is not a
defect, it is a fact about what the subject has said in public. But it governs
the one question worth asking the user before packaging, and it changes that
question's shape:

> Of the eight kinds of question you want to ask, the corpus can answer five.
> It has nothing on pricing, channel strategy, or how they handle layoffs. If
> you have their material on those, a talk transcript, a paid newsletter, a
> book, uploading it would close the gap directly.

That is a request someone can act on. "Would you like to upload anything?" is
not.

## Sources

Collection has to handle video, because for many subjects most of the public
material is video. Shorts, reels, talks, interviews, podcasts.

### Provenance is measured, not taken on trust

A transcript is a machine's or a person's rendering of what was said, not the
thing itself, so a quote from it is a quote of the rendering. The question is
how much that matters, and it varies enormously: plenty of subjects review
their own captions, because captions carry search and accessibility weight, and
a reviewed track is as good as prose.

The tempting shortcut is to read YouTube's `trackKind` field, which marks a
track `ASR` or `standard`, and treat `ASR` as weaker. Do not build on that
alone. Whether editing an auto-generated track reclassifies it is not
documented anywhere we could find, so the label may say "automatic" about a
track a person corrected line by line, or say nothing useful at all.

Measure the artifact instead:

| Signal | How |
|---|---|
| punctuation density | sentence-ending marks per hundred characters |
| sentence case | proportion of sentence starts that are capitalised |
| cue segmentation | whether text arrives in timed fragments |

A transcript carrying real punctuation and real casing has been written or
reviewed by someone, whatever its label claims, and is treated as text. One
with neither has not, whatever its label claims.

This also puts the consequence in the right place. An unpunctuated transcript
is not *less honest* about what the subject believes, it is **unanchorable**.
`G2-anchor` verifies a quote against its source, and an unpunctuated,
uncapitalised, mis-heard stream cannot support that check. The problem is
mechanical rather than a judgement about anyone's diligence.

Burned-in on-screen text read by OCR is in the same position, and says so.

### Cue joining

Even a human-written caption track is segmented by time, not by sentence, so a
sentence routinely spans several cues. Cues are joined before storage, exactly
as hard-wrapped lines are. `experiments/g2_realcorpus.py` has the measurements
behind that: before wrapped lines were rejoined, every passage crossing a wrap
point failed to match.

## The install step cannot be fixed, so make it rare

Installing by hand, once, is a cost this project cannot remove. What it can do
is stop charging that cost repeatedly:

* every gate runs before a zip exists;
* the zip carries a corpus fingerprint and a version, so a user can tell which
  build they are running;
* regenerating from a fixed corpus is deterministic, so a correction costs one
  reinstall and not a round of guessing.

## Naming

The machine is `persona-to-skill`. Its output is not. A package called
`<name>-persona-to-skill` announces what built it; `<name>-method` says what it
is, which is what someone picking it out of a list needs to know.

## State of this

| Stage | Built |
|---|---|
| A collect | partly: cue joining, provenance measurement and speaker attribution are done; the fetchers are not |
| B validate | gates yes (`G1` to `G5`, 154 tests); not yet on the packaging path |
| C package | no |
| D install | manual, by the user |
| E correct | follows from B |

The gates currently validate an artifact shape that nothing in this repository
produces yet. That is the next thing to fix.
