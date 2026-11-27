<h1 align="center">persona-to-skill</h1>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
<strong>Turn a practitioner's documented method into an agent skill — one that cites its sources and proves it transferred.</strong>
</p>

<p align="center">
  <em>Not "clone anyone." Reconstruct a method, with receipts.</em>
</p>

---

## Why this is not a persona cloner

Ask a model to *be* someone and you get the one thing it is already good at:
voice. Cadence, catchphrases, the shape of their sentences. What you do not get
is their judgement, because judgement lives in the parts of their output nobody
clips — the follow-up question, the case they turned down, the post-mortem on a
deal that died.

So a persona prompt produces an advisor that **sounds right and decides
generically**. That is the worst possible failure mode, because the voice is
convincing enough that you stop checking.

This tool goes the other way. It extracts decision rules and refuses to
impersonate, which forces an unanswerable question to read as unanswerable
instead of being smoothed over in a familiar tone.

Two consequences, and they are the whole design:

1. **Every attributed claim names a source and quotes it**, and the quote is
   verified against the source file on disk. Not "probably said something like
   this" — the passage, or the claim does not ship.
2. **The skill is scored on questions held back from extraction.** Questions
   the subject has publicly answered, that the pipeline never saw. Alignment on
   held-back material is the only evidence a method transferred rather than a
   mannerism. The default gate is 80%.

## What it produces

```
reconstructions/<slug>/
├── SKILL.md              Decision rules, with a source anchor on every claim
├── decision-table.md     Situation → what they ask first → criteria → what they refuse
├── refusals.md           The conditions under which they say no
├── positions-changed.md  Views they have revised, newest first
├── sources.json          Every source: tier, date, retrieval provenance
└── holdout-report.md     Alignment, divergences, and what stayed unknown
```

`refusals.md` tends to be the most useful file. Anyone can paraphrase a
practitioner's positive claims; almost nobody can guess the conditions under
which they decline. That is the part that behaves like a fingerprint.

`positions-changed.md` exists because people change their minds and corpora do
not. Citing a view someone has publicly abandoned is the fastest way to
discredit an advisor built this way.

## Source tiers

Assigned per document, not per project.

| Tier | Material | Treatment |
|------|----------|-----------|
| **T0** | Private, supplied by the subject | Requires a consent record naming it |
| **T1** | Public and freely citable | Quote and cite |
| **T2** | Public but copyrighted | Short quotations with attribution only |
| **T3** | Paywalled, leaked, scraped from a closed community | **Never enters the pipeline** |

T3 is a category, not a threshold. No consent record and no output scope
unlocks it.

## Output scope

One axis, because only one question needs a switch: where does the result go.

| | `PRIVATE` | `PUBLISHED` |
|---|---|---|
| Source tier gate | enforced | enforced |
| Source anchor gate | enforced | enforced |
| Holdout gate | enforced | enforced |
| Disclosure block | not required | **required** |
| Impersonation phrasing | warned | **blocked** |

Building an advisor from someone's public talks, for your own use, is ordinary
and this tool does not lecture you about it. The source and quality gates still
run — not to protect the subject, but because **you** are the one who gets hurt
by an advisor that invents a rule and states it confidently.

Disclosure applies when someone else reads the output, because that is the
point at which a third party can be misled.

## What it will not do

* Voice cloning, or any audio rendition of the subject
* Images, video, or avatars depicting the subject
* First-person dialogue presented as the subject speaking
* Any claim that the subject authored, reviewed, or endorsed the output

These are refused in every scope. The 2024–2026 wave of digital-replica
statutes — Tennessee's ELVIS Act, Washington SB 5886, California SB 1111, the
proposed federal NO FAKES Act — reaches voice and visual likeness. This tool
produces text and stays on its side of that line.

## Capability limits

Stated plainly so the tool is not read as offering what it cannot:

* Cannot verify that a consent record is genuine. It checks structure only.
* Cannot establish that a source is authentic, correctly attributed, or current.
* Cannot determine whether a use is lawful anywhere. **Not legal advice.**
* Cannot reconstruct judgement the sources never recorded. Sparse material
  yields a sparse result, reported as sparse.
* Cannot detect that a subject withdrew consent after a build.

## Gates

Four, each with negative tests that must go red on a deliberately broken input.
A gate that cannot fail is worse than no gate, because it grants false
confidence.

| Gate | Blocks on |
|------|-----------|
| `G1-consent` | T3 present; T0 without a consent record; untiered or unreadable sources |
| `G2-anchor` | A quote absent from its source; a figure the source does not contain; a claim with no source |
| `G3-disclosure` | Impersonation when published; an incomplete disclosure block |
| `G4-holdout` | Alignment below 80%; fewer than 10 scored items; over 30% unobserved |

Each gate recomputes independently, fails closed when an input it depends on is
missing, and reads the artifact actually being delivered rather than a fixture.

`G4-holdout` treats **unknown as a first-class state**. An item with no recorded
observation is not a pass and not a failure: it leaves the denominator and is
reported separately. A high unknown rate fails the gate and blames the question
set, which is where the defect is. (`bool` is a subclass of `int` in Python, so
a JSON `true` would satisfy a naive integer check and be summed as 1 — this
module refuses to invent a score nobody recorded.)

## Prior art

[book-to-skill](https://github.com/virgiliojr94/book-to-skill) does this for
books, and does it well. A book arrives pre-structured: the author already named
the frameworks, ordered the chapters, and paired the cases. A person's output
has none of that. It is scattered, repetitive, self-contradictory across years,
and weighted toward conclusions rather than reasoning — which is why the
extraction here is weighted toward the opposite: interviews under follow-up,
public disagreements, post-mortems, and refusals.

The evaluation harness follows book-to-skill's approach to scoring, which
refuses to derive missing observations.

## License

Apache-2.0. Section 6 grants no trademark rights: a fork may change the code but
may not present itself as this project.
