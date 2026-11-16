# das-channel-mapping

**English** · [中文](README_zh.md)

A Claude Code skill (and a small set of Python scripts) for building, checking and delivering a **DAS channel
map**: every channel of a distributed acoustic sensing fibre placed at a latitude / longitude, with a position
uncertainty, for land, submarine or mixed cables.

The map is built from

- **anchors**: channels the data pin to a point on the ground — hammer / tap-test shots with GPS, and the
  waterlines found from ocean-wave loading;
- **paths** between anchors: OpenStreetMap roads shifted through the shot points, the operator's route, routes
  the user draws by hand;
- **placement rules**: uniform in channel between anchors, slack coils at one point of the road, the submarine
  route stretched between the two waterlines, unanchored ends placed with the measured fibre/road ratio;
- **slack evidence**: extra fibre per segment, earthquake coupling (fibre that does not follow the ground),
  vehicles (a coil at one point vs a stretch along the road, and where on the road it sits);
- **uncertainty rules**, **independent checks** (shot GPS vs route, AIS ship crossings, hammer travel times)
  and a **versioned delivery** (CSV tables, data dictionary, slack inventory, change table, GeoJSON / KML, md5).

The method was developed on the Kefalonia–Ithaca seafloor DAS cable (Greece, 2024); the skill includes that case
as a worked example with its real numbers. No data and no coordinates are included.

## Install the skill

```bash
git clone https://github.com/WANGYuhan2002/das-channel-mapping
ln -s "$PWD/das-channel-mapping/das-channel-mapping" ~/.claude/skills/das-channel-mapping
```

Claude Code then uses it when you ask to map, georeference or check DAS channels, interpret a tap test, find
fibre slack, place a cable route or deliver a channel table (in English or Chinese).

## Use the scripts directly

Python ≥ 3.9 with numpy, pandas, scipy (networkx for the OSM paths; pytest for the tests):

```bash
pip install -r requirements.txt
cd examples/synthetic
python3 make_synthetic.py --out data
python3 ../../das-channel-mapping/scripts/road_path.py --config data/config.json --piece land \
    --osm data/osm.json --reference data/reference_route.csv --out data/paths.csv
python3 ../../das-channel-mapping/scripts/build_channel_map.py data/config.json --out data/out
python3 compare_truth.py data
```

| Script | Does |
|---|---|
| `hammer_anchor.py` | find the blows of each shot, stack them, read the anchor channel, footprint, loops and coils; test which distance convention a field log used |
| `waterline_waves.py` | waterline and end of a beach from storm vs calm wave power (one-channel steps, half-rise) |
| `road_path.py` | OSM shortest paths between anchors, shifted through the shot points; choice against a reference route |
| `build_channel_map.py` | the channel map from a JSON configuration of pieces (point, line, path, anchored, ratio) |
| `quake_coupling.py` | weak-coupling runs from regional earthquakes, matched with the segments' extra fibre |
| `vehicle_coil.py` | coil at one point or stretch along the road; the coil's point on the road (stacked correlations or single cars) |
| `validate_map.py` | independent checks: GPS vs route, AIS crossings, hammer moveout |
| `make_delivery.py` | data dictionary, slack inventory, per-channel change table, GeoJSON / KML, md5 manifest |
| `upload_version.sh` | upload a delivery as an immutable version, check md5 remotely, move `current` |

Every script has `--help`. The skill's `SKILL.md` gives the workflow and `references/` the method in detail.

## Tests

```bash
python3 -m pytest -q tests/
```

The tests run every script on synthetic data. The scripts were also checked against the original Kefalonia–Ithaca
results: the channel table, the land paths, the hammer stacks, the earthquake weak runs, the waterline steps, the
vehicle coil positions and the AIS check are reproduced (positions to the rounding of the original tables).

## Credits

OpenStreetMap data © OpenStreetMap contributors (ODbL) — credit it on figures made with OSM paths.

## License

MIT — see [LICENSE](LICENSE).
