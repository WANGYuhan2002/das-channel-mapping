# Position uncertainty (`pos_unc_m`, about 1 σ)

Every channel gets a number that says how far it may be from where the table puts it. The rules are simple on
purpose: users should be able to reproduce them from the README.

| Where | Rule | Kefalonia |
|---|---|---|
| inside the interrogator | none (empty) | — |
| stored reel / cabin, manhole coil, beach | ~15 m (a point or a short straight line with stored fibre) | 15 m |
| land between anchors, on a road path | `road_m` + ½ × \|fibre − block fibre − path\| of that segment | 5 + ½ \|…\| → 5.1–14.4 m, median 7.5 m |
| land between anchors, on a straight line | `straight_m` + ½ × \|…\| | 10 + ½ \|…\| |
| channels of a block placed by vehicles | `road_m` + `located_m` | 5 + 5 = 10 m |
| channels of a block placed by "uniform rest" | `road_m` + ½ × block fibre | e.g. 5 + 65 = 70 m for a 131 m coil |
| submarine route stretched between two waterlines | a constant set by the route quality and the AIS check | 30 m |
| far end placed by a ratio | on a beach tied by the waves ~15 m; inland, no anchors, end unknown ~60 m | 15 / 60 m |

Where the numbers come from:

- `road_m` = 5 m: two independent path shapes through the same anchors (OSM vs operator route) differ by a
  median 4 m channel by channel; the GPS of the anchors is good to a few m.
- `straight_m` = 10 m: a straight line cuts corners.
- ½ × |unexplained extra fibre|: if the extra fibre is not spread evenly but sits somewhere in the segment, the
  channels can be off by up to the whole amount; half of it is a 1 σ-like number. This is what makes a located
  block pay off (Kefalonia: one segment went from 79.5 m to 8.1 m when its 155 m coil was put at the vehicle point).
- `located_m` = 5 m: vehicle position error (two-direction difference + shared speed bias ≈ ±4 m) on top of
  the path error.
- Sea 30 m: the drawn route is smoothed over ~±45 m and has no anchors between the two waterlines; the AIS check
  constrains only the bulk position (and only where the big ships cross).
- Far end 60 m: an inference; say so.

Report min / median / max per segment and draw `pos_unc_m` along the cable. If a user needs better positions
somewhere, the cure is more anchors there (another tap test, a GPS'ed feature the data can see), not a smarter
interpolation.
