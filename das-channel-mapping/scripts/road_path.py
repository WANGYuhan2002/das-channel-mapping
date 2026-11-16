#!/usr/bin/env python3
"""Paths between consecutive land anchors from OpenStreetMap roads, a reference route and the anchor GPS points.

Each source gives what it is best at:
  - anchor GPS points (hammer / tap-test blows): accurate, and they say on which side of the road the fibre runs;
  - OpenStreetMap: the road geometry (vertices every few metres);
  - a reference route (operator / as-built drawing, georeferenced screenshot): WHICH road the cable takes, but its
    line is smoothed and carries the georeferencing error.
Per segment (anchors a -> b):
  1. road part: shortest path along OSM ways between the road points nearest to the two anchors (each anchor may
     join any way within nearest + join_extra_m, e.g. at a junction; the leg + road + leg total decides), first
     on drivable roads (no footway / path / steps / pedestrian / cycleway / bridleway / corridor), else on all ways;
  2. the road part is shifted sideways so that it passes through both anchor points: every vertex moves along
     the local normal by an offset that changes linearly with arc length from a's signed offset to b's (an anchor
     left of the road keeps the fibre left of it; anchors on opposite sides = the fibre crosses in between);
  3. choice: where the reference route covers the segment (both anchors within ref_tol_m of its vertices), the OSM
     path is used if it stays within same_road_m of the reference route both ways (Hausdorff), else the reference
     route (shifted through the anchors the same way); elsewhere the OSM path is used if both anchors are within
     snap_max_m of it and it is not longer than the fibre by more than long_tol_m, unless it is > shortcut_over_m
     longer than the fibre while the straight line matches the fibre within shortcut_fit_m (the cable takes a
     shortcut); otherwise the straight line.
A hand-drawn route (e.g. digitised by the user on imagery) is not handled here: it overrides everything for its
stretch; give it to build_channel_map.py as a "path" or "ratio" piece, or as that segment's rows in the paths CSV.

    python3 road_path.py --config config.json --piece land --osm overpass.json [--reference ref_route.csv] \
        --out paths.csv [--report paths_report.json]

The OSM file is an Overpass JSON with way geometry, e.g. the query
    [out:json]; way["highway"](S,W,N,E); out geom;
(c) OpenStreetMap contributors, ODbL: credit it on figures and in the delivery. Requires networkx and scipy.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmap_geo import LocalXY, densify, hausdorff  # noqa: E402
import build_channel_map as BCM  # noqa: E402

FOOT = {"path", "footway", "steps", "pedestrian", "cycleway", "bridleway", "corridor"}
RULES = dict(snap_max_m=20.0, long_tol_m=25.0, same_road_m=25.0, shortcut_over_m=15.0, shortcut_fit_m=10.0,
             ref_tol_m=20.0, join_extra_m=5.0)


def plen(p):
    return float(np.sum(np.hypot(*np.diff(p, axis=0).T)))


def at_frac(p, f):
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    return np.stack([np.interp(f * s[-1], s, p[:, 0]), np.interp(f * s[-1], s, p[:, 1])], -1)


def through(p, pa, pb, step=2.0, half=2):
    """polyline p (from the road point nearest to anchor a to the one nearest to b) shifted sideways so that it
    passes through pa and pb; the signed offset (+ = left of the direction a -> b) changes linearly with arc
    length. Returns the path and the two offsets (NaN if p is degenerate: then the straight line)."""
    p = p[np.r_[True, np.hypot(*np.diff(p, axis=0).T) > 1e-6]]
    if len(p) < 2 or plen(p) < 1.0:
        return np.vstack([pa, pb]), np.nan, np.nan
    q = densify(p, step)
    i = np.arange(len(q))
    t = q[np.minimum(i + half, len(q) - 1)] - q[np.maximum(i - half, 0)]
    t /= np.hypot(t[:, 0], t[:, 1])[:, None]
    nrm = np.stack([-t[:, 1], t[:, 0]], -1)
    oa, ob = float((pa - q[0]) @ nrm[0]), float((pb - q[-1]) @ nrm[-1])
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(q, axis=0).T))]
    out = q + (oa + (ob - oa) * s / s[-1])[:, None] * nrm
    out[0], out[-1] = pa, pb
    return out, oa, ob


def azimuth(p, half=6):
    """local axial azimuth (deg, 0-180) over +-half points."""
    out = np.full(len(p), np.nan)
    if len(p) > 2 * half:
        d = p[2 * half:] - p[:-2 * half]
        out[half:-half] = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 180
    return out


class Net:
    """undirected graph of OSM ways (edge weight = length in m) with 1-m samples along every edge for snapping."""

    def __init__(self, ways, P):
        import networkx as nx
        from scipy.spatial import cKDTree
        self.nx = nx
        self.G, self.pos = nx.Graph(), {}
        for w in ways:
            for nd, g in zip(w["nodes"], w["geometry"]):
                self.pos[nd] = np.array(P.xy(g["lat"], g["lon"]), float)
            for u, v in zip(w["nodes"][:-1], w["nodes"][1:]):
                if u != v:
                    self.G.add_edge(u, v, w=float(np.hypot(*(self.pos[v] - self.pos[u]))))
        samp, self.owner = [], []
        for u, v, d in self.G.edges(data=True):
            t = np.linspace(0, 1, max(int(np.ceil(d["w"])), 1) + 1)
            samp.append(self.pos[u] + t[:, None] * (self.pos[v] - self.pos[u]))
            self.owner += [(u, v, ti) for ti in t]
        self.samp = np.vstack(samp) if samp else np.zeros((0, 2))
        self.tree = cKDTree(self.samp) if len(self.samp) else None

    def route(self, pa, pb, extra=5.0, kmax=6):
        """shortest leg + road + leg between anchors a and b; returns the road part and the two leg lengths."""
        if self.tree is None:
            return None, np.inf, np.inf
        G, ends, added = self.G, {}, []
        for tag, p in (("A", pa), ("B", pb)):
            d0, _ = self.tree.query(p)
            best = {}
            for k in self.tree.query_ball_point(p, d0 + extra):
                d = float(np.hypot(*(self.samp[k] - p)))
                e = self.owner[k][:2]
                if e not in best or d < best[e][0]:
                    best[e] = (d, k)
            ends[tag] = sorted(best.values())[:kmax]
            for j, (d, k) in enumerate(ends[tag]):
                u, v, t = self.owner[k]
                name = f"{tag}{j}"
                self.pos[name] = self.samp[k]
                G.add_edge(name, u, w=t * G[u][v]["w"])
                G.add_edge(name, v, w=(1 - t) * G[u][v]["w"])
                G.add_edge(tag, name, w=d)
                added.append(name)
        for i, (_, ka) in enumerate(ends["A"]):
            for j, (_, kb) in enumerate(ends["B"]):
                (ua, va, ta), (ub, vb, tb) = self.owner[ka], self.owner[kb]
                if (ua, va) == (ub, vb):
                    G.add_edge(f"A{i}", f"B{j}", w=abs(ta - tb) * G[ua][va]["w"])
        try:
            nodes = self.nx.shortest_path(G, "A", "B", weight="w")
        except self.nx.NetworkXNoPath:
            nodes = None
        G.remove_nodes_from(added + ["A", "B"])
        if nodes is None:
            return None, ends["A"][0][0], ends["B"][0][0]
        da, db = ends["A"][int(nodes[1][1:])][0], ends["B"][int(nodes[-2][1:])][0]
        return np.vstack([self.pos[nd] for nd in nodes[1:-1]]), da, db


def reference_part(pa, pb, ref, tol):
    """the reference route between its vertices nearest to a and b (a -> b order), or None if a or b is more than
    tol m from its nearest vertex."""
    da, db = np.hypot(*(ref - pa).T), np.hypot(*(ref - pb).T)
    ia, ib = int(np.argmin(da)), int(np.argmin(db))
    if da[ia] > tol or db[ib] > tol or ia == ib:
        return None
    part = ref[min(ia, ib):max(ia, ib) + 1]
    return part[::-1] if ia > ib else part


def build_paths(A, ways, ref, P, spacing, rules=RULES, ref_name="reference_route"):
    nets = dict(roads=Net([w for w in ways if w.get("tags", {}).get("highway") not in FOOT], P), all=Net(ways, P))
    rows, cands = [], []
    for i in range(len(A) - 1):
        a, b = A.iloc[i], A.iloc[i + 1]
        pa, pb = np.array(P.xy(a.lat, a.lon)), np.array(P.xy(b.lat, b.lon))
        F, Ls = (b.col - a.col) * spacing, float(np.hypot(*(pb - pa)))
        r = dict(seg=i, segment=f"{a['name']}-{b['name']}", col_from=a.col, col_to=b.col, fibre_m=F,
                 straight_len_m=Ls, osm_net="none")
        cand = dict(straight=np.vstack([pa, pb]))
        op = reference_part(pa, pb, ref, rules["ref_tol_m"]) if ref is not None else None
        if op is not None:
            cand["ref"], r["ref_off_a_m"], r["ref_off_b_m"] = through(op, pa, pb)
            r["ref_len_m"] = plen(cand["ref"])
        for name, net in nets.items():
            road, da, db = net.route(pa, pb, rules["join_extra_m"])
            r.update({f"{name}_snap_a_m": da, f"{name}_snap_b_m": db})
            if road is None:
                continue
            path, oa, ob = through(road, pa, pb)
            L = plen(path)
            r[f"{name}_len_m"] = L
            if "osm" in cand or max(da, db) > rules["snap_max_m"]:
                continue
            if op is not None:
                r[f"{name}_vs_ref_hausdorff_m"] = h = hausdorff(road, op)
                ok = h <= rules["same_road_m"]
            else:
                ok = L <= F + rules["long_tol_m"] and not (L - F > rules["shortcut_over_m"]
                                                           and abs(F - Ls) <= rules["shortcut_fit_m"])
            if ok:
                cand["osm"], r["osm_net"], r["osm_off_a_m"], r["osm_off_b_m"], r["osm_len_m"] = path, name, oa, ob, L
        r["path_source"] = "osm_road" if "osm" in cand else (ref_name if op is not None else "straight")
        key = dict(osm_road="osm", straight="straight").get(r["path_source"], "ref")
        r["path_len_m"] = plen(cand[key])
        r["fibre_minus_path_m"] = F - r["path_len_m"]
        rows.append(r)
        cands.append(cand)
    return pd.DataFrame(rows), cands


def check_paths(S, cands, half=6):
    """channel positions (uniform in channel) along the chosen path vs along the reference route and vs the
    straight line, on the segments the reference route covers: the size of the path-shape error."""
    cols, X = {}, {}
    have = [i for i, c in enumerate(cands) if "ref" in c and "osm" in c]   # OSM chosen where the reference is
    if not have:
        return {}
    for kind, order in dict(final=("osm", "ref", "straight"), ref=("ref",), straight=("straight",)).items():
        pts = []
        for i in have:
            c0, c1 = S.col_from[i], S.col_to[i]
            cc = np.arange(np.ceil(c0), np.ceil(c1))
            p = cands[i][next(k for k in order if k in cands[i])]
            pts.append(at_frac(p, (cc - c0) / (c1 - c0)))
            cols[i] = cc
        X[kind] = np.vstack(pts)
    out = {}
    for k in ("final", "straight"):
        d = np.hypot(*(X[k] - X["ref"]).T)
        da = np.abs((azimuth(X[k], half) - azimuth(X["ref"], half) + 90) % 180 - 90)
        da = da[np.isfinite(da)]
        out[f"{k}_vs_reference"] = dict(n_channels=len(d), median_m=float(np.median(d)),
                                        p90_m=float(np.percentile(d, 90)), max_m=float(d.max()),
                                        az_median_deg=float(np.median(da)) if len(da) else None)
    return out


def main():
    ap = argparse.ArgumentParser(description="OSM road paths between consecutive anchors, shifted through them.")
    ap.add_argument("--config", required=True, help="build_channel_map config (anchors, merging, fixes, spacing)")
    ap.add_argument("--piece", default="land", help="segment name of the anchored piece")
    ap.add_argument("--osm", required=True, help="Overpass JSON of highway ways with geometry")
    ap.add_argument("--reference", help="reference route CSV (lat, lon in route order), e.g. the operator route")
    ap.add_argument("--reference-name", default="reference_route", help="path_source label for it")
    ap.add_argument("--rules", help="JSON overriding " + ", ".join(RULES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    cfg = BCM.load_config(a.config)
    piece = next(p for p in cfg["pieces"] if p["type"] == "anchored" and p.get("segment") == a.piece)
    A = BCM.anchors_of(piece)
    P = BCM.frame(cfg)
    ways = [e for e in json.load(open(a.osm))["elements"] if e["type"] == "way" and len(e.get("nodes", [])) > 1]
    ref = None
    if a.reference:
        R = pd.read_csv(a.reference)
        ref = np.stack(P.xy(R.lat.to_numpy(), R.lon.to_numpy()), -1)
    rules = dict(RULES, **(json.loads(a.rules) if a.rules else {}))
    S, cands = build_paths(A, ways, ref, P, float(cfg["spacing_m"]), rules, a.reference_name)
    rows = []
    for i, cand in enumerate(cands):
        key = dict(osm_road="osm", straight="straight").get(S.path_source[i], "ref")
        la, lo = P.latlon(cand[key][:, 0], cand[key][:, 1])
        rows += [dict(seg=i, **{"from": A.name[i], "to": A.name[i + 1]}, col_from=S.col_from[i], col_to=S.col_to[i],
                      path_source=S.path_source[i], k=k, lat=x, lon=y) for k, (x, y) in enumerate(zip(la, lo))]
    pd.DataFrame(rows).to_csv(a.out, index=False, float_format="%.10g")
    rep = dict(rules=rules, n_ways=len(ways), segments=S.round(3).to_dict("records"),
               by_path=S.path_source.value_counts().to_dict(), check=check_paths(S, cands))
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=1, default=float)
    pd.set_option("display.width", 220)
    cols = [c for c in ["segment", "fibre_m", "straight_len_m", "ref_len_m", "roads_len_m", "roads_snap_a_m",
                        "roads_snap_b_m", "osm_off_a_m", "osm_off_b_m", "roads_vs_ref_hausdorff_m", "path_source",
                        "fibre_minus_path_m"] if c in S]
    print(S[cols].round(1).to_string(index=False))
    print(json.dumps(dict(by_path=rep["by_path"], check=rep["check"]), indent=1))


if __name__ == "__main__":
    main()
