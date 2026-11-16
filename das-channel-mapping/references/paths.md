# Paths: where the cable runs between anchors

Anchors say where some channels are; the path says what the cable does in between. Use each source for
what it is good at, and record which one every channel came from (`path_source`).

| Source | Good at | Weak at |
|---|---|---|
| anchor GPS points | position (~2–5 m), which side of the road | nothing in between |
| OpenStreetMap roads | road geometry, vertices every few m | which road the cable takes; road width / side |
| operator / as-built route (georeferenced drawing or screenshot) | which road, the submarine route | smoothed over tens of m, georeferencing error (~5–10 m), drawn loops rarely shown |
| hand-drawn route (user traces it on imagery) | stretches nothing else covers (landings, private ground, the far end) | only as good as the imagery; no channel information |
| straight line | nothing — only a fallback | cuts every corner |

**Priority**: a route the user traced by hand for a stretch beats automatic traces for that stretch (the
user knows the ground); keep its shape and let the data decide only where along it the channels sit.

## 1. Land between hammer anchors (`road_path.py`)

1. Snap both anchors to the OSM network (each may join any way within nearest + 5 m — at junctions two roads are
   about equally close) and take the shortest leg + road + leg, first on drivable roads, then on all ways.
2. **Shift the road sideways through both anchor points**: the signed offset (+ = left of the direction of
   travel) changes linearly with arc length from the first anchor's offset to the second's. Anchors on opposite
   sides mean the fibre crosses the road in between; the crossing point is then a guess (linear).
3. Choose per segment:
   - where the reference route covers the segment (both anchors within 20 m of its vertices): OSM if it stays
     within 25 m of the reference both ways (Hausdorff = same road), else the reference route shifted the same way;
   - elsewhere: OSM if both anchors are within 20 m of it and it is not > 25 m longer than the fibre (pick and
     GPS errors at both ends), unless it is > 15 m longer while the straight line matches the fibre within 10 m
     (the cable takes a shortcut); else the straight line.
4. Report per segment: fibre, straight line, OSM and reference lengths, snap distances, offsets, the choice and
   fibre − path. Segments with much more fibre than path are slack candidates (slack.md); segments with
   *less* fibre than path (beyond ~10 m) mean a wrong road, a wrong anchor or a shortcut — check them.

**Check** (validation.md): on the segments the reference covers, place channels uniformly along both paths and
compare (Kefalonia: OSM vs operator route through the same anchors, median 4 m, p90 14 m, max 23 m, strike 4°;
straight lines would give 11 / 77 / 112 m and 10°).

Credit OSM (© OpenStreetMap contributors, ODbL) on every figure and in the delivery README.

## 2. Submarine part

- Take the operator route between the two landings and **stretch it between the two waterline channels**
  found from the waves: channels uniform in channel along the route (`path` piece with `ends` = the two
  waterline channels). The extra fibre (Kefalonia: 6857.7 m for 6723.2 m of route, 2.0 %) is spread evenly; say so.
- Keep the alternative the operator's numbers imply (e.g. "anchored" at one shore with the nominal slack) as
  extra columns, so users can see how much the choice matters.
- If a hand-drawn approach exists at one landing, cut the operator route where it meets the drawing and follow
  the drawing to the hand-marked water exit (record the junction gap); then stretch over the spliced route.
- AIS ship crossings test the along-cable position of the whole submarine part (validation.md).

## 3. A stretch no data tie to the map (far end, private ground)

Use the hand-drawn route and place channels with the fibre/path ratio measured on the anchored land
(`ratio` piece). Keep the whole drawn shape (detours, hairpins) unless the data say otherwise: Kefalonia–Ithaca
showed that cutting the drawn detours to make the record end at the telecom node was impossible (the road part
would have held less fibre than the straight line), while the full drawing placed at the Kefalonia ratio put
the vehicle features within 3 channels of where they are seen (validation.md §5). State plainly in the
delivery that this part is an inference, and where the record is believed to end.

## 4. Short pieces

- **interrogator → first anchor** ("cabin"): often a stored reel next to the unit (Kefalonia: 145 m of fibre on
  a 10.5 m straight line); place on the straight line, uniform, uncertainty ~15 m, no strike.
- **manhole coil → waterline** ("beach"): straight line from the manhole (shot point) to the water entry.
