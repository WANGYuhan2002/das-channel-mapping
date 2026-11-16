# Channel numbering and distance conventions

Settle these before touching any position. Most channel-map errors are convention errors, and they are
systematic: they grow along the cable and look like "the map is a bit off".

## 1. Three different along-fibre numbers

| Quantity | Formula | What it is |
|---|---|---|
| channel index `c` | 0 … n−1 | column of the recorded data |
| true fibre distance | `start_distance + c × spacing` | what the interrogator measures (file header: start distance, spatial sampling interval) |
| nominal label | e.g. `offset + nominal_step × c` | a convenient label some products carry (e.g. "8 m channels"), **not** a length |

- **True spacing = nominal spacing × fibre-length multiplier** (the refractive-index / group-index factor in the
  header; e.g. 8 m × 1.020952 = 8.1676 m). Use the true spacing for every fibre length, wavenumber and speed.
  A label built with the nominal step drifts from the true distance by `(true − nominal) × c` — 0.17 m per
  channel in the example, 159 m after 900 channels.
- **Negative distances** are fibre inside the interrogator (header start distance / start locus < 0): put
  those channels at the interrogator, with no uncertainty and no strike.
- **Decimated products** (e.g. every 2nd channel after spatial low-pass): record which raw channel each output
  channel is centred on (`j = c / 2` for even `c` is common) and give that product its own table, with the
  same columns, from the same build.

## 2. Which distance did the field log use?

Hammer / tap-test logs, station lists and older channel tables quote "the distance" without saying which
one. Test it, don't assume it: pick the channel of every shot, then compare the pick with the channel the
logged distance implies under each convention (`hammer_anchor.py conventions`).

- The right convention leaves residuals of a few channels that **do not grow with distance**
  (Kefalonia: 44 of 45 shots within ±21 m, median −3.9 m, for the header distance).
- The wrong one shows a linear trend (Kefalonia: the nominal label drifted to −170 m by the beach).
- A single shot far off on its own is usually a coil between two shots logged at the same point (Kefalonia:
  shot #33 at +164 m sat at the far end of the 172 m beach-manhole coil, #34 at its near end).

Every derived product made under the wrong convention is shifted along the cable by the drift; list them and
tell the user which ones to rebuild.

## 3. A channel's position is the centre of its gauge

A channel averages strain over its gauge length (e.g. ±5 m of fibre around its centre; neighbouring gauges
overlap when the gauge is longer than the spacing). Give `lat`/`lon` for the **centre of the gauge**, and say
so in the delivery. A hammer anchor is the channel whose gauge is centred on the blow, so anchors satisfy this
whatever the interrogator calls the channel's position; tie waterlines and other features the same way.

## 4. Positions and metres

- Work in a local metric frame (`cmap_geo.LocalXY`): x east, y north, metres per degree from the WGS84
  ellipsoid at the reference latitude. The shortcut "111 320 m per degree" for latitude too makes north–south
  distances ~0.3 % too long at 38° N (harmless next to 5–60 m uncertainties, but avoid it in new work).
- Write `lat`/`lon` with ≥ 7 decimals (`%.10g`): a 7-significant-digit float format keeps only 5 decimals,
  i.e. ~1 m quantisation.
- Strike = azimuth of the chord between channels `c − h` and `c + h` (h = 6 → ±48 m in the example), clockwise
  from north; empty where the chord leaves the valid run, is shorter than ~20 m, or inside slack blocks.

## 5. Names to settle with the user (write them in the data dictionary)

- channel index name (`raw_col`), decimated index name (`sorted_j`), label column (`fo_nom_m`), distance
  column (`dist_header_m`);
- segment names (e.g. `internal`, `cabin`, `land`, `coil`, `beach`, `sea`, `far_land`);
- `path_source` values; `slack` kinds (e.g. `beach_coil`, `loop`, `unseen`, `quake_coil`, `car_coil`).
