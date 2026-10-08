"""hold — a still frame: a background colour, optionally an image centred on it.

Placeholder style used to stand up the pipeline before the real sections are designed.
params:
  background  "#rrggbb"  (default: inherited state's background)
  image       path to show centred, or "" for none (default: inherited state's image)
  height_frac image height as a fraction of the frame height (default 1.0)
"""
from songs.nothing.timeline import asset


def plan(ctx):
    return {
        "background": ctx.param("background", default="#000000"),
        "image": ctx.param("image", default=""),
        "height_frac": float(ctx.param("height_frac", "image_height_frac", 1.0)),
    }


def exit_state(ctx, plan):
    return ctx.enter.with_(background=plan["background"], image=plan["image"],
                           image_height_frac=plan["height_frac"])


def assets(ctx):
    img = plan(ctx)["image"]
    return [asset(img)] if img else []


def build(ctx, plan):
    from songs.nothing import build as B
    B.set_background(plan["background"])
    if plan["image"]:
        _, fh = ctx.frame_size
        B.image_plane("hold_image", asset(plan["image"]), height=fh * plan["height_frac"])
