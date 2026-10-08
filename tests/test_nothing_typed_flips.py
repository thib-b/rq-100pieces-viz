"""Pure tests for the typed verse 2 and the NOTHING flips."""
from songs.nothing import cues, manifest, timeline
from songs.nothing.styles import nothing_flips as nf
from songs.nothing.styles import typed_lyrics as tl

RUNS = {r.section.id: r for r in manifest.walk(timeline.load())}


def test_verse2_lines_are_the_sung_lines_in_order():
    texts = [ln["text"] for ln in RUNS["verse2"].plan["lines"]]
    assert texts == [
        "A knock on the front door of your day:", "Fill out the survey.",
        "Don't listen to the bitterness in your brain", "But a question remains:",
        "What does, what does, what does a promise mean?", "What does a promise mean?"]


def test_typing_is_monotonic_one_line_at_a_time_and_tiles_frames():
    sec = RUNS["verse2"].section
    lines = RUNS["verse2"].plan["lines"]
    owner = {}
    for li, ln in enumerate(lines):
        assert " ".join(r["text"] for r in ln["rows"]) == ln["text"]
        for ri, r in enumerate(ln["rows"]):
            prev = 0
            for sp in r["spans"]:
                assert len(sp["text"]) > prev and r["text"].startswith(sp["text"])
                prev = len(sp["text"])
                for f in range(sp["first"], sp["last"] + 1):
                    assert (ri, f) not in owner, f"two prefixes of a row on frame {f}"
                    owner[(ri, f)] = li
            assert r["spans"][-1]["text"] == r["text"]          # every row fully typed
    # one line at a time: frames never show rows of two different lines
    by_frame = {}
    for (ri, f), li in owner.items():
        assert by_frame.setdefault(f, li) == li
    assert max(by_frame) == sec.last                            # last line held to the end


def test_rows_wrap_long_lines():
    lines = RUNS["verse2"].plan["lines"]
    for ln in lines:
        assert all(len(r["text"]) <= 30 for r in ln["rows"])
    assert len(lines[4]["rows"]) == 2                           # the stuttered line wraps


def test_first_character_appears_when_the_word_is_sung():
    ln = RUNS["verse2"].plan["lines"][0]
    first = ln["rows"][0]["spans"][0]["first"]
    assert abs(first - (round(102.36 * 60) + 1)) <= 1          # "A" at 1:42.36


def test_flip_colours_alternate_and_text_fades_out():
    p = nf.DEFAULTS
    t0 = cues.nothing_typed()
    assert nf.colours_at(t0) == ("#ffffff", "#000000")       # black on white
    flips = cues.nothing_flips()
    for i, f in enumerate(flips):
        bg, fg = nf.colours_at(f + 0.01)
        assert (bg == "#000000") == (i % 2 == 0)
    claps = cues.clap_flips()
    hold = (cues.scene1()["music_stop"] + claps[0]) / 2               # the pause before the claps
    assert nf.colours_at(hold) == ("#000000", "#ffffff")
    gaps = []
    for i, f in enumerate(claps):
        bg, fg = nf.colours_at(f + 0.01)
        assert bg in ("#000000", "#ffffff")                  # backgrounds stay pure
        assert (bg == "#ffffff") == (i % 2 == 0)             # and keep alternating
        gaps.append(abs(int(bg[1:3], 16) - int(fg[1:3], 16)))
    assert gaps == sorted(gaps, reverse=True) and gaps[-1] == 0   # text fades into its bg
    assert nf.colours_at(claps[-1] + 0.01) == ("#ffffff", "#ffffff")   # ends on white, text gone


def test_flip_sections_hand_over_and_end_blank():
    assert RUNS["nothing2"].exit["mode"] == "nothing"
    ex = RUNS["claps"].exit
    assert (ex["mode"], ex["background"]) == ("blank", "#ffffff")   # 38th flip: white, text gone
    # NOTHING is fully typed through the claps section
    assert RUNS["claps"].plan["spans"] == [{"text": "NOTHING", "first": RUNS["claps"].section.first,
                                            "last": RUNS["claps"].section.last}]
    keys = RUNS["nothing2"].plan["keys"]
    assert len(keys) == 1 + 11                               # initial + one per flip


def test_each_flip_key_lands_on_the_frame_of_its_cue():
    keys = RUNS["nothing2"].plan["keys"]
    for i, (f, bg, fg) in enumerate(keys[1:]):
        assert f == round(cues.nothing_flips()[i] * 60) + 1
        assert (bg == "#000000") == (i % 2 == 0)        # first flip → white on black


def test_clap_flips_each_get_their_own_frame_before_the_bridge():
    keys = RUNS["claps"].plan["keys"]
    frames = [f for f, _, _ in keys[1:]]
    assert len(frames) == 27 and len(set(frames)) == 27
    assert frames[-1] < RUNS["strings_bridge"].section.first
