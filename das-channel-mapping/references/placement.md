# Placement rules and the build configuration

`build_channel_map.py config.json --out DIR` turns anchors, paths and rules into the table. The config is a
list of **pieces** along the fibre; each owns a channel range `cols: [lo, hi]` (`lo ≤ c < hi`; `include_end`
also takes `c == hi`; the last piece and anchored pieces include their end; earlier pieces win ties). Start from
`assets/config_template.json`.

## 1. Top level

```json
{"name": "...", "n_channels": 1872, "spacing_m": 8.16761589, "first_channel_distance_m": -207.208,
 "label": {"column": "fo_nom_m", "offset_m": -215, "step_m": 8}, "distance_column": "dist_header_m",
 "tables": [{"name": "8m", "step": 1}, {"name": "16m", "step": 2, "index_column": "sorted_j"}],
 "strike": {"half": 6, "min_chord_m": 20, "exclude_slack": true},
 "projection": {"lat0": ..., "lon0": ...},          // optional; kx / ky only to reproduce an old pipeline
 "pieces": [...]}
```

## 2. Piece types

| type | rule | keys |
|---|---|---|
| `point` | every channel at one point | `at` [lat, lon], `unc_m` (null inside the interrogator), `slack_label` |
| `line` | uniform in channel on a straight line | `from`, `to`, `ends` (channels tied to the two points; default `cols`) |
| `path` | uniform in channel along a polyline whose ends are tied to channels | `route` (CSV lat, lon / GeoJSON / list), `ends` |
| `anchored` | anchors + paths + slack blocks | `anchors`, `paths`, `slack`, `merge_within_cols`, `anchor_fix`, `unc` |
| `ratio` | along a route from `start_col` with a fibre/path ratio | `route`, `start_col`, `ratio` (number or `"anchored"`), `max_excess_rest_m`, `features` |

Every piece takes `segment`, `path_source`, `unc_m` or `unc_rules`, `strike` (false for point-like pieces).

## 3. Anchored segments (land between anchors)

- Channels between two anchors are **uniform in channel along the path** (any extra fibre is spread evenly) —
  unless a **slack block** is declared for that segment.
- A slack block `{"between": "14-15", "cols": [245.5, 250.5], "kind": "quake_coil", "at_fraction": 0.5926,
  "placed_by": "vehicles"}`: every channel with `k1 ≤ c ≤ k2` sits at ONE point of the path, at `at_fraction`
  of the path length (or `at_m` from the first anchor). The channels before the block are uniform between the
  first anchor and the block point, those after between the block point and the second anchor. Without a given
  point the block goes where the rest of the segment is uniform in channel (`uniform_rest`).
- The anchored ratio for a `ratio` piece = Σ(fibre − block fibre) / Σ path over the anchored segments, leaving
  out segments with > 100 m of unexplained extra fibre (an unlocated coil would bias it).

**Block edges.** A weak run from the earthquakes ("channels a … b are not coupled") is usually written with
half-channel edges, `[a − 0.5, b + 0.5]`: block fibre = n channels. But the two edge channels' gauges are half
in the coil and half on the road, so the coil itself is closer to "centre of a to centre of b" (n − 1
channels). Signs that the edges are too wide: the fibre before (or after) the block comes out *shorter* than the
road (Kefalonia: −6.2 m and −9.5 m in two segments, within the uncertainty), or the vehicles put the channels
just outside the block a full channel away from it. A block found by the vehicles alone (all its channels at
one point, the neighbours a channel away) is best written centre to centre. Changing edges is the user's call:
show the fibre − road before / after the block both ways.

## 4. Where the channel table must stay honest

- Write the rule each channel came from (`segment`, `path_source`, `slack`).
- Channels in a block or a coil are at one point: tell users they are not a line array (no wavenumbers,
  apparent speeds or beamforming through them).
- Where nothing ties the cable to the map (a far end placed by `ratio`), say "inference" in the summary and the
  README, give the route left after the last channel, and do not let a hopeful end point ("it ends at the
  node") override the data. Keep the alternative placements you rejected, with the reason.

## 5. After every build

1. `--compare previous_map.csv`: how many channels moved > 0.5 m / > 10 m, the largest move, per segment. Moves
   outside the stretch you changed mean a mistake.
2. Look at `*_segments.csv` (fibre vs ground per segment) and `*_anchored_segments.csv` (fibre − path per
   segment, blocks, `excess_rest_m`): segments with fibre shorter than path by more than the uncertainty need a
   look; a big positive `excess_rest_m` is unlocated slack.
3. Draw the map: every channel on imagery (or OSM), anchors, blocks as one marker, the segment colours, the
   paths; and the along-cable profiles of cumulative fibre − ground, ground length per channel, `pos_unc_m`.
4. Add elevation if wanted: bilinear in a DEM (land, e.g. Copernicus GLO-30; check it against the shot-point GPS
   altitudes) and a bathymetry grid (sea, e.g. EMODnet); `elev_unc_m` = spread of the grid within `pos_unc_m`;
   set coastal cells that are part land to 0 and mark them (`elev_src`). Re-add it after every rebuild.
