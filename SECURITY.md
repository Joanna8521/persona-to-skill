# Security policy

## Reporting

Report a vulnerability through GitHub's private advisory form:
**Security → Report a vulnerability** on this repository. Please do not open a
public issue for anything exploitable.

Expect an acknowledgement within a week.

## What this project treats as a vulnerability

Beyond the usual, two classes specific to what it does:

**Gate bypass.** A way to get a reconstruction past a gate that should have
blocked it: prohibited-tier material entering the pipeline, a fabricated quote
passing anchor reconciliation, impersonation phrasing surviving into published
output, or a holdout score that counts consensus answers as alignment. These are
the project's whole purpose; a bypass is a vulnerability, not a bug.

**Corpus-driven injection.** Source material is untrusted input. A corpus file
that steers the pipeline through its own content — instructions in a transcript,
control characters, bidirectional overrides that change how a quote renders
against what was verified — is a vulnerability.

## Verifying what you installed

Only this repository is this project:

> **https://github.com/Joanna8521/persona-to-skill**

A re-upload under another account is not maintained, reviewed, or endorsed here,
whatever it is called. This matters more than usual for a tool of this kind: it
reads private material supplied under a consent record, so a modified copy is
well placed to exfiltrate exactly the material a subject agreed to share with
one builder.

Before running a copy you did not clone from the URL above, check it against
this repository: in particular `persona_to_skill/contract.py` and
`persona_to_skill/gates/`, which hold every threshold and every refusal. CI runs
`gates-intact.yml` on every pull request here, so a fork that weakened a gate
would show it.
