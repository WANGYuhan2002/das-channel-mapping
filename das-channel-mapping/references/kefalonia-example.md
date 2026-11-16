# Worked example: the Kefalonia–Ithaca seafloor DAS cable (2024)

The method in this skill was built on this cable. The numbers below are the real ones from that work (no
coordinates and no data are included). Use them as a scale for what to expect, not as defaults.

## The cable and the recording

- Interrogator in a cabin in northern Kefalonia; land route down a road to a beach manhole; ~6.7 km of submarine
  cable across the strait; landing on a beach on Ithaca; a road up to a telecom node.
- RAW 400 Hz, 1872 channels, true spacing 8 m × 1.020952 = 8.16762 m (header multiplier); SORTED product 80 Hz,
  936 channels of 16.335 m, channel j centred on raw channel 2j.
- True fibre distance = −207.208 + 8.16762 c m (header start distance + c × spacing); the label used by the
  projects was FO_nom = −215 + 8 c. The two differ by 7.8 + 0.168 c m: 159 m at the beach, 304 m at the far shore.

## Segments of the final map

| Segment | Raw channels | Fibre / ground (m) | Positioned by | Checked by | Uncertainty |
|---|---|---|---|---|---|
| internal | 0–24 | 204 / — | interrogator GPS (header) | header start locus −25 | — |
| cabin | 25–42 | 145 / 10.5 | straight line interrogator → shot #1; reel next to the unit | #1 blows lit c 34–40 at once; earthquakes weak at c 40–41 | 15 m |
| land | 43–899 | 7000 / 6434 | 43 hammer anchors; OSM road shape shifted through the shots (41 segments), operator route (1); 6 slack blocks at points set by vehicles | GPS to operator route 7 m; OSM vs operator route 4 m median; earthquakes + vehicles confirm 5 coils | 5.1–14.4 m (median 7.5) |
| coil | 900–920 | 172 / 0 | all 21 channels at the manhole shot point | #33 blows arrive at once on c 900–922; earthquakes 0.02× | 15 m |
| beach | 921–926 | 49.6 / 40.7 | straight line manhole → water entry (waterline c 926.9) | wave half-rise 7194 / 7197 m | 15 m |
| sea | 927–1766 | 6858 / 6723 | operator route stretched between the two waterlines; 2.0 % slack spread | AIS bias −279 m (old map) → −7 m | 30 m |
| far land | 1767–1871 | 854 / 832 | user's hand-drawn route, Kefalonia fibre/road ratio 1.026 from the waterline ("placement K") | vehicle features within 3 channels of K | 15 m beach / 60 m inland |

## Anchors

- **Hammer test**: 45 shot points, 524 blows over 3.3 h; 43 land anchors (two shots on the same channel merged;
  one shot sat at the far end of the beach coil). Footprint ±4.5 channels (±37 m), peak falling 10× per 24 m;
  anchor scatter between blows 0.12 channel. Onset speeds 0.6–3 km/s, ±2.5 ms per blow.
- **Convention test**: 44 / 45 picks within ±21 m of the logged distance read as the header distance (median
  −3.9 m, MAD 4.0 m); read as the nominal label the error grew to −170 m at the beach. The outlier (+164 m) was
  the coil: two shots logged at the same point landed at the two ends of the 172 m coil.
- **Anchor fixes** after stacking all blows: two anchors with a wide strong response and the pick at one end
  moved to the equal-ratio channel (140.4 → 143.2 and 531.3 → 533.1); the fibre − path of their neighbours went
  from −21 / +24 m to +2 / +2 m and from −11 / +20 m to +4 / +5 m.
- **Waterlines**: Kefalonia FO_nom 7.20 km (c 926.9) from 60 days of swell / wind-sea half-rise (7194 / 7197 m,
  95 % 7189–7200 m), confirmed by the hammer (49.6 m of fibre from the coil end vs 40.7 m straight line from the
  manhole to the water entry). Ithaca on RAW 8 m channels (24 storm + 8 calm hours): one-channel step of −14.1 dB
  at c 1766.5 (waterline) and −24.2 dB at c 1775.5 (end of the beach; plateau of 73.5 m with +22 dB wind sea,
  sea-state correlation 0.50). The earlier 16 m half-rise had put the shore at c 1770.6.

## Paths

- Land: OSM road (Overpass, ~340 ways) shortest path between consecutive shots, shifted through both shot points;
  41 OSM segments, 1 operator-route segment (OSM took another road), 0 straight lines. Shots lie a median 2.9 m from
  the OSM centreline. OSM vs operator route through the same shots: median 4 m, p90 14 m, max 23 m (straight lines:
  11 / 77 / 112 m).
- Sea: the operator's submarine route (georeferenced screenshot), the last stretch before Ithaca replaced by the
  user's hand-drawn approach, stretched between c 926.875 and c 1766.5: 6857.7 m of fibre on 6723.2 m (2.0 %).
- Ithaca land: the user's hand-drawn route (92 vertices, 1137 m to the node: a shore strip, a V-shaped detour and
  two hairpins). Automatic traces near the landing were poor; the user: the hand-picked route is the most accurate.

## Slack: seven blocks in the map

| Block | Channels | Fibre | Segment, point | Evidence | Uncertainty |
|---|---|---|---|---|---|
| quake_coil | 246–250 | 41 m | #14→#15, 68.1 m after #14 (uniform rest: 64.7) | +36 m extra; earthquakes 0.05×; road channels 1.4 (stack), 0.22 / −0.20 (single cars) | 10 m |
| loop | 503–506 | 33 m | 5.1 m before #26 | #26 stack: second peak; earthquakes 0.05×; 1.3 / 1.4 | 10 m |
| loop | 681–683 | 25 m | 13.8 m after #32 | #32 stack: second peak (0.47×); earthquakes 0.06×; cars cross without delay | 10 m |
| car_coil | 705–707 | 16 m | 122.1 m after #45 | found by cars (three channels within 1.4 m of road, neighbours a channel away); +22 m extra; earthquakes only 0.24–0.52× | 10 m |
| quake_coil | 750–768 | 155 m | #43→#42, 115.1 m after #43 (uniform rest: 109.5) | +149 m extra; earthquakes 0.06×; 0.9 (stack); all coil channels light at once as a car passes | 10 m |
| unseen | 844–859 | 131 m | 1.2 m before #37 | neither #37 nor #38 (32 m apart) sees these channels; earthquakes 0.11× | 10 m |
| beach_coil | 900–920 | 172 m | manhole shot point | all channels hit at once by the blows; earthquakes 0.02× | 15 m |

Plus ~145 m stored next to the interrogator (cabin). Segments without a block: fibre − path −10 … +19 m, spread.
Fibre − road before / after each block: −6.2 / +1.4, +10.2 / +1.0, +1.7 / +16.1, +1.9 / +3.6, −9.5 / +3.3,
+16.3 / −1.2 m — the two negative "before" values (fibre shorter than road) are within the uncertainty and would
disappear with blocks pulled in by half a channel at each edge (left to the user).

## Earthquake coupling

8 catalogue events, ML 2.85–4.05, 9–38 km, from WSW, SW and S. SNR median: land 69, sea 467, far land 14. The 5
land segments with > 30 m extra fibre each hold exactly one weak run whose length matches the extra fibre; the
other 37 segments none (chance ≈ 2 × 10⁻⁴). Weak runs keep normal noise (0.8–1.0×); signal 0.02–0.12×; fibre
inside the interrogator 0.01×. One run next to a road was "noisy" (noise 6×). The 17 weak channels right after the
Ithaca beach are not a coil: the vehicles show them laid along the drawn V.

## Vehicles

60 days of 2–20 Hz envelope (0.2 s RMS, 5 Hz), log minus running median; 1423 h after dropping gaps.
- Stacked cross-correlations: road channels in the five weak runs 0.9–1.4 (coil at a point); five control
  stretches of the same length 3.1–24.4 (≈ n).
- Single cars: 409 068 tracks → 62 259 after the cut (≥ 30 channels followed, detection score ≥ 1.0, no car in the
  same direction within 20 s, no channel slower than 3 s, no earthquake); coil positions from the light-up moment,
  the two directions within 0.7–2.3 m; total ~±4 m on straight road.
- Not used for ordinary channels: braking at corners moves "constant-speed" positions by 10–30 m.
- Ithaca: cars followed over c 1801–1870 (~77 s end to end); no cars on c 1782–1792 (V); c 1849–1859 passed within
  ~3 s (first hairpin); placement K puts these features within 2.2 channels with no tuning.

## Checks

- AIS: 43 big-ship crossings, bias −279 m (old map) → −7 m (final), 90 % −146 … +26 m. An intermediate version
  of the submarine route gave −29 m: rerun checks after every rebuild.
- Hammer moveout residual: median 8.6 m, p90 26.2 m (368 channels).

## How the map evolved (why versions matter)

1. The old station list was interpolated with the wrong distance convention: land channels slid back along the
   road by up to 159 m, and the 172 m beach coil was spread over ~170 m of road. A 2 % spacing error happened to
   cancel the coil at the shoreline, which made the old map look right there.
2. New map from the hammer anchors, OSM paths, the stretched sea route and the hand-drawn Ithaca route.
3. Ithaca end: first assumed to end at the node (detours cut out, fibre/path 0.91); withdrawn when the user said
   the end is not known → placement K (median 137 m move on Ithaca land).
4. Two earthquake coils written at the vehicle points (37 channels moved > 10 m, max 55.9 m); three hammer blocks
   moved to the earthquake channels and the vehicle points (122 channels > 0.5 m, max 9.3 m); the small car coil
   written (23 channels, max 11.2 m). The Kefalonia ratio went 1.0354 → 1.0271 → 1.0284 → 1.0259 and the Ithaca
   channels moved with it (≤ 8 m). Each step: user decision → rebuild → per-channel change table → new version.
