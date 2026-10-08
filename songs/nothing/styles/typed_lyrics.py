"""typed_lyrics — verse 2, typed on the blank white we landed in (scene 1, 1:39 → 2:07.7).

Helvetica Neue Medium (the weight of the verse-1 lyrics), black on white, centred, ONE LINE AT A TIME: each word's characters appear one
by one, spread across the time the word is sung; a line holds until the next line starts
typing, which erases it. The last line is erased when the section ends (the typed NOTHING).
Long lines wrap (at word boundaries, by character count) into centred rows that type in turn.

Lines are the aligned phrases whose first word is sung inside the section (minus a margin
before its end so the "Nothing" loop belongs to the next section). Each character becomes
visible on a frame; every distinct prefix of a line is one text object shown for exactly its
frames (constant keys), so any single frame renders on its own.
"""
from __future__ import annotations

DEPENDS = ["songs/nothing/fonts.py"]

DEFAULTS = {
    "ink": "#000000",
    "paper": "#ffffff",
    "size": 0.95,               # text size (world units at magnification 1; frame width 10)
    "row_chars": 30,            # rows hold at most this many characters (balanced wrap)
    "leading": 1.12,            # row spacing (× size): wrapped rows sit close together
    "max_width": 0.86,          # widest row ≤ this fraction of the frame width (size shrinks)
    "end_margin": 0.25,         # phrases starting this close to the section end are left out (s)
}


def _p(ctx):
    return {**DEFAULTS, **ctx.params.get("typed", {})}


def display(token):
    return token.lstrip("-– ").strip()


def lines_in(words, t0, t1):
    """Group words (lyrics.Word) whose phrase starts in [t0, t1) into lines (phrase order)."""
    by = {}
    for w in words:
        if display(w.text):
            by.setdefault(w.phrase, []).append(w)
    return [ws for _, ws in sorted(by.items()) if t0 <= ws[0].start < t1]


def type_events(line_words, fps):
    """[(frame, prefix_len)] for one line: each word's characters spread evenly over its sung
    time (the first on the word's start); the space before a word arrives with its first char."""
    text, events = "", []
    for i, w in enumerate(line_words):
        word = display(w.text)
        lead = "" if i == 0 else " "
        n = len(word)
        for k in range(n):
            t = w.start + (w.end - w.start) * k / n
            text += (lead if k == 0 else "") + word[k]
            events.append((round(t * fps) + 1, len(text)))
    # several characters landing on one frame: keep the longest prefix for that frame
    out = {}
    for f, n in events:
        out[f] = max(n, out.get(f, 0))
    return text, sorted(out.items())


def wrap(text, row_chars):
    """Balanced wrap: the fewest rows of ≤ row_chars (word boundaries), split so the longest row
    is as short as possible → [(start, end)] char ranges (the space between rows belongs to
    neither). A single word longer than row_chars gets a row of its own."""
    words, i = [], 0
    for wd in text.split(" "):
        words.append((i, i + len(wd)))
        i += len(wd) + 1
    n = len(words)

    def best(k):                  # min over splits into k rows of the longest row; with breaks
        memo = {}

        def go(start, rows_left):
            if (start, rows_left) in memo:
                return memo[(start, rows_left)]
            if rows_left == 1:
                r = (words[-1][1] - words[start][0], [])
            else:
                r = (float("inf"), [])
                for end in range(start + 1, n - rows_left + 2):
                    width = words[end - 1][1] - words[start][0]
                    rest, brk = go(end, rows_left - 1)
                    cand = max(width, rest)
                    if cand < r[0]:
                        r = (cand, [end] + brk)
            memo[(start, rows_left)] = r
            return r
        return go(0, k)

    for k in range(1, n + 1):
        width, breaks = best(k)
        if width <= row_chars or k == n:
            break
    cuts = [0] + breaks + [n]
    return [(words[a][0], words[b - 1][1]) for a, b in zip(cuts, cuts[1:])]


def schedule(lines, fps, section_last, row_chars):
    """Pure: per line, its rows and every visible row-prefix with its frame span. A line is
    erased when the next starts typing; earlier rows stay complete while later rows type."""
    out = []
    for li, ws in enumerate(lines):
        text, ev = type_events(ws, fps)
        end_line = (type_events(lines[li + 1], fps)[1][0][0] - 1 if li + 1 < len(lines)
                    else section_last)
        rows = []
        for a, b in wrap(text, row_chars):
            spans = []
            for k, (f, n) in enumerate(ev):
                shown = text[a:min(max(n, a), b)]
                last = min(ev[k + 1][0] - 1 if k + 1 < len(ev) else end_line, end_line)
                if not shown.strip() or last < f:
                    continue
                if spans and spans[-1]["text"] == shown and spans[-1]["last"] == f - 1:
                    spans[-1]["last"] = last              # unchanged row: extend its span
                else:
                    spans.append({"text": shown, "first": f, "last": last})
            rows.append({"text": text[a:b], "spans": spans})
        out.append({"text": text, "rows": rows})
    return out


def plan(ctx):
    p = _p(ctx)
    sec = ctx.section
    t0, t1 = ctx.time(sec.first), ctx.time(sec.last + 1) - p["end_margin"]
    lines = lines_in(ctx.lyrics.words, t0, t1)
    return {"params": p, "lines": schedule(lines, ctx.fps, sec.last, p["row_chars"])}


def exit_state(ctx, plan):
    return ctx.enter.with_(background=plan["params"]["paper"], image="", mode="blank")


def build(ctx, plan):
    import bpy
    from songs.nothing import build as B
    p = plan["params"]
    fw, _ = ctx.frame_size
    B.set_background(p["paper"])
    mat, _ = B.emission_material("typed_ink", p["ink"])
    from songs.nothing import fonts
    medium = bpy.data.fonts.load(str(fonts.face_path()))

    def text(*a, **kw):
        obj = B.text_object(*a, **kw)
        obj.data.font = medium
        return obj

    # one global size; shrink only if the widest row would exceed max_width
    size = p["size"]
    rows = [r for ln in plan["lines"] for r in ln["rows"]]
    widths = {}
    for r in rows:
        probe = text("probe", r["text"], size, mat)
        widths[r["text"]] = B.text_width(probe)
        bpy.data.objects.remove(probe)
    widest = max(widths.values(), default=0)
    if widest > p["max_width"] * fw:
        k = p["max_width"] * fw / widest
        size *= k
        widths = {t: w * k for t, w in widths.items()}
    for li, ln in enumerate(plan["lines"]):
        n = len(ln["rows"])
        for ri, r in enumerate(ln["rows"]):
            y = (n - 1 - 2 * ri) / 2 * p["leading"] * size        # rows centred around y=0
            for si, sp in enumerate(r["spans"]):
                obj = text(f"typed_{li}_{ri}_{si}", sp["text"], size, mat,
                                    x=-widths[r["text"]] / 2, y=y, align_x="LEFT")
                B.show_between(obj, sp["first"], sp["last"])
