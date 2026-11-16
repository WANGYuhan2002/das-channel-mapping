# Slack: finding it, proving it is a coil, putting it on the road

Installers leave extra fibre: reels next to the interrogator, coils in manholes and pull boxes, loops at road
crossings. Spread evenly, it is harmless; concentrated in a coil and spread anyway, it shifts every channel of
the segment along the road. Three independent lines of evidence, each answering a different question:

| Evidence | Question it answers | Tool |
|---|---|---|
| extra fibre per segment (hammer anchors + path) | *how much* slack between two anchors | `build_channel_map.py` → `excess_m` |
| earthquake coupling | *which channels* do not follow the ground | `quake_coupling.py` |
| vehicles | is it a coil *at one point* or a stretch; *where* on the road | `vehicle_coil.py` |
| hammer stacks | loops next to a shot point; coils at a shot point | `hammer_anchor.py stack` |

## 1. Extra fibre per segment

`excess_m = fibre − path` for every pair of anchors. A few metres either way is pick + GPS + path error.
Kefalonia: 37 of 42 land segments had −10 … +22 m; 5 had +36, +44, +42, +149 and +146 m. Those five are the
slack candidates; the rest is spread evenly.

## 2. Earthquakes: which channels are not coupled

Regional events (Kefalonia: 8 catalogue events, ML 2.85–4.05, 9–38 km away, from three directions) reach a few-km
array almost equally (distance effects ≲ 1.3×). Per event: 2–20 Hz, no common-mode removal; SNR = RMS(+2…+45 s) /
RMS(−28…−1 s); medians over events. A channel is weak below 0.2× the median of its non-weak neighbours within
±30; runs of ≥ 2 (one-channel gaps bridged); per run signal and noise relative to the neighbours.

- **weak coupling** = signal < 0.2×, noise normal (< 2×): fibre not following the ground. Kefalonia: the five
  candidate segments each held exactly one weak run, about as long as the extra fibre (41 m for +36, 33 for +44,
  25 for +42, 155 for +149, 131 for +146 m); the other 37 segments none. These segments are 17.7 % of the land
  channels, so the chance that five runs land in them at random is 0.177⁵ ≈ 2 × 10⁻⁴ (`slack_match`).
- **noisy** = noise ≥ 2×: a noise source, not coupling (Kefalonia: one run next to a road works).
- Signal 0.02–0.12× rather than 0: coils touch the manhole floor a little. Only fibre inside the interrogator is
  truly silent (0.01×): a useful reference.
- Rule out the alternatives in the report: noise (normal), direction (weak for every back-azimuth), site
  (edges change 10–40× within 1–2 channels; site effects are hundreds of m and 2–3×), optics (would raise
  the noise), common-mode removal (not done), distance (≤ 1.3×).
- A weak run is not automatically a coil: on Kefalonia–Ithaca the 17 weak channels right after the far
  beach turned out (from vehicles) to be fibre laid along a detour, not coiled.

## 3. Vehicles: coil at one point, and where

**Coil or stretch?** Cars cross the run without delay if it is a coil: road channels in the run = (t(b+1) −
t(a−1)) / (s per channel) − 1 ≈ 0 for a coil, ≈ n for a stretch along the road. Two estimators:
`vehicle_coil.py ridge` on cross-correlations stacked over many hours (Kefalonia: 1423 h; the five runs gave
0.9–1.4 road channels, controls of the same length 3–24 ≈ n) and `cars` on single tracked cars (Kefalonia:
62 259 cars after the selection the user approved; medians −0.2 … 1.0). At junctions a tracker may join two
cars; drop crossings with ≥ n/2 road channels. Every channel of a coil lights up at the moment the car passes.

**Where on the road?** Per car, assume constant speed between the segment's two anchors and map the
light-up moment onto the road between them; medians per direction; the mean of the two directions cancels a
time offset common to both; half their difference (Kefalonia 0.7–2.3 m) plus a shared speed bias on straight
road (3–4 m) gives ~±4 m; larger near corners and junctions where everybody brakes. Write it as
`at_fraction` = position / segment road length, so it survives small changes of the path.

**Small coils the earthquakes miss.** Per-channel car positions can show two or three channels at the same
point of the road while their neighbours are a full channel away (Kefalonia: c 705–707, 16 m of fibre, in a
segment with +22 m extra; the earthquakes saw them only at 0.24–0.52×, too little for a weak run). Weaker
evidence: present it as such and let the user decide.

**What vehicles must not do**: move ordinary channels. Constant speed between anchors fails at corners and
junctions by 10–30 m at segment scale (22 % of neighbouring channel pairs in the Kefalonia test came out with a
ground spacing longer than the fibre — physically impossible). Use vehicles for block points only.

## 4. From evidence to the map

| Situation | In the map |
|---|---|
| extra fibre, no weak run, no vehicle signature | spread evenly (`excess_rest_m`), uncertainty grows with it |
| weak run + extra fibre, vehicles: one point | block at the weak-run channels, point from the vehicles (`placed_by = vehicles`) |
| weak run, no vehicles | block at the weak-run channels, point where the rest is uniform; larger uncertainty |
| coil at a shot point (all channels light at once) | `point` piece at the shot point (`beach_coil`) |
| stored reel at the interrogator | `line` piece interrogator → first anchor (the cabin) |
| weak run without extra fibre | not slack: loose or detoured fibre; keep it on the path, note it |

Writing a block in, moving one, or changing its edges is the user's decision: show the evidence figure (raw
waterfall around the run, the earthquake profile, a car crossing, the 60-day statistic) and the fibre − road
before / after the block, then rebuild and report the per-channel moves.
