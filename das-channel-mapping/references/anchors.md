# Anchors: where the data pin a channel to a point on the ground

An anchor is a (fractional) channel with a known position. Everything between anchors is interpolation, so
spend the effort here. Two kinds were used: hammer / tap-test shots on land and the waterlines from ocean-wave
loading at the landings. Hand-drawn or GPS'ed features (a manhole, a building) can also serve when the data show
the channel that sits there.

## 1. Hammer / tap test

**Field side**: shots every 100–200 m along the land route, several blows per shot, GPS of every shot point,
logged time and (optionally) the along-fibre distance the crew read off the waterfall. Shots right next to
known features (manholes, turns, both ends of a suspected coil) are worth extra.

**Find the blows** (`hammer_anchor.py detect`, on a continuous high-frequency envelope, e.g. 30–180 Hz RMS in
0.05 s bins): ratio to the per-channel median of the whole test; keep impulsive bins only (envelope above
its own level 0.3–1.0 s before and after: blows are impulsive, vehicles change over seconds); peaks ≥ 8×;
peak channel refined by a parabola. A shot point is a **stationary** sequence of blows (within 1 channel, 40 s),
scored by strength × impulsiveness × closeness to the logged time; footsteps are impulsive too but drift.
Report the runner-up group > 3 channels away and its score ratio: a close second means ambiguity.

**Stack** (`hammer_anchor.py stack`, blow windows [−1, +1.5] s at the raw rate, common mode removed):
15–150 Hz envelope / pre-blow median = SNR; align every blow on its onset at the anchor channel (30 % of the
peak) and refine by cross-correlating log envelopes (±30 ms); drop blows < 0.3× the strongest (weak blows,
footsteps); geometric-mean stack. Then read:

| Output | Meaning | Kefalonia |
|---|---|---|
| anchor channel | peak of the stack / median of the blows' peak channels | scatter between blows 0.12 channel (~1 m) |
| footprint | contiguous channels with stack SNR ≥ 6 | ±4.5 channels (±37 m); strength falls 10× per 24 m |
| near range, centroid | contiguous ≥ 0.25× the anchor | wide range with the pick at one end → revisit the anchor |
| secondary maximum | ≥ 0.25×, separated by a dip | the fibre comes back near the shot point: a loop |
| simultaneous channels | outside the footprint, SNR ≥ 6, delay ≤ 25 ms | fibre lying at the shot point though far along the fibre: a coil |
| onset moveout | delay vs map distance | 0.6–3 km/s; ±2.5 ms per blow → only ~10 m: a check, never a placement tool |

**Special cases** (all seen in the Kefalonia test; each changed the map only after the user agreed):

- *Two shots on the same channel* (picks < 0.5 channel apart, GPS a few m apart): merge into one anchor at the
  mean channel and mean GPS point (`merge_within_cols`).
- *Wide strong response with the pick at one end* while one neighbouring segment has less fibre than road and
  the other more: move the anchor to the channel that gives both neighbours the same fibre/path ratio
  (`hammer_anchor.equal_ratio_column`), accepted only if it lies inside the strong response (Kefalonia: two
  anchors, by 2.8 and 1.8 channels; budgets −21/+24 m → +2/+2 m). Record pick and fix (`anchor_fix`).
- *A secondary maximum a few channels away*: a small loop next to the shot point.
- *Channels between two close shots that neither shot sees* although the fibre between them is long: a coil
  that is badly coupled (confirm with earthquakes, see slack.md).
- *Every channel of a run lights up at once*: a coil at the shot point (Kefalonia: 21 channels, 172 m of fibre in
  the beach manhole; the shots at the two ends of the coil were logged at the same GPS point).

**What the hammer cannot do**: measure coupling. Blow strength depends on distance and on how hard the fibre
at the shot point is shaken — a blow on the lid of a manhole shakes the coil inside. Use earthquakes for
coupling. Background noise before the blows sits at the instrument floor on a quiet land cable, so it cannot
tell coupled from loose fibre either.

**Statistics to report**: convention test (conventions.md §2); anchor scatter; footprint half-width; GPS
distance of the shot points to the reference route and to the OSM road centreline (Kefalonia: median 6.7 m to
the operator route, 2.9 m to the OSM centreline: the GPS points are accurate and say which side of the road the
fibre is on); fibre − path per segment (segments with ≥ 30 m extra fibre are slack candidates).

## 2. Waterlines from ocean-wave loading

Wave pressure only acts on submerged fibre and is strongest in the surf zone. Average PSDs over storm hours and
calm hours (e.g. 24 storm + 8 calm hours) and look at storm − calm in the swell (0.07–0.15 Hz) and wind-sea
(0.18–0.35 Hz) bands along the cable (`waterline_waves.py`):

- **one-channel step**: the largest drop of storm wave power between two adjacent channels in a window, at the
  finest channel spacing you have (RAW 8 m rather than a 16 m product). Kefalonia–Ithaca: −14.1 dB between
  c 1766 and 1767 = the Ithaca waterline at c 1766.5; a second step of −24.2 dB at c 1775.5 = where the cable
  leaves the beach (the plateau between, 73.5 m of fibre, carries +22 dB of wind-sea power and correlates with
  the sea state at r 0.50).
- **half-rise**: half way (in dB) from the land level to the near-shore peak, also 25 / 75 %, bootstrapped over
  days: definition-dependent (Kefalonia: 7194 / 7197 m for swell / wind sea, 95 % 7189–7200 m; sensitivity
  range 7138–7261 m).
- Lines that bound the shore from the land side (where sea-state-coherent noise stops) and from the sea side
  (the surf peak) are limits, not the waterline.
- Cross-check with a hammer shot near the shore: fibre from the coil end to the waterline vs the straight line
  from the shot point to the mapped water entry (Kefalonia: 49.6 m of fibre for 40.7 m, ratio 1.22 on a beach).

Choose the land band, peak band and step windows by looking at the profiles with the user (visual picks).

## 3. Write down every anchor

`anchors.csv`: `name, col, lat, lon` (+ `col_pick`, notes). Keep the hammer picks file, the stack table and the
convention test with the delivery: they are the evidence behind every land position.
