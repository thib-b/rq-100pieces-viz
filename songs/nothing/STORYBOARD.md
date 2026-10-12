# Nothing — storyboard

Three scenes, with sections inside them. Every time below is measured from the master (the
grid and cues live in `cues.toml`; section starts in `song.toml`).

**Grid:**
- Click-locked at 154 bpm on the 8th-note grid. The felt tempo is **77 bpm**: a beat is 0.7793 s and a bar is 3.117 s.
- The kick is on beats 1 and 3, the snare on 2 and 4.
- Bar downbeats fall at 12.0555 + n·3.117 s and hold within ±15 ms through 5:02.

**Plate (`plates/nothing.jpg`):**
- The dish radius is 0.291 of the photo's side, and the agar is deep navy #06142b, almost black.
- Four large white puffs sit in a cluster on the lower left. The largest is at (-0.35, -0.08) dish radii (image axes, y down), r ≈ 0.34.
- A large lavender ring colony is at the top right.
- A white starburst tuft and a few ochre and green dots complete the main growths.

## Scene 1 — The song (0:00 → 2:20.636)

| Time | Section | Picture |
|---|---|---|
| 0:00 | exposition | The plate photo, centred. |
| 0:10.50 → 1:39.335 | exposition, first_bridge | **Ratchet:** 15° clockwise per 2-beat step, landing on every kick (beats 1 and 3). Each step eases in, then a ~1° mechanical overshoot settles within a 16th. 57 steps = 855°. |
| 0:00 → 1:34.66 | exposition, first_bridge | **Creeping zoom**, almost imperceptible: the dish grows from 70% to 92% of the frame height and stays fully on screen. |
| 0:09.85 → ~1:32 | exposition, first_bridge | **Verse 1 lyrics** in the side columns (Haha filament language), dissolving slower and more organically. They stay upright while the plate rotates. |
| 1:34.66 → 1:39.335 | first_bridge | **The fall:** an accelerating zoom into the largest white puff, tracked through the rotation. It falls through the 2-beat band stop (1:37.00–1:38.55) and stops dead on the downbeat, deep inside the puff. That view of the photo stays on as **the paper**: the "white" of everything until the bridge is the plate's own grain, breathing very slowly (≤4% zoom and a slight drift per 4 bars, from rest at the landing). |
| 1:39.335 → 2:07.73 | verse2 | **Typed lyrics:** Helvetica Neue Bold, ALL CAPS (as every word in the film), pure black on the paper, centred, two-row lines set close together, one line at a time, character by character over each word's sung time. A line is erased when the next starts. |
| 2:07.73 | nothing2 | **NOTHING** typed in capitals, centred, pure black on the paper. |
| 2:08.51 → 2:16.31 | nothing2 | **11 negative flips** (the paper's exact negative, text pure white), one per sung "Nothing", each on the "&" (50 ms ahead of the grid, as sung). |
| 2:17.13 → 2:17.55 | claps | **Hold**: the music stops, and so does the picture. |
| 2:17.55 → 2:20.57 | claps | **One flip per hand clap**, 27 of them, as detected on the separated stem: sparse at first, accelerating into continuous 32nds, each within a frame of its clap. The background keeps alternating paper and negative, and only the **text** fades a step more transparent on each flip. The last flip lands on the paper with the text gone, and the bridge carries straight on on that paper as the **bass and kick come in at 2:20.636**. |

## Scene 2 — The bridge (2:20.636 → 2:58.1)
**Black slime mould** (`slime_cover`). On the paper, black filaments grow up from the bottom edge like Physarum foraging: they wander, branch more and more, steer away from explored ground and thicken into a network. Nothing is drawn hard-edged: filaments fade out across their width with a noisy, blurred edge and taper to points as they grow; the moulds have wide, ragged, blurred rims. The front is ragged: each filament has its own speed and lead, and the roots start at staggered times. The takeover accelerates through the bridge. Lobed black concentric moulds (solid, with faint growth rings) slowly swell out of the gaps the network leaves, each over 3.5–8 s. In the last 3 s a few of them balloon, accelerating, until each alone covers the frame, so the release lands on **#000000** with no fade. Black is the only fact scene 3 inherits.

## Scene 3 — The outro (2:58.1 → end)

| Time | Section | Picture |
|---|---|---|
| 2:58.1 → 3:22.97 | sleepy_piano | **The plate regrows on black** (`plate_colonies`), with growths at their real places, sizes and colours (`plates/nothing_colonies.json`, 17 colonies, 1,600 blooms). Each piano phrase (2:58.2, 3:03.5, 3:07.4, 3:09.4, 3:15.6, 3:19.9, 3:22.2) sets the next colonies growing, largest first; each colony spreads outward from its centre, every bloom swelling in over 4 s. The last phrases' blooms are still growing at the bass entry; the zoom's first plate is the same plate and finishes growing them (`colonies.growth`). |
| 3:22.97 → | outro_bass | **The Droste plate** (`droste_zoom`): a miniature plate grows inside the largest white puff: first its navy dish, then its organisms one by one (largest colonies first, each spreading from its centre). Every nested plate grows the same way, at a steady rate over the whole level it takes the camera to reach it (evenly spaced thresholds), so new blooms appear at an even pace. Two ancestor plates are kept behind the current one: the off-centre view sees past the parent's dish near the end of each level. The camera then falls towards the nesting's fixed point, one level (k = 3.6×) per 2 bars, endlessly and seamlessly. It rhymes with scene 1's single fall into the same puff. |
| 4:12.06 → | strings_outro | **Log-spiral + clockwise roll:** each nested plate turns up to 24° relative to its parent (zoom then reads as rotation), and the whole screen rolls clockwise (7°/s), both easing in. |
| 5:02.85 → end | end_resonance | The zoom carries on while fading to black over 5 s. |

**Outro lyrics:**
- **Which lines:** only the lyric sheet's closing lines, once each: "The definitive version – the ideal." and "The wonderful image – It's finally real." (3:49–4:04), then "What does a promise mean?" (4:38) and "Nothing." (4:49). The sung repeats are not shown.
- **Where:** the same side columns as verse 1, fixed on screen either side of the zoom centre.
- **Look:** light lavender-white and translucent. The words fade in as they trace, then simply fade away in place.
