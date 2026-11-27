# -*- coding: utf-8 -*-
"""Caption handling, and the attribution rules that keep a transcript honest.

Every rule here was found by running against a real human-written transcript of
a talk, 427 cues, not by reasoning about what transcripts are like. The
measurements that justify each one are in the module docstrings.
"""
import _base  # noqa: F401
from persona_to_skill.collect import transcript as tr
from persona_to_skill.collect.transcript import Cue

VTT = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
There have been three themes
running through the conference,

2
00:00:04.000 --> 00:00:07.000
which are relevant
to what I want to talk about.

3
00:00:12.000 --> 00:00:14.000
So that is the first one.
"""

SRT = """1
00:00:01,000 --> 00:00:04,000
I walk away from a stalled deal,

2
00:00:04,000 --> 00:00:06,000
rather than discount.
"""


# ------------------------------------------------------------------ parsing
def test_vtt_parses():
    cues = tr.parse_vtt(VTT)
    assert len(cues) == 3
    assert cues[0].start_ms == 1000 and cues[0].end_ms == 4000


def test_srt_parses_with_comma_decimals():
    assert len(tr.parse_vtt(SRT)) == 2


def test_short_timecodes_parse():
    assert len(tr.parse_vtt("WEBVTT\n\n00:01.000 --> 00:03.000\nhello there.\n")) == 1


def test_header_and_notes_are_not_cues():
    raw = "WEBVTT\n\nNOTE this is a comment\n\n00:00:01.000 --> 00:00:02.000\nreal text.\n"
    assert len(tr.parse_vtt(raw)) == 1


def test_vtt_markup_is_stripped():
    raw = ("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n"
           "<c.yellow>styled</c> and <00:00:01.500>timed text.\n")
    assert "<" not in tr.parse_vtt(raw)[0].text


def test_voice_tag_becomes_a_speaker_label():
    """<v Name> carries attribution, so it is recovered before the tag
    stripper discards it."""
    raw = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Morris Chang>Not always.</v>\n"
    who, rest, inline = tr.split_speaker(tr.parse_vtt(raw)[0].text)
    assert who == "Morris Chang" and rest == "Not always." and not inline


def test_cue_list_parses():
    cues = tr.parse_cue_list([{"text": "one.", "time": 0}, {"text": "two.", "time": 2000}])
    assert len(cues) == 2 and cues[1].start_ms == 2000


# ------------------------------------------------------------------ joining
def test_cues_spanning_a_sentence_are_joined():
    """41% of cues in the real transcript ended mid-sentence, so two in five
    quotes drawn across a boundary would have failed G2."""
    text = tr.join_cues(tr.parse_vtt(VTT))
    assert "three themes running through the conference, which are relevant" in text


def test_display_wrapping_inside_a_cue_is_undone():
    assert "\n" not in tr.join_cues([Cue(0, "a line\nwrapped for display.")])


def test_paragraph_break_needs_both_a_finished_sentence_and_a_pause():
    done_and_pause = [Cue(0, "First point.", 1000), Cue(9000, "Second point.")]
    assert "\n" in tr.join_cues(done_and_pause)

    pause_mid_sentence = [Cue(0, "First point and", 1000), Cue(9000, "it continues.")]
    assert "\n" not in tr.join_cues(pause_mid_sentence)

    done_no_pause = [Cue(0, "First point.", 1000), Cue(1100, "Second point.")]
    assert "\n" not in tr.join_cues(done_no_pause)


def test_stage_directions_are_dropped():
    for noise in ("(Laughter)", "[MUSIC]", "（笑聲）", "【音樂】"):
        assert noise not in tr.join_cues([Cue(0, "Real words."), Cue(2000, noise)])


# --------------------------------------------------------- speaker detection
def test_speaker_forms_are_detected():
    for text, who in (("(Audience) Good.", "Audience"),
                      (">> JOHN: I walk away.", "JOHN"),
                      ("Interviewer: Why?", "Interviewer"),
                      ("MODERATOR: next question", "MODERATOR"),
                      ("Morris Chang: We never discount.", "Morris Chang"),
                      ("林志明：我不打折。", "林志明")):
        assert tr.split_speaker(text)[0] == who, text


def test_a_colon_inside_a_sentence_is_not_attribution():
    """The false positive matters more than the miss: labelling the subject's
    own words as another speaker's drops them from what can be quoted."""
    for text in ("I said: never discount.", "The ratio: about three to one.",
                 "One more thing: margin is the point."):
        assert tr.split_speaker(text)[0] is None, text


def test_bracketed_is_inline_and_colon_is_a_turn():
    assert tr.split_speaker("(Audience) Good.")[2] is True
    assert tr.split_speaker("Interviewer: Why?")[2] is False


def test_roles_that_are_never_the_subject():
    for label in ("Audience", "INTERVIEWER", "Moderator", "主持人", "觀眾"):
        assert tr.is_non_subject(label), label
    for label in ("Morris Chang", "JOHN", "林志明", None):
        assert not tr.is_non_subject(label)


# ------------------------------------------------------------- attribution
def test_an_interjection_does_not_reassign_the_rest():
    """The real bug this caught: one bracketed "(Audience)" in a 427-cue
    monologue reassigned the remaining 382 cues away from the speaker."""
    cues = [Cue(0, "Good morning."), Cue(2000, "(Audience) Good."),
            Cue(4000, "It has been great."), Cue(6000, "I am leaving.")]
    r = tr.attribute(cues, "Ken Robinson")
    assert r["counts"][tr.SUBJECT] == 3
    assert r["counts"][tr.OTHER] == 1


def test_a_turn_marker_holds_until_the_next_label():
    cues = [Cue(0, "Interviewer: Why walk away from a stalled deal?"),
            Cue(3000, "Morris Chang: Discounting teaches them to wait."),
            Cue(6000, "And margin is the point.")]
    r = tr.attribute(cues, "Morris Chang")
    assert r["inherited_labels"] is True
    subject = [t for t in r["turns"] if t["speaker_class"] == tr.SUBJECT]
    assert subject[0]["cues"] == ["Discounting teaches them to wait.",
                                  "And margin is the point."]


def test_sparse_labelling_yields_unknown_rather_than_a_guess():
    """A transcript that labels one turn out of many has not said who spoke the
    rest. Inheriting there assigns the subject's answers to someone else."""
    cues = [Cue(0, "Interviewer: Why walk away from a stalled deal in month three?")] + \
           [Cue(3000 + i * 2000, f"Point number {i} about pricing discipline.") for i in range(12)]
    r = tr.attribute(cues, "Morris Chang")
    assert r["inherited_labels"] is False
    assert r["counts"][tr.UNKNOWN_SPEAKER] == 12
    assert r["counts"][tr.SUBJECT] == 0


def test_an_unrecognised_label_is_unknown_not_assigned():
    """Label detection is heuristic, so an unmatched label is surfaced rather
    than guessed in either direction."""
    cues = [Cue(0, "Morris Chang: I walk away from stalled deals, always."),
            Cue(3000, "我覺得：這樣不行，風險太高了吧。"),
            Cue(6000, "Morris Chang: Not always, but usually it holds.")]
    r = tr.attribute(cues, "Morris Chang")
    assert r["counts"][tr.UNKNOWN_SPEAKER] >= 1
    assert "我覺得" in r["unresolved_labels"]


def test_name_variants_match_the_subject():
    for label in ("Morris Chang", "CHANG", "Morris"):
        cues = [Cue(0, f"{label}: I walk away from stalled deals, every time."),
                Cue(3000, "Interviewer: Always, in every single market?")]
        r = tr.attribute(cues, "Morris Chang")
        assert r["counts"][tr.SUBJECT] >= 1, label


# -------------------------------- other speakers are context, not contamination
def test_a_subject_turn_carries_what_prompted_it():
    """"Not always." says nothing without the question before it, and material
    where the subject is pushed is the most informative there is."""
    cues = [Cue(0, "Interviewer: Is that always true, in every market?"),
            Cue(3000, "Morris Chang: Not always.")]
    turns = tr.attribute(cues, "Morris Chang")["turns"]
    subject = [t for t in turns if t["speaker_class"] == tr.SUBJECT][0]
    assert subject["prompted_by"]["label"] == "Interviewer"
    assert "every market" in subject["prompted_by"]["text"]


def test_non_subject_turns_are_kept_not_discarded():
    cues = [Cue(0, "Interviewer: Is that always true, in every market?"),
            Cue(3000, "Morris Chang: Not always.")]
    turns = tr.attribute(cues, "Morris Chang")["turns"]
    assert any(t["speaker_class"] == tr.OTHER for t in turns)


def test_continuing_through_an_interjection_keeps_the_real_prompt():
    cues = [Cue(0, "Interviewer: Is that always true, in every market?"),
            Cue(3000, "Morris Chang: Not always."),
            Cue(6000, "(Audience) Interesting."),
            Cue(8000, "But usually.")]
    turns = tr.attribute(cues, "Morris Chang")["turns"]
    last = [t for t in turns if t["speaker_class"] == tr.SUBJECT][-1]
    assert last["prompted_by"]["label"] == "Interviewer"
    assert last.get("continues_through_interjection") is True


# ------------------------------------------------------------------- ingest
def test_ingest_reports_that_the_prose_was_assembled():
    r = tr.ingest(VTT)
    assert r["provenance"]["cue_segmented"] is True
    assert r["provenance"]["cues_joined"] == 3
    assert r["provenance"]["kind"] == "transcript"


def test_ingest_of_unpunctuated_captions_is_not_anchorable():
    """Long enough that locating a quote needs sentence boundaries. A short
    unpunctuated source IS anchorable, because the whole of it is the quotable
    unit; that distinction is tested in test_collect_provenance.py."""
    blocks = []
    for i in range(60):
        blocks.append(f"00:00:{i % 60:02d}.000 --> 00:00:{(i + 1) % 60:02d}.000\n"
                      "i walk away from a stalled deal rather than discount it to close")
    raw = "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"
    prov = tr.ingest(raw)["provenance"]
    assert prov["chars"] > 1000, prov["chars"]
    assert prov["anchorable"] is False


if __name__ == "__main__":
    import sys
    sys.exit(_base.run_module(dict(globals())))
