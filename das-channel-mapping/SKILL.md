---
name: das-channel-mapping
description: >-
  Build, check and deliver a DAS channel map: every channel of a distributed acoustic sensing fibre placed at a
  latitude / longitude with a position uncertainty, for land, submarine or mixed cables. Covers anchors from
  hammer / tap tests and from the ocean-wave waterline; paths from OpenStreetMap roads, operator routes and
  hand-drawn routes; placement rules (uniform between anchors, slack coils at one point, the sea route stretched
  between waterlines, unanchored ends by the fibre/road ratio); finding slack with earthquakes and vehicles;
  uncertainty rules; independent checks (GPS, AIS ship crossings, hammer travel times); a versioned delivery
  (tables, data dictionary, GeoJSON / KML, md5). Trigger on "channel mapping", "map / georeference / locate the
  DAS channels", "tap test", "hammer test", "fibre slack", "coil", "cable route", "where is channel N", and on
  通道映射, 道位, 每道经纬度, 锤击试验, 敲击测试, 余缆, 盘缆, 光缆路由, 水线, 岸线, 光纤/道路比, 通道表.
---

# DAS channel mapping / 通道映射

A channel map is **anchors** (channels the data pin to a point on the ground) + **paths** between the anchors
+ **placement rules** along the paths, each channel with an **uncertainty** from simple rules, then **checks**
with data that did not go into the build, then a **versioned delivery**. Every step has a script in `scripts/`
(Python 3 with numpy, pandas, scipy; networkx for OSM; run any script with `--help`) and a reference in
`references/`. The method was developed on the Kefalonia–Ithaca seafloor cable; its real numbers are in
`references/kefalonia-example.md` as a scale for what to expect.

## Ground rules

1. **Originals are read-only.** Never edit raw data, earlier result folders, other people's tables or a
   manuscript; build new files and new versions.
2. **Conventions before positions** (`references/conventions.md`): true spacing (nominal × fibre-length
   multiplier), header distance vs nominal label, which one the field log used (test it), position = centre of
   the gauge, decimated products. Most map errors are convention errors that grow along the cable.
3. **Visual picks and map changes are the user's decisions**: analysis windows, land / peak bands, thresholds,
   which weak run is a coil, moving an anchor, writing a block into the map, block edges. Show the figure,
   propose with numbers, wait for a yes.
4. **A route the user drew by hand beats automatic traces** for its stretch. Keep its shape; the data decide
   only where along it the channels sit.
5. **Vehicles place slack blocks, never ordinary channels** (cars brake at corners: 10–30 m errors).
6. **Say what is inference.** Where nothing ties the cable to the map (e.g. the far end), place by the measured
   fibre/path ratio along the full route, write "not known" for the end of the record, give 60 m-class
   uncertainty. Never force an assumed end point.
7. **Every rebuild**: compare with the previous version (`--compare`), report how many channels moved and where,
   rerun the checks that depend on the changed part, deliver as a new version.
8. **Look at the data first**: raw waterfalls and spectra before calling something a coil or an artefact; one QC
   figure per step (overview → zoom on one case → statistics over the cable).

## Workflow

**0. Inventory** — ask for what is missing: raw recordings (rate, channel count, header start distance, spatial
sampling, fibre-length multiplier, gauge length, interrogator GPS), decimated products, the tap-test log (times,
GPS, logged distances), operator / as-built route drawings, OSM coverage of the land route, imagery the user can
trace on, a catalogue of regional earthquakes in the window, hours of traffic, AIS data for the sea part.

**1. Conventions** — `hammer_anchor.py conventions` on the first picks: the right convention leaves residuals that
do not grow with distance. List every earlier product built under a wrong convention.

**2. Anchors** (`references/anchors.md`)
- Tap test: `hammer_anchor.py detect` (stationary blow sequences in the high-frequency envelope) →
  `hammer_anchor.py stack` (anchor channel, footprint, near range, secondary maxima = loops, simultaneous channels =
  coils) → `anchors.csv` (`name, col, lat, lon`). Merge two shots on one channel; revisit anchors with a wide
  response (`equal_ratio_column`); every change with the user's agreement.
- Waterlines: `waterline_waves.py` on storm vs calm band power (swell, wind sea) along the cable at the finest
  spacing: one-channel steps (waterline, end of a beach) and half-rise as a range. Cross-check with a shot near the shore.

**3. Paths** (`references/paths.md`) — `road_path.py`: OSM shortest path between consecutive anchors, shifted
sideways through both anchor points; the operator route where OSM takes another road; straight lines only as a
fallback. Submarine: operator route stretched between the two waterline channels (splice in a hand-drawn approach
if there is one). Far end / private ground: the user's hand-drawn route.

**4. First build** (`references/placement.md`) — copy `assets/config_template.json`, fill the pieces (point,
line, path, anchored, ratio), run `build_channel_map.py config.json --out DIR`. Read `*_anchored_segments.csv`:
segments with much more fibre than path are slack candidates; fibre clearly *shorter* than path means a wrong
road, anchor or a shortcut.

**5. Slack** (`references/slack.md`)
- `quake_coupling.py`: weak-coupling runs (signal < 0.2× neighbours, noise normal) from 5–10 regional events in
  2–3 directions; `slack_match` tests whether they sit in the segments with extra fibre.
- `vehicle_coil.py ridge` (stacked correlations) and `cars` (single tracked cars): coil at one point (≈ 0 road
  channels) or a stretch (≈ n), and the block's point on the road (`at_fraction`, two-direction mean).
- With the user's go-ahead, write blocks into the config, rebuild with `--compare`, report the moves.

**6. Uncertainty** (`references/uncertainty.md`) — encoded in the config: road 5 m / straight 10 m + ½ ×
unexplained extra fibre per segment; vehicle-placed blocks 10 m; coils, cabin, beach 15 m; sea ~30 m; inferred
far end ~60 m.

**7. Checks** (`references/validation.md`) — `validate_map.py gps` (shot GPS vs reference route), the path-shape
check in the `road_path.py` report, `validate_map.py ais` (ship crossings vs the sea part, old vs new map),
`validate_map.py moveout` (hammer travel times), vehicle features on an unanchored stretch.

**8. Delivery** (`references/delivery.md`) — `make_delivery.py dictionary | slack | change | gis | manifest`, a
README that says which file for which data and what not to use any more, the method report, then
`upload_version.sh -n …` (dry run) and the real upload: one immutable version folder, md5 checked on the remote,
`current` moved last. Common traps: `references/pitfalls.md`.

## Scripts

| Script | Does | Main inputs → outputs |
|---|---|---|
| `cmap_geo.py` | local metric frame (WGS84 m/deg), polylines, crossings, strike | library |
| `hammer_anchor.py` | detect blows, stack shots, convention test, equal-ratio anchor | envelope / blow windows / log → picks, stack table, per-channel delays |
| `waterline_waves.py` | one-channel steps and half-rise of storm wave power | band-power table → waterline JSON |
| `road_path.py` | OSM paths through the anchors, reference-route choice, path-shape check | config + Overpass JSON + reference route → `paths.csv`, report |
| `build_channel_map.py` | the map from a JSON config | config → channel tables, summary, segment tables, `--compare` |
| `quake_coupling.py` | per-channel earthquake SNR, weak runs, match with extra fibre | event windows → coupling CSV, weak runs |
| `vehicle_coil.py` | coil vs stretch, block point on the road | stacked correlations / car tracks → tables |
| `validate_map.py` | GPS vs route, AIS crossings, hammer moveout | map + check data → numbers |
| `make_delivery.py` | data dictionary, slack inventory, change table, GeoJSON / KML, md5 | built tables → delivery files |
| `upload_version.sh` | versioned upload with md5 check and `current` link | folder → remote version |

The repository's `examples/synthetic/` builds a cable with a known truth and runs the chain end to end; the tests
(`tests/`) cover every script on synthetic data.

## References

| File | Read when |
|---|---|
| `references/conventions.md` | always first |
| `references/anchors.md` | tap tests, waterlines |
| `references/paths.md` | choosing paths between anchors, the sea route, hand-drawn routes |
| `references/placement.md` | writing the config; slack blocks and their edges; unanchored ends |
| `references/slack.md` | extra fibre, earthquakes, vehicles; deciding what goes into the map |
| `references/uncertainty.md` | `pos_unc_m` rules and where they come from |
| `references/validation.md` | independent checks and what each can show |
| `references/delivery.md` | the package, versions, upload |
| `references/pitfalls.md` | before delivering, and when something looks "a bit off" |
| `references/kefalonia-example.md` | real numbers from the cable the method was built on |
