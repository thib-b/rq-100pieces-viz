"""Pure tests for the outro's regrown plate (sleepy piano)."""
from songs.nothing import colonies, cues, manifest, timeline
from songs.nothing.styles import plate_colonies as pc

RUN = {r.section.id: r for r in manifest.walk(timeline.load())}["sleepy_piano"]
SEC = RUN.section


def test_blooms_grow_slowly_and_late_ones_finish_in_the_zoom():
    sched = colonies.growth(cues.raw()["scene3"]["piano_onsets"], 60)
    assert all(e - b == 240 for b, e in sched)                 # every bloom swells over 4 s
    shown = {b["seed"] for b in RUN.plan["blooms"]}
    assert shown == {i for i, (b, _) in enumerate(sched) if b <= SEC.last}
    assert all(b >= SEC.first for b, _ in sched)
    # whatever is still growing at the bass entry, the zoom's level-0 plate finishes — same keys
    zoom = {r.section.id: r for r in manifest.walk(timeline.load())}["outro_bass"].plan
    still = {(i, b, e) for i, (b, e) in enumerate(sched) if e > SEC.last}
    assert still and still == set(zoom["zero"])


def test_colonies_start_on_piano_phrases_biggest_first():
    data = colonies.data()
    onsets = cues.raw()["scene3"]["piano_onsets"]
    starts = pc.cluster_onsets(data["clusters"], onsets)
    biggest = max(data["clusters"], key=lambda c: c["area"])
    assert starts[biggest["id"]] == onsets[0]
    assert set(starts.values()) == set(onsets)


def test_blooms_are_identical_across_styles():
    a = colonies.blooms(2.5, 1.6)
    b = colonies.blooms(2.5, 1.6)
    assert a == b and len(a) == len(colonies.data()["seeds"])


def test_hands_on_the_growing_plate():
    assert RUN.exit["mode"] == "plate_growing"
    assert abs(RUN.exit["dish_r"] - RUN.plan["dish_r"]) < 1e-6
