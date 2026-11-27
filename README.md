<h1 align="center">persona-to-skill</h1>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
<strong>Turn a practitioner's documented method into an agent skill that cites its sources and proves it transferred.</strong>
</p>

<p align="center">
  <em>Not "clone anyone." Reconstruct a method, with receipts.</em>
</p>

---

## Why this is not a persona cloner

Ask a model to *be* someone and you get the one thing it is already good at:
voice. Cadence, catchphrases, the shape of their sentences. What you do not get
is their judgement, because judgement lives in the parts of their output nobody
clips: the follow-up question, the case they turned down, the post-mortem on a
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
   this", the passage, or the claim does not ship.
2. **The skill is scored on questions a generic model gets wrong.** Questions
   the subject has publicly answered, held back from extraction, and split by a
   recorded baseline: the same question answered with no reconstruction loaded
   at all.

   Most of what any practitioner says out loud is consensus, and a
   reconstruction answers those questions correctly whether or not it learned
   anything. Scored in one pool, five right out of ten that matter plus forty
   consensus answers reads as 90%. So the consensus pool is reported and never
   gated, and the gate reads the divergent pool, the questions where the
   default answer is wrong, and only judgement that actually carried across can
   be right. The default is 80% there, which is lift over baseline measured
   directly rather than subtracted.

   The honest consequence, which the gate states rather than hides: a subject
   whose public positions are all consensus cannot be meaningfully
   reconstructed.

## Why a person is harder than a book

Distilling a book is mostly transport. The author did the knowledge
engineering already: the frameworks have names, the chapters have an order, the
cases are paired to the claims they support.

A practitioner's output has none of that scaffolding. It is scattered across
years and formats, repetitive, and self-contradictory. The position they held
in 2021 may be one they have since argued against. It is also weighted the
wrong way: public material is mostly marketing, so it carries conclusions and
withholds the reasoning.

That shapes the extraction. Sources are not weighted equally:

| Weight | Material |
|---|---|
| High | Interviews under follow-up, public disagreements, post-mortems, cases they declined, answers to hostile questions |
| Low | Position pieces, promotional writing, quotable lines, course outlines |

A corpus of nothing but keynotes and listicles will not yield a single usable
decision rule, and the holdout gate will say so rather than produce a
confident-sounding shell.

## What it produces

```
reconstructions/<slug>/
├── SKILL.md              Decision rules, with a source anchor on every claim
├── decision-table.md     Situation, what they ask first, criteria, what they refuse
├── refusals.md           The conditions under which they say no
├── contradictions.md     Where they contradict themselves, and what reconciles it
├── sources.json          Every source: tier, date, retrieval provenance
└── holdout-report.md     Alignment, divergences, and what stayed unknown
```

`refusals.md` tends to be the most useful file. Anyone can paraphrase a
practitioner's positive claims; almost nobody can guess the conditions under
which they decline. That is the part that behaves like a fingerprint.

`contradictions.md` treats a contradiction as the find, not the problem.
Someone who argued one thing in 2021 and the opposite in 2024 has rarely
reversed: usually an unstated condition changed, and recovering that condition
is the most valuable thing in the whole reconstruction, because it is a
criterion the subject has never spelled out. So every entry has to answer what
condition makes both true, and where no condition can be found the entry stays
open and flagged. Picking the newer one and moving on throws the find away.

It also keeps an advisor from citing a view its subject has publicly abandoned,
which is the fastest way to discredit one.

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

## Video, and what a transcript is

For many subjects most of the public material is video, so collection has to
handle captions. Two things about that are measured rather than assumed, and
both were found by running against a real human-written transcript of a talk,
427 cues.

**Captions are segmented by display timing, not by sentence.** In that
transcript only 59% of cues ended on sentence punctuation, so two in five
quotes drawn across a cue boundary would have failed `G2-anchor` for a reason
that has nothing to do with misquoting: the quote spanned a boundary the
storage invented. Cues are joined before storage.

**A transcript carries other people's words.** That same transcript stored
"(Audience) Good." inline, two cues after the speaker's own first sentence.
Left undifferentiated, another person's words become quotable as the subject's,
and `G2-anchor` would pass such a quote correctly, because the words really are
in the source. That is misattribution produced by the storage.

So speaker turns are detected and tagged, and the tagging fails towards
*unknown*. Detection is heuristic and cannot be otherwise, since Chinese and
Japanese carry no case and "我覺得：" is shaped exactly like an attribution. A
turn is the subject's only when the label matches the subject, somebody else's
only when the label says so outright, and unknown otherwise, surfaced for a
person to resolve. Guessing either way loses: guess "subject" and another
person's words become quotable as theirs, guess "other" and the subject's own
words are dropped.

Non-subject turns are kept, because they are context rather than
contamination. "Not always." says nothing without the question before it, and
material where the subject is pushed is the most informative material there is,
so each subject turn records what prompted it.

### Anchorability is measured, not taken on trust

The shortcut is to read YouTube's `trackKind`, which marks a track `ASR` or
`standard`, and treat `ASR` as weaker. Do not. Whether editing an
auto-generated track reclassifies it is not documented anywhere we could find,
so the label may say "automatic" about a track someone corrected line by line.
It is recorded and decides nothing.

The stored text is measured instead, on sentence-ending punctuation and
sentence casing. Across ~190k characters of real human-written text in two
languages the density ran 1.02 to 1.85 marks per hundred characters, and the
same texts stripped measured exactly 0.00, so the bar sits in a gap nothing
lands in.

Be precise about what that buys. It establishes **anchorability**: text with
sentence boundaries can support quote reconciliation, an unpunctuated stream
cannot, because there is nothing to quote between. It does **not** establish
human review, since current speech recognition punctuates its own output.
Reading `anchorable` as "a person checked this" reads more than is there.

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
and this tool does not lecture you about it. The source and quality gates still run, and not to protect the subject.
**You** are the one who gets hurt by an advisor that invents a rule and states
it confidently.

Disclosure applies when someone else reads the output, because that is the
point at which a third party can be misled.

## What it will not do

* Voice cloning, or any audio rendition of the subject
* Images, video, or avatars depicting the subject
* First-person dialogue presented as the subject speaking
* Any claim that the subject authored, reviewed, or endorsed the output

These are refused in every scope. The 2024 to 2026 wave of digital-replica
statutes, Tennessee's ELVIS Act, Washington SB 5886, California SB 1111, the
proposed federal NO FAKES Act, reaches voice and visual likeness. This tool
produces text and stays on its side of that line.

## Capability limits

Stated plainly so the tool is not read as offering what it cannot:

* Cannot verify that a consent record is genuine. It checks structure only.
* Cannot establish that a source is authentic, correctly attributed, or current.
* Cannot determine whether a use is lawful anywhere. **Not legal advice.**
* Cannot reconstruct judgement the sources never recorded. Sparse material
  yields a sparse result, reported as sparse.
* Cannot detect that a subject withdrew consent after a build.

## Install and run

```bash
pip install .
```

Five subcommands. Each wraps a function that already existed and was already
tested, so the command line adds argument parsing and exit codes and nothing
else: a CLI that contains judgement of its own is a second implementation, and
the two drift.

```bash
# May this URL be fetched? robots.txt decides, and nothing else.
persona-to-skill fetch https://example.com/post/1 --robots robots.txt

# Records in the import contract shape into a corpus directory.
persona-to-skill import export.json \
    --subject "A Practitioner" --tier T2 --corpus corpus/

# Every gate on a bundle, without packaging. This is the CI-shaped one.
persona-to-skill gates bundle.json --corpus corpus/

# Gate, then write the zip only if every gate passed.
persona-to-skill package bundle.json --corpus corpus/ --out dist/

# The punctuation gate on the documentation.
persona-to-skill punct docs/
```

**The exit code is the whole point of it being a command.** 0 means the gate
passed; non-zero means it did not. Anything that prints a verdict and exits 0
is a gate that cannot be put in a CI job, which is the same as not having one.
A bare `persona-to-skill` with no subcommand exits non-zero too, because a
command that succeeds having done nothing is the same failure in miniature.

<details>
<summary>This command did not exist for eleven commits, and nothing noticed</summary>

`pyproject.toml` declared it from the first commit:

```toml
[project.scripts]
persona-to-skill = "persona_to_skill.cli:main"
```

`persona_to_skill/cli.py` did not exist. `pip install .` succeeded, `pip show`
reported the package as installed, and then:

```
$ persona-to-skill --help
ModuleNotFoundError: No module named 'persona_to_skill.cli'
```

321 tests and eleven CI checks were green throughout, because not one of them
ran the installed command. The tests import the package; the entry point is
resolved by a console script that only exists after an install.

This is a fourth shape of a gate that is not one, and the purest form of it.
The other three are wrong, stale, or untested, and each at least has something
to inspect. This one is **declared and absent**: it reads as a feature in the
packaging metadata and resolves to nothing at all.

Two things now hold it down. `tests/test_entry_points.py` parses
`[project.scripts]` and resolves every declared target, which catches an absent
module. A CI step invokes the installed command from a temporary directory
outside the repo, which catches the rest: a console script generated wrong, an
import that only fails outside the repo root, an exit code that does not come
back.

Writing it produced the same class of bug one level down. The first version
compared a verdict against `fetch.FETCH_OK`, a constant that does not exist
(they are `FETCH` and `IMPORT_ONLY`). Importing `cli.py` succeeded, the new
guard went green, and every `fetch` invocation ended in a traceback. Hence
`tests/test_cli.py`, which calls `main(argv)` and asserts on exit codes rather
than importing the module and stopping there.
</details>

## Gates

Five, each with negative tests that must go red on a deliberately broken input.
A gate that cannot fail is worse than no gate, because it grants false
confidence.

| Gate | Blocks on |
|------|-----------|
| `G1-consent` | T3 present; T0 without a consent record; untiered or unreadable sources |
| `G2-anchor` | A quote absent from its source; a figure the source does not contain; a claim with no source |
| `G3-disclosure` | Impersonation when published; an incomplete disclosure block |
| `G4-holdout` | Divergent-pool alignment below 80%; fewer than 5 divergent items; missing baselines; over 30% unobserved |
| `G5-interrogation` | A memo field left unanswered; a claim called fact with no source or with hedging; a committing verdict while the deciding number is unknown; confidence that contradicts the open evidence gaps |

Each gate recomputes independently, fails closed when an input it depends on is
missing, and reads the artifact actually being delivered rather than a fixture.

`G5-interrogation` exists because the things that go wrong in a deliberation
hide in fluent prose: an unsourced claim written as established fact, a
recommendation quietly resting on an assumption nobody verified, a hedge
standing where "I do not know" belongs. The more polished the output, the more
it needs that pass. Two of its rules carry most of the weight. A verdict that
commits to a decision is unavailable while the quantity that decides it is
still unknown, because what is missing then is a number rather than an opinion.
And a stated confidence has to cohere with the open evidence gaps in both
directions: high confidence alongside a gap that bears on the decision is
incoherent, and so is low confidence with nothing missing.

`G4-holdout` treats **unknown as a first-class state**. An item with no recorded
observation is not a pass and not a failure: it leaves the denominator and is
reported separately. A high unknown rate fails the gate and blames the question
set, which is where the defect is. (`bool` is a subclass of `int` in Python, so
a JSON `true` would satisfy a naive integer check and be summed as 1, so this
module refuses to invent a score nobody recorded.)

## License

Apache-2.0. Section 6 grants no trademark rights: a fork may change the code but
may not present itself as this project.
