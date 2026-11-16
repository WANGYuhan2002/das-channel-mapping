# The delivery package

The map is used by people who will not read the method. Give them one folder, one README that says which file
to use, and enough metadata that nobody has to guess a convention again.

## 1. Layout

```
<delivery>/
  README.md                          which file for which data, the conventions, what not to use any more
  data/
    channel_map_<raw>.csv            one row per raw channel (from build_channel_map.py)
    channel_map_<decimated>.csv      one row per channel of each decimated product, same columns
    channel_map_summary.json         build parameters: anchors, fixes, blocks, ratios, per-piece numbers
    channel_map_segments.csv         per segment: channel range, fibre, ground, ratio, uncertainty
    channel_map_anchored_segments.csv   per pair of anchors: path, fibre, extra fibre, block, its point
    data_dictionary.csv              every column of both tables: unit, dtype, empty cells, meaning, how, when empty
    segment_positioning.csv          per segment: how it was positioned, how it was checked, uncertainty
    slack_inventory.csv              every block in the map + the extra fibre spread evenly
    map_change.csv                   per channel: move since the previous version(s), along / across the path
    validation.json                  numbers of the independent checks (validation.md)
    channel_map_<raw>.geojson, _features.geojson, channel_map.kml   GIS
    intermediate/                    previous versions of the table (for comparison only)
  report/                            the method report (figures + text)
  md5sums.txt
```

## 2. Columns of the channel table

| Column | Content |
|---|---|
| `raw_col`, `sorted_j` | channel index; index in the decimated product (−1 where not in it) |
| label column (e.g. `fo_nom_m`) | the nominal label users know — marked as a label |
| distance column (e.g. `dist_header_m`) | true fibre distance |
| `segment`, `path_source`, `slack` | which rule placed the channel; block kind |
| `lat`, `lon` | WGS84, centre of the gauge, ≥ 7 decimals |
| `s_path_m`, `strike_deg` | ground length from channel 0; local strike |
| `pos_unc_m` | ~1 σ |
| alternatives | e.g. `sea_lat_anchored`/`sea_lon_anchored` for a second submarine placement |
| optional | `elev_m`, `elev_src`, `elev_unc_m`; the old positions and old − new (along / across) |

`make_delivery.py dictionary` writes the data dictionary from the actual tables (dtype, empty cells) and a
description of the standard columns; describe project columns with `--extra`.

## 3. Tables that answer users' questions

- **Segment positioning** (one row per segment): channel and decimated ranges, labels, fibre / ground length,
  how it was positioned, how it was checked, uncertainty min / median / max. Write it by hand from
  `channel_map_segments.csv` plus the method; it is the table people copy into papers.
- **Slack inventory** (`make_delivery.py slack`): every block (channels, fibre, point, `placed_by`,
  `at_m_from_first_anchor`, `uniform_rest_at_m`, fibre − road before / after the block, uncertainty) and the
  extra fibre spread evenly per part. Add the evidence per block (earthquake signal ratio, vehicle road channels).
- **Map change** (`make_delivery.py change --old ... --new ...`): per channel, how far it moved since each
  earlier delivered version; summarise "who must redo what" in the README (which channel ranges moved > 10 m).

## 4. GIS

`make_delivery.py gis`: GeoJSON points per table ([lon, lat], RFC 7946, NaN → null), a features file (segment
lines, anchors, blocks, extra points from `--points` such as waterlines, the beach end, the node at the far end,
the drawn route beyond the last channel) and a KML for Google Earth (segment lines, every channel with an
attribute table, every 10th labelled).

## 5. Versioning and upload

- Never overwrite a delivered version. Name versions after the build they hold (`<map>_<YYYY-MM-DD>_<HHMM>`),
  keep a version table in the top-level README ("what changed, which channels moved"), and point `current` at
  the newest: scripts that want reproducibility use the version folder, others `current`.
- `upload_version.sh [-n] [-r README] <host> <remote-root> <version> <folder>`: writes `md5sums.txt`, refuses an
  existing version, rsyncs, runs `md5sum -c` on the remote and only then moves `current`. Dry-run first (`-n`).
  Check inode / quota limits of the remote store before uploading many small files.
- When the map changes: rebuild → compare with the delivered version → refresh the delivery (tables, GIS,
  change table, report numbers) → new version folder → upload → tell every downstream user what moved.

## 6. README for users (template)

1. Which file for which data (raw vs decimated), with a two-line loading example.
2. Conventions: position = gauge centre; true spacing; label vs true distance.
3. Slack blocks and coils: channel ranges, "not a line array", how to exclude them.
4. Uncertainty per segment, and which parts are inferences.
5. What not to use any more (older station lists, tables made under the wrong convention).
6. Version table.
