#!/usr/bin/env python3
"""A synthetic land + sea cable with a known truth, to try the das-channel-mapping scripts end to end.

Truth: an interrogator, a winding road on land with 9 tap-test anchors, one 41 m coil at a point between two
anchors, a 120 m coil in a beach manhole, a short beach, a 3 km submarine route with 1.5 % slack, and a far-shore
road with no anchors (placed with the fibre / road ratio of the land part). Everything is invented: the place is
an arbitrary point and the coordinates mean nothing.

    python3 make_synthetic.py --out data/
writes anchors.csv, osm.json (the road + a decoy parallel road), reference_route.csv (an "operator" drawing:
smoothed, shifted by a few metres), sea_route.csv, far_route.csv, config.json and truth.csv (true position of every
channel). Then:
    python3 ../../das-channel-mapping/scripts/road_path.py --config data/config.json --piece land \
        --osm data/osm.json --reference data/reference_route.csv --out data/paths.csv
    python3 ../../das-channel-mapping/scripts/build_channel_map.py data/config.json --out data/out
    python3 compare_truth.py data/
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "das-channel-mapping", "scripts"))
from cmap_geo import LocalXY, arclength, at_s  # noqa: E402

LAT0, LON0 = 10.0, 20.0
SPACING = 8.2
RATIO = 1.02                       # fibre / road on land outside the coils
COIL_AT, COIL_M = 0.55, 41.0       # coil between anchors 4 and 5: at 55 % of the segment road, 41 m of fibre
MANHOLE_M, BEACH_M = 120.0, 40.0
SEA_SLACK = 1.015


def road_polyline(rng):
    """a winding road ~2.2 km long (x east, y north, metres)."""
    s = np.linspace(0, 2200, 441)
    x = s * 0.8 + 60 * np.sin(s / 180.0)
    y = -s * 0.55 + 40 * np.sin(s / 95.0 + 0.4)
    return np.stack([x, y], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "data"))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    P = LocalXY(LAT0, LON0)
    road = road_polyline(rng)
    s_road = arclength(road[:, 0], road[:, 1])
    L = s_road[-1]
    # fibre along the road: channel c sits at road position s(c); internal 10 channels + 40 m stored in a cabin
    n_int, cabin_m = 10, 40.0
    c_land0 = n_int + cabin_m / SPACING                 # fractional channel where the road starts (anchor 0)
    anchors_s = np.linspace(0, L, 9)                    # 9 anchors along the road
    seg_coil = 4                                        # coil between anchors 4 and 5
    fibre_at_anchor = [0.0]
    for i in range(1, len(anchors_s)):
        f = (anchors_s[i] - anchors_s[i - 1]) * RATIO + (COIL_M if i - 1 == seg_coil else 0.0)
        fibre_at_anchor.append(fibre_at_anchor[-1] + f)
    anchor_cols = c_land0 + np.array(fibre_at_anchor) / SPACING
    s_coil = anchors_s[seg_coil] + COIL_AT * (anchors_s[seg_coil + 1] - anchors_s[seg_coil])
    k1 = anchor_cols[seg_coil] + (s_coil - anchors_s[seg_coil]) * RATIO / SPACING
    k2 = k1 + COIL_M / SPACING
    c_road_end = anchor_cols[-1]
    c_manhole_end = c_road_end + MANHOLE_M / SPACING
    c_water = c_manhole_end + BEACH_M * 1.1 / SPACING   # beach fibre 10 % longer than the straight line
    sea_len = 3000.0
    c_far = c_water + sea_len * SEA_SLACK / SPACING
    far_len = 420.0
    n = int(np.floor(c_far + far_len * RATIO / SPACING * 0.8))   # the record ends before the far route ends

    def land_s(c):
        """true road position of fractional channel c on land."""
        out = np.empty_like(c)
        for j, cc in enumerate(c):
            i = min(int(np.searchsorted(anchor_cols, cc, side="right") - 1), len(anchor_cols) - 2)
            a0, a1 = anchor_cols[i], anchor_cols[i + 1]
            s0, s1 = anchors_s[i], anchors_s[i + 1]
            if i == seg_coil:
                if cc <= k1:
                    out[j] = s0 + (cc - a0) * SPACING / RATIO
                elif cc < k2:
                    out[j] = s_coil
                else:
                    out[j] = s_coil + (cc - k2) * SPACING / RATIO
            else:
                out[j] = s0 + (cc - a0) * (s1 - s0) / (a1 - a0)
        return out
    cabin_xy = road[0] + np.array([-8.0, 6.0])
    manhole = road[-1] + np.array([25.0, -20.0])
    water = manhole + np.array([BEACH_M * 0.6, -BEACH_M * 0.8])
    sea = np.stack([water[0] + np.linspace(0, 2600, 60), water[1] - np.linspace(0, 1500, 60) +
                    80 * np.sin(np.linspace(0, 3, 60))], -1)
    sea = np.vstack([water, sea[1:]])
    s_sea = arclength(sea[:, 0], sea[:, 1])
    sea = np.stack(at_s(sea[:, 0], sea[:, 1], np.linspace(0, s_sea[-1], 200)), -1)
    sea = water + (sea - water) * sea_len / s_sea[-1]           # exactly 3 km
    far = np.stack([sea[-1, 0] + np.linspace(0, 300, 40), sea[-1, 1] + 120 * np.sin(np.linspace(0, 2.5, 40))], -1)
    c = np.arange(n, dtype=float)
    X = np.zeros((n, 2))
    seg = np.full(n, "", dtype=object)
    m = c < n_int
    X[m], seg[m] = cabin_xy + np.array([-10.0, 0.0]), "internal"
    m = (c >= n_int) & (c < c_land0)
    f = (c[m] - n_int) / (c_land0 - n_int)
    X[m] = (cabin_xy + np.array([-10.0, 0.0])) + f[:, None] * (road[0] - (cabin_xy + np.array([-10.0, 0.0])))
    seg[m] = "cabin"
    m = (c >= c_land0) & (c <= c_road_end)
    X[m] = np.stack(at_s(road[:, 0], road[:, 1], land_s(c[m])), -1)
    seg[m] = "land"
    m = (c > c_road_end) & (c <= c_manhole_end)
    X[m], seg[m] = manhole, "coil"
    m = (c > c_manhole_end) & (c < c_water)
    X[m] = manhole + ((c[m] - c_manhole_end) / (c_water - c_manhole_end))[:, None] * (water - manhole)
    seg[m] = "beach"
    m = (c >= c_water) & (c <= c_far)
    s_q = (c[m] - c_water) / (c_far - c_water) * sea_len
    X[m], seg[m] = np.stack(at_s(sea[:, 0], sea[:, 1], s_q), -1), "sea"
    m = c > c_far
    X[m] = np.stack(at_s(far[:, 0], far[:, 1], (c[m] - c_far) * SPACING / RATIO), -1)
    seg[m] = "far_land"
    lat, lon = P.latlon(X[:, 0], X[:, 1])
    pd.DataFrame(dict(raw_col=c.astype(int), segment=seg, lat=lat, lon=lon)).to_csv(
        os.path.join(a.out, "truth.csv"), index=False, float_format="%.10g")
    # observations
    gps = np.stack(at_s(road[:, 0], road[:, 1], anchors_s), -1) + rng.normal(0, 2.0, (len(anchors_s), 2))
    gps[0] = road[0] + rng.normal(0, 2.0, 2)
    pick = anchor_cols + rng.normal(0, 0.1, len(anchor_cols))   # tap-test picks ~0.1 channel
    alat, alon = P.latlon(gps[:, 0], gps[:, 1])
    pd.DataFrame(dict(name=[str(i + 1) for i in range(len(pick))], col=pick, lat=alat, lon=alon)).to_csv(
        os.path.join(a.out, "anchors.csv"), index=False, float_format="%.10g")
    # OSM: the road (vertices every ~10 m, 0.5 m noise) + a decoy parallel road 60 m to the side, as Overpass JSON
    def way(xy, wid, hw, node0):
        la, lo = P.latlon(xy[:, 0], xy[:, 1])
        return dict(type="way", id=wid, nodes=list(range(node0, node0 + len(xy))), tags=dict(highway=hw),
                    geometry=[dict(lat=float(p), lon=float(q)) for p, q in zip(la, lo)])
    rd = road[::5] + rng.normal(0, 0.5, road[::5].shape)
    decoy = road[::5] + np.array([60.0, 40.0])
    osm = dict(elements=[way(rd, 1, "tertiary", 1000), way(decoy, 2, "residential", 5000),
                         way(np.vstack([rd[len(rd) // 2], decoy[len(rd) // 2]]), 3, "footway", 9000)])
    osm["elements"][2]["nodes"] = [1000 + len(rd) // 2, 5000 + len(rd) // 2]
    json.dump(osm, open(os.path.join(a.out, "osm.json"), "w"))
    # "operator" drawing of the land route: smoothed over ~45 m and shifted 6 m (georeferencing error)
    from scipy.ndimage import uniform_filter1d
    ref = uniform_filter1d(road, 9, axis=0, mode="nearest") + np.array([4.0, -4.5])
    rla, rlo = P.latlon(ref[:, 0], ref[:, 1])
    pd.DataFrame(dict(lat=rla, lon=rlo)).to_csv(os.path.join(a.out, "reference_route.csv"), index=False,
                                                float_format="%.10g")
    sla, slo = P.latlon(sea[:, 0], sea[:, 1])
    pd.DataFrame(dict(lat=sla, lon=slo)).to_csv(os.path.join(a.out, "sea_route.csv"), index=False, float_format="%.10g")
    fla, flo = P.latlon(far[:, 0], far[:, 1])
    pd.DataFrame(dict(lat=fla, lon=flo)).to_csv(os.path.join(a.out, "far_route.csv"), index=False, float_format="%.10g")
    mla, mlo = P.latlon(*manhole)
    wla, wlo = P.latlon(*water)
    ila, ilo = P.latlon(*(cabin_xy + np.array([-10.0, 0.0])))
    # the waterlines are what the wave analysis would give (here: the truth +- a fraction of a channel)
    cw_obs = round(c_water * 2) / 2
    cf_obs = round(c_far * 2) / 2
    k1_obs, k2_obs = np.floor(k1) + 0.5, np.ceil(k2) - 0.5      # weak run from the earthquakes, half-channel edges
    cfg = dict(
        name="synthetic example", n_channels=n, spacing_m=SPACING, first_channel_distance_m=-n_int * SPACING,
        tables=[dict(name="all", step=1), dict(name="dec2", step=2, index_column="j2")],
        pieces=[
            dict(segment="internal", type="point", cols=[0, n_int], at=[float(ila), float(ilo)], unc_m=None,
                 path_source="interrogator_gps"),
            dict(segment="cabin", type="line", cols=[n_int, float(pick[0])], **{"from": [float(ila), float(ilo)],
                 "to": [float(alat[0]), float(alon[0])]}, unc_m=15, strike=False),
            dict(segment="land", type="anchored", anchors="anchors.csv", paths="paths.csv",
                 slack=[dict(between=[str(seg_coil + 1), str(seg_coil + 2)], cols=[float(k1_obs), float(k2_obs)],
                             kind="quake_coil", at_fraction=COIL_AT, placed_by="vehicles")]),
            dict(segment="coil", type="point", cols=[float(pick[-1]), float(c_manhole_end)], include_end=True,
                 at=[float(mla), float(mlo)], unc_m=15, path_source="manhole", slack_label="beach_coil"),
            dict(segment="beach", type="line", cols=[float(c_manhole_end), cw_obs],
                 **{"from": [float(mla), float(mlo)], "to": [float(wla), float(wlo)]}, unc_m=15),
            dict(segment="sea", type="path", cols=[cw_obs, cf_obs], include_end=True, route="sea_route.csv", unc_m=30,
                 path_source="route_stretch"),
            dict(segment="far_land", type="ratio", cols=[cf_obs, n - 1], start_col=cf_obs, route="far_route.csv",
                 ratio="anchored", unc_rules=[dict(unc_m=60)], path_source="drawn_route"),
        ])
    json.dump(cfg, open(os.path.join(a.out, "config.json"), "w"), indent=1)
    print(f"{n} channels; anchors at {np.round(anchor_cols, 1).tolist()}; coil {k1:.2f}-{k2:.2f}; "
          f"waterlines {c_water:.2f} / {c_far:.2f}; written to {a.out}")


if __name__ == "__main__":
    main()
