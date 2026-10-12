"""Pure tests for the side-column lyrics layer (verse 1 + outro smoke)."""
import json

from songs.nothing import cues, timeline
from songs.nothing.styles import lyrics_columns as lc
from songs.nothing.timeline import asset

FPS = 60
FW, FH = 10.0, 5.625


def sched(**over):
    p = {**lc.DEFAULTS, **over}
    layout = json.loads(asset(lc.layout_path(p)).read_text())
    return layout, lc.schedule(layout, FW, FH, p, FPS, lc.clear_by(p)), p


def test_verse1_fully_dissolved_before_the_landing():
    layout, sch, p = sched()
    landing_f = round(cues.scene1()["landing"] * FPS) + 1
    assert len(sch["lines"]) == len(layout) == 18
    for ln in sch["lines"]:
        assert ln["gone"] <= landing_f
        for w in ln["words"]:
            assert w["birth"] + w["trace"] < w["leave"]


def test_words_appear_when_sung():
    layout, sch, _ = sched()
    for c, ln in zip(layout, sch["lines"]):
        for src, w in zip(c["words"], ln["words"]):
            assert w["birth"] == round(src["start"] * FPS) + 1


def test_lines_on_the_same_side_never_overlap_while_visible():
    for setname in ("verse1", "outro"):
        _, sch, _ = sched(set=setname, clear_by="")
        for a in sch["lines"]:
            for b in sch["lines"]:
                if a is b or a["side"] != b["side"]:
                    continue
                both = a["first"] <= b["gone"] and b["first"] <= a["gone"]
                ha, hb = a["H"] * a["scale"] / 2, b["H"] * b["scale"] / 2
                apart = abs(a["cy"] - b["cy"]) >= ha + hb
                assert not both or apart, (setname, a["text"], b["text"])


def test_columns_clear_the_dish_and_the_frame_edge():
    cols, (y0, y1) = lc.columns(FW, FH, lc.DEFAULTS)
    r = 0.5 * lc.DEFAULTS["dish_frac"] * FH
    assert cols["R"][0] > r and cols["L"][1] < -r
    assert cols["R"][1] < FW / 2 and cols["L"][0] > -FW / 2
    assert y0 > -FH / 2 and y1 < FH / 2


def test_outro_shows_each_sheet_line_once():
    song = timeline.load()
    p = {**lc.DEFAULTS, **song.section("outro_bass").params["lyrics"]}
    layout = json.loads(asset(lc.layout_path(p)).read_text())
    assert [c["text"] for c in layout] == [t.upper() for t in [            # all caps on screen
        "The definitive version the ideal.", "The wonderful image It's finally real.",
        "What does a promise mean?", "Nothing"]]
    assert lc.clear_by(p) is None
