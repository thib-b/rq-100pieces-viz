"""Nothing — section-based, deterministic render pipeline.

The song is a list of sections (song.toml). Each section owns a disjoint range of global frames,
draws its randomness from its own seed, and hands a `State` to the next section, so any one
section can be re-rendered on its own. See README "Nothing" for the workflow.
"""
