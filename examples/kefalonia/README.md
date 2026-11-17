# Real example: the Kefalonia–Ithaca seafloor DAS cable (2024)

`run_kefalonia.py` rebuilds the delivered channel map of this cable from its real inputs:

```bash
python3 examples/kefalonia/run_kefalonia.py          # ~5 s; writes examples/kefalonia/out/ and docs/kefalonia.png
```

1. **Distance convention**: the 45 shot picks against the logged distances. Read as the header distance, 44 of
   45 agree within ±21 m; read as the nominal label FO_nom, the error grows to −170 m at the beach.
2. **Paths**: `road_path.py` on the OpenStreetMap extract and the operator's land route: 41 OSM segments, 1
   operator-route segment; the OSM path and the operator route through the same anchors differ by a median 4 m.
3. **Build**: `build_channel_map.py data/config.json`: 1872 channels in seven segments, six slack blocks on
   land at the points the vehicles gave, the sea route stretched between the two waterlines, Ithaca placed with
   the Kefalonia fibre / road ratio. Compared channel by channel with the delivered table: largest difference
   0.76 m, which is the rounding in the 2024 files (positions kept to 5 decimals of a degree, land paths to ~0.1 m).
4. **Figure** `docs/kefalonia.png`.

The evidence behind the anchors, the waterlines and the slack blocks (hammer stacks, wave spectra, earthquakes,
60 days of traffic) is summarised in `das-channel-mapping/references/kefalonia-example.md`; those raw data are
not in this repository, only the numbers they produced (anchor channels, waterline channels, block channels and
points in `data/config.json`).

## Files in `data/`

| File | Content | Source |
|---|---|---|
| `config.json` | the placement configuration (pieces, anchors fixes, slack blocks, waterlines) | this project |
| `shots.csv` | 45 tap-test shots: picked channel, GPS latitude / longitude, logged along-fibre distance | tap test, 2024-04-23 |
| `anchors.csv` | the 44 land shots used as anchors (shot #33 is the far end of the beach coil) | from `shots.csv` |
| `osm_highways.json` | Overpass extract of the highway ways around the land route (2026-10-28) | © OpenStreetMap contributors, ODbL 1.0 |
| `operator_land_route.csv` | the land route as drawn by the cable operator, traced from a georeferenced screenshot | cable operator |
| `sea_route.csv` | the operator's submarine route; its last stretch before Ithaca follows the hand-drawn approach | cable operator, this project |
| `ithaca_route.csv` | the Ithaca land route, drawn by hand on the operator's screenshot (to the telecom node) | this project |
| `coastline.csv` | 1 m contour of the Copernicus GLO-30 DSM, for the figure only | © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved |
| `delivered_channel_map_8m.csv` | the delivered channel table (version of 2026-11-01), main columns | this project |

The experiment data (shots, routes, delivered table) are provided to reproduce this example; ask the
repository owner before using them for anything else. OSM data must be credited as above and stay under the ODbL.
