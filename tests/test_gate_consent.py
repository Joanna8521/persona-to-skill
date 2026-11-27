# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path

import _base  # noqa: F401
from persona_to_skill.gates import consent

GOOD_CONSENT = {
    "subject_name": "A. Example",
    "granted_to": "Studio X",
    "scope": "the 12 interview transcripts listed in sources.json",
    "signed_date": "2026-11-01",
    "revocable": "yes, on 30 days written notice",
}


def _consent_file(data):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return Path(f.name)


# ----------------------------------------------------------------- positive
def test_public_sources_pass():
    v = consent.check([{"id": "s1", "tier": "T1"}, {"id": "s2", "tier": "T2"}])
    assert v.passed, v.errors


def test_private_build_from_public_sources_passes():
    """The most common real use: build an advisor from someone's public
    material, for your own use. Nothing here to block."""
    v = consent.check([{"id": f"talk{i}", "tier": "T1"} for i in range(8)])
    assert v.passed, v.errors
    assert v.stats["t0_count"] == 0


def test_t0_with_consent_passes():
    v = consent.check([{"id": "s1", "tier": "T0"}], _consent_file(GOOD_CONSENT))
    assert v.passed, v.errors
    assert v.warnings, "must warn that signature authenticity is unverified"


# ----------------------------------------------------- negative: must go red
def test_t3_always_blocks_even_with_consent_on_file():
    v = consent.check([{"id": "leak", "tier": "T3"}], _consent_file(GOOD_CONSENT))
    assert not v.passed
    assert any("never usable" in e for e in v.errors)


def test_t0_without_consent_blocks_rather_than_skipping():
    """The fail-open shape this guards against: optional input absent, check
    quietly waved through. Applies to a private build too -- private material
    needs the record whoever is building."""
    v = consent.check([{"id": "s1", "tier": "T0"}], None)
    assert not v.passed
    assert any("consent" in e.lower() for e in v.errors)


def test_unreadable_consent_file_blocks():
    bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    bad.write("{not json")
    bad.close()
    v = consent.check([{"id": "s1", "tier": "T0"}], Path(bad.name))
    assert not v.passed, "unreadable consent treated as absent instead of blocking"


def test_incomplete_consent_blocks_each_missing_field():
    for field in consent.CONSENT_REQUIRED_FIELDS:
        partial = {k: v for k, v in GOOD_CONSENT.items() if k != field}
        v = consent.check([{"id": "s1", "tier": "T0"}], _consent_file(partial))
        assert not v.passed, f"missing {field} did not block"


def test_blank_consent_field_blocks():
    blank = dict(GOOD_CONSENT, scope="   ")
    v = consent.check([{"id": "s1", "tier": "T0"}], _consent_file(blank))
    assert not v.passed


def test_untiered_source_blocks():
    v = consent.check([{"id": "mystery"}])
    assert not v.passed


def test_unknown_tier_blocks():
    v = consent.check([{"id": "s1", "tier": "T9"}])
    assert not v.passed


def test_empty_manifest_blocks():
    assert not consent.check([]).passed


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
