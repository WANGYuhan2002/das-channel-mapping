# Independent checks

A check counts only if its data did not go into building the map. Run them after every rebuild that touches
the parts they test, and put the numbers in the delivery report.

## 1. Anchor GPS against the reference route (`validate_map.py gps`)

Distance of every shot point inside the reference drawing to the drawn line. Small distances (Kefalonia: 21
shots, median 6.7 m, 0.5–14 m) check both the georeferencing of the drawing and that the cable runs where it
says. Points at the edge of the drawing, where the line is cut, are not evidence.

## 2. Two path shapes through the same anchors (`road_path.py --report`)

On the segments the reference route covers, channels placed uniformly along the chosen OSM path vs along the
reference route, both shifted through the same anchors (Kefalonia, 11 segments / 276 channels: median 4 m, p90
14 m, max 23 m, strike 4°; straight lines instead: 11 / 77 / 112 m, 10°). This is the size of the path-shape
error and the basis of `road_m`.

## 3. AIS ship crossings (`validate_map.py ais`)

Pair DAS ship passages (the channel where a passing ship is loudest / where its signature crosses) with AIS
vessels (length ≥ 50 m, |Δt| ≤ 15 min). Cross each AIS chord (two consecutive hourly positions on either side of
the cable) with the mapped submarine polyline and subtract the DAS label: the median tests the along-cable
position of the submarine part. Kefalonia: 43 crossings, old map −279 m (90 % −425 … −224), final map −7 m
(−146 … +26). The scatter (~300 m with hourly AIS positions) is AIS, not the map; the test only covers the
stretch where big ships cross. Earlier notes of a "systematic AIS offset" may simply be an old map.

## 4. Hammer travel times (`hammer_anchor.py stack --map --gps`, `validate_map.py moveout`)

Inside each footprint, the onset delay vs the map distance from the shot point, with a speed fitted per shot:
residual median 8.6 m, p90 26.2 m (368 channels) on Kefalonia. Timing (±2.5 ms per blow) limits this to ~10 m, so
it is supporting evidence; it got better when a block was moved to the vehicle point.

## 5. Vehicles on an unanchored stretch

Where the far end was placed by a ratio along a drawn route, cars can still test it: channels that hear the
cars at the same time as the road end, channels that never hear them (a detour off the road), channels passed
all at once (a hairpin), and the time per channel along the road. Compare the feature channels with where the
placement puts the drawn features (Kefalonia–Ithaca: the V start, tip and end and the first hairpin all within
3 channels, max 2.2, with no tuning). A line through the features (here ratio 0.984 vs 1.026) shows how
sensitive the placement is. This supports the placement; it is not an anchor.

## 6. Do not over-read

- AIS checks the sea part only, the GPS check the drawing only, the moveout only ~10 m.
- A check made against an older version of the map is stale: rerun it after a rebuild (Kefalonia: −29 m on an
  intermediate submarine route, −7 m on the final one).
