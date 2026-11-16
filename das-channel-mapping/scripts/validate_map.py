#!/usr/bin/env python3
"""Independent checks of a channel map: data that did NOT go into building it.

  gps      distance of GPS points (e.g. the hammer points) to a reference route (operator / as-built drawing):
           checks the route's georeferencing and that the cable runs where the drawing says
  ais      ship crossings: the point where an AIS track segment (two consecutive positions on either side of
           the cable) crosses the mapped submarine cable, as an along-fibre label, minus the label of the channel
           where the DAS sees the ship pass. The median tests the along-cable position of the whole submarine
           part; the scatter (~300 m with hourly AIS) says nothing about single channels. Compare an old and a
           new map with the same pairs.
  moveout  hammer onset delays vs map distance inside each footprint (hammer_anchor.py stack --map --gps):
           residuals of a few to ~10 m are consistent; it cannot place channels better than ~10 m
  paths    (done by road_path.py --report): channel positions along the chosen road path vs along the reference
           route through the same anchors: the size of the path-shape error

    python3 validate_map.py gps --points shots.csv --route ref_route.csv --out gps_check.csv
    python3 validate_map.py ais --map channel_map_16m.csv --segment sea --label-col fo_nom_m \
        --crossings ais_pairs.csv [--old-map old_16m.csv] [--min-length 50] [--max-dt 15] --out ais_check.json
    python3 validate_map.py moveout --delays delays.csv
ais_pairs.csv: lat1, lon1, lat2, lon2 (the AIS chord), das_label_m (along-fibre label of the DAS passage), and
optionally length_m (ship length) and dt_min (AIS crossing time - DAS passage time) for the filters.
"""
import argparse
import json
import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmap_geo import LocalXY, point_to_polyline, segment_crossing  # noqa: E402


def gps_check(points, route):
    P = LocalXY.around(np.r_[points.lat, route.lat], np.r_[points.lon, route.lon])
    x, y = P.xy(route.lat.to_numpy(), route.lon.to_numpy())
    px, py = P.xy(points.lat.to_numpy(), points.lon.to_numpy())
    d, s = point_to_polyline(px, py, x, y)
    return points.assign(dist_to_route_m=d, s_on_route_m=s)


def crossing_labels(M, chords, segment, label_col):
    q = M[M.segment.isin(segment)] if segment else M
    P = LocalXY.around(q.lat, q.lon)
    x, y = P.xy(q.lat.to_numpy(), q.lon.to_numpy())
    lab = q[label_col].to_numpy(float)
    out = []
    for r in chords.itertuples():
        p1, p2 = P.xy(r.lat1, r.lon1), P.xy(r.lat2, r.lon2)
        out.append(segment_crossing((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])), x, y, lab))
    return np.array(out)


def bootstrap_median(v, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    bs = [np.median(rng.choice(v, len(v))) for _ in range(n)]
    return dict(median_m=float(np.median(v)), ci90=[float(np.percentile(bs, 5)), float(np.percentile(bs, 95))],
                mad_m=float(np.median(np.abs(v - np.median(v)))), p05_m=float(np.percentile(v, 5)),
                p95_m=float(np.percentile(v, 95)), n=int(len(v)))


def main():
    ap = argparse.ArgumentParser(description="independent checks of a channel map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gps")
    g.add_argument("--points", required=True, help="CSV name, lat, lon")
    g.add_argument("--route", required=True, help="CSV lat, lon in route order")
    g.add_argument("--max-m", type=float, default=50.0, help="points farther than this are reported as outside")
    g.add_argument("--out")
    s = sub.add_parser("ais")
    s.add_argument("--map", required=True)
    s.add_argument("--old-map")
    s.add_argument("--segment", action="append", default=[], help="segment label(s) of the submarine part")
    s.add_argument("--label-col", default="dist_m", help="along-fibre column used by the DAS passage labels")
    s.add_argument("--crossings", required=True)
    s.add_argument("--min-length", type=float, default=50.0)
    s.add_argument("--max-dt", type=float, default=15.0)
    s.add_argument("--out")
    m = sub.add_parser("moveout")
    m.add_argument("--delays", required=True, help="hammer_anchor.py stack --delays output with resid_m")
    a = ap.parse_args()
    if a.cmd == "gps":
        R = gps_check(pd.read_csv(a.points), pd.read_csv(a.route))
        ins = R.dist_to_route_m <= a.max_m
        print(R.round(2).to_string(index=False))
        print(dict(n_within=int(ins.sum()), median_m=float(R.dist_to_route_m[ins].median()),
                   p90_m=float(R.dist_to_route_m[ins].quantile(0.9)), max_m=float(R.dist_to_route_m[ins].max())))
        if a.out:
            R.to_csv(a.out, index=False, float_format="%.6g")
    elif a.cmd == "ais":
        C = pd.read_csv(a.crossings)
        keep = np.ones(len(C), bool)
        if "length_m" in C:
            keep &= C.length_m.to_numpy() >= a.min_length
        if "dt_min" in C:
            keep &= np.abs(C.dt_min.to_numpy()) <= a.max_dt
        C = C[keep].copy()
        maps = dict(new=a.map, **({"old": a.old_map} if a.old_map else {}))
        res = {}
        for k, f in maps.items():
            C[f"label_{k}"] = crossing_labels(pd.read_csv(f), C, a.segment, a.label_col)
            C[f"d_{k}_m"] = C[f"label_{k}"] - C.das_label_m
        ok = np.all([C[f"label_{k}"].notna() for k in maps], axis=0)
        for k in maps:
            res[k] = bootstrap_median(C.loc[ok, f"d_{k}_m"].to_numpy())
        print(json.dumps(res, indent=1))
        if a.out:
            json.dump(res, open(a.out, "w"), indent=1)
            C.to_csv(os.path.splitext(a.out)[0] + ".csv", index=False, float_format="%.6g")
    else:
        D = pd.read_csv(a.delays)
        r = D.resid_m.dropna().abs()
        print(dict(n_channels=int(len(r)), median_abs_m=float(r.median()), p90_abs_m=float(r.quantile(0.9)),
                   by_shot=D.groupby("name").resid_m.apply(lambda v: float(v.abs().median())).round(1).to_dict()))


if __name__ == "__main__":
    main()
