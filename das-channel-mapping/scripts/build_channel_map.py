#!/usr/bin/env python3
"""Build a DAS channel map (channel -> lat, lon, position uncertainty) from a JSON configuration.

The map is a sequence of pieces along the fibre. Each piece covers a range of channel numbers "cols": [lo, hi]
(lo <= c < hi; "include_end": true also takes c == hi; the last piece and anchored pieces include their end by
default; earlier pieces win ties) and places its channels by one rule:

  point     every channel at one point: fibre inside the interrogator, a coil in a manhole, a reel in a cabin
  line      uniform in channel along the straight line "from" -> "to" (tied to channels "ends", default cols)
  path      uniform in channel along a polyline whose two ends are tied to (fractional) channels "ends", e.g. the
            submarine route stretched between the two waterlines found from ocean-wave loading
  anchored  a run of anchors (channel picked from a hammer / tap test + GPS point of the blow). Between two
            consecutive anchors: along the given path (default the straight line), uniform in channel, except
            slack blocks: every channel of a block sits at ONE point of the path (at "at_fraction" of the path
            or "at_m" from the first anchor, else where the rest of the segment is uniform in channel); the
            channels before and after a block are uniform in channel on their own stretch
  ratio     from "start_col" along a route with a fibre / path ratio, for a stretch no data tie to the map; the
            ratio is a number or "anchored" = (fibre - located slack) / path summed over the anchored segments
            (segments with more than max_excess_rest_m of unexplained extra fibre are left out)

Every position is the CENTRE of the channel's gauge. A hammer anchor is the channel whose gauge is centred on
the blow, so anchored pieces satisfy this automatically; tie waterlines and other features the same way.

Uncertainty (pos_unc_m, ~1 sigma): a piece's "unc_m" or "unc_rules" [{"max_col": c, "unc_m": u}, ..., {"unc_m":
u}] (the first rule with channel <= max_col wins). Anchored segments: base (road_m on a path, straight_m on a
straight line) + excess_factor * |fibre - block fibre - path length|; channels of a block: base + located_m if the
block's point is given (measured, e.g. by vehicles), else base + excess_factor * block fibre.

    python3 build_channel_map.py config.json --out results/ [--prefix channel_map] [--compare old_map.csv]

Writes <prefix>_<table>.csv (one per entry of "tables", default one <prefix>.csv), <prefix>_summary.json,
<prefix>_segments.csv (fibre and ground length per segment label) and <prefix>_anchored_segments.csv (one row per
pair of consecutive anchors). Relative file names in the config are relative to the config file.
See references/placement.md and assets/config_template.json.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmap_geo import LocalXY, arclength, read_polyline, strike  # noqa: E402

UNC_DEFAULT = dict(road_m=5.0, straight_m=10.0, located_m=5.0, excess_factor=0.5)
FMT = "%.10g"                     # 8 decimals for lat / lon: never round positions to ~1 m in a CSV


# ----------------------------------------------------------------------------------------------------- inputs
def read_anchors(spec):
    """anchors as a DataFrame (name, col, lat, lon, ...) sorted by col; spec = CSV path or list of dicts."""
    A = pd.DataFrame(spec) if isinstance(spec, list) else pd.read_csv(spec)
    need = {"name", "col", "lat", "lon"}
    if not need <= set(A.columns):
        raise ValueError(f"anchors need columns {sorted(need)}, got {list(A.columns)}")
    A = A.copy()
    A["name"] = A["name"].astype(str)
    return A.sort_values("col").reset_index(drop=True)


def merge_close(A, within):
    """anchors picked within `within` channels of each other (two hammers on the same channel) become one anchor
    at their mean channel and mean GPS point; names joined with '+'."""
    if within is None or len(A) < 2:
        return A
    key = np.r_[0, np.cumsum(np.diff(A.col.to_numpy()) > within)]
    agg = {c: "mean" for c in A.columns if c != "name" and pd.api.types.is_numeric_dtype(A[c])}
    agg["name"] = lambda s: "+".join(sorted(s, key=lambda v: (len(v), v)))
    return A.groupby(key).agg(agg).sort_values("col").reset_index(drop=True)


def anchors_of(piece):
    """the anchors of an anchored piece after merging and the manual fixes (col_pick keeps the pick)."""
    A = merge_close(read_anchors(piece["anchors"]), piece.get("merge_within_cols", 0.5))
    A["col_pick"] = A["col"]
    for name, col in (piece.get("anchor_fix") or {}).items():
        if name not in set(A.name):
            raise ValueError(f"anchor_fix: no anchor named {name} (anchors: {A.name.tolist()})")
        A.loc[A.name == name, "col"] = float(col)
    A = A.sort_values("col").reset_index(drop=True)
    if np.any(np.diff(A.col) <= 0):
        raise ValueError("anchor channels must increase strictly after merging / fixes")
    return A


def unc_from_rules(c, piece):
    rules = piece.get("unc_rules")
    if not rules:
        u = piece.get("unc_m")
        return np.full(len(c), np.nan if u is None else float(u))
    out, todo = np.full(len(c), np.nan), np.ones(len(c), bool)
    for r in rules:
        m = todo & (c <= r["max_col"]) if "max_col" in r else todo.copy()
        out[m] = np.nan if r.get("unc_m") is None else float(r["unc_m"])
        todo &= ~m
    return out


# ---------------------------------------------------------------------------------------- anchored segments
def block_fractions(a, b, blocks, plen):
    """fractions of the path length at the knots (a, k1, k2, ..., b) of one anchored segment. A block without a
    given point gets the fraction at which the rest of the segment is uniform in channel between the nearest
    knots whose fraction is known."""
    cols, fr = [a], [0.0]
    for k in blocks:
        f = k.get("at_fraction")
        if f is None and k.get("at_m") is not None:
            f = float(k["at_m"]) / plen
        cols += [k["k1"], k["k2"]]
        fr += [f, f]
    cols.append(b)
    fr.append(1.0)
    cols = np.asarray(cols, float)
    fr = np.array([np.nan if v is None else float(v) for v in fr])
    inblock = np.zeros(len(cols) - 1, bool)
    inblock[1::2] = True                                  # interval k1 -> k2 of every block
    u = np.r_[0.0, np.cumsum(np.where(inblock, 0.0, np.diff(cols)))]   # non-block channels counted from a
    known = np.flatnonzero(np.isfinite(fr))
    for i in np.flatnonzero(~np.isfinite(fr)):
        L, R = known[known < i].max(), known[known > i].min()
        fr[i] = fr[L] + (fr[R] - fr[L]) * (u[i] - u[L]) / max(u[R] - u[L], 1e-12)
    if np.any(np.diff(fr) < -1e-9) or fr.min() < -1e-9 or fr.max() > 1 + 1e-9:
        raise ValueError(f"slack blocks of segment {a:.2f}-{b:.2f} are out of order along the path: {fr}")
    return cols, fr


def place_anchored(c, piece, P, spacing):
    """positions of channels c (any fractional values inside the piece) and one row per anchored segment."""
    A = anchors_of(piece)
    paths = pd.read_csv(piece["paths"]) if piece.get("paths") else None
    unc = dict(UNC_DEFAULT, **(piece.get("unc") or {}))
    by_seg = {}
    for k in piece.get("slack", []):
        key = k["between"] if isinstance(k["between"], str) else "-".join(map(str, k["between"]))
        k1, k2 = map(float, k["cols"])
        by_seg.setdefault(key, []).append(dict(k, k1=k1, k2=k2))
    n = len(c)
    lat, lon, u = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    src, slack = np.full(n, "", dtype=object), np.full(n, "", dtype=object)
    rows, used = [], set()
    for i in range(len(A) - 1):
        a, b = A.iloc[i], A.iloc[i + 1]
        key = f"{a['name']}-{b['name']}"
        m = (c >= a.col) & ((c <= b.col) if i == len(A) - 2 else (c < b.col))
        how, plat, plon = "straight", np.array([a.lat, b.lat]), np.array([a.lon, b.lon])
        if paths is not None:
            g = paths[paths.seg == i] if "seg" in paths else \
                paths[(paths["from"].astype(str) == a["name"]) & (paths["to"].astype(str) == b["name"])]
            if len(g):
                if "col_from" in g and (abs(g.col_from.iloc[0] - a.col) > 1e-3 or abs(g.col_to.iloc[0] - b.col) > 1e-3):
                    raise ValueError(f"the path of segment {i} ({key}) was built for anchors at "
                                     f"{g.col_from.iloc[0]:.3f}-{g.col_to.iloc[0]:.3f}, not {a.col:.3f}-{b.col:.3f}: "
                                     "rebuild the paths after changing anchors")
                g = g.sort_values("k") if "k" in g else g
                plat, plon = g.lat.to_numpy(float), g.lon.to_numpy(float)
                how = str(g.path_source.iloc[0] if "path_source" in g else g.path.iloc[0])
        x, y = P.xy(plat, plon)
        s = arclength(x, y)
        plen = float(s[-1])
        blocks = sorted(by_seg.get(key, []), key=lambda k: k["k1"])
        if blocks:
            used.add(key)
        for k in blocks:
            if not (a.col <= k["k1"] < k["k2"] <= b.col):
                raise ValueError(f"slack block {k['cols']} is not inside segment {key} ({a.col:.2f}-{b.col:.2f})")
        kc, kf = block_fractions(a.col, b.col, blocks, plen)
        f = np.interp(c[m], kc, kf)
        lat[m], lon[m] = P.latlon(np.interp(f * plen, s, x), np.interp(f * plen, s, y))
        fibre = (b.col - a.col) * spacing
        sl = sum((k["k2"] - k["k1"]) * spacing for k in blocks)
        u0 = unc["straight_m"] if how == "straight" else unc["road_m"]
        useg = u0 + unc["excess_factor"] * abs(fibre - sl - plen)
        uu = np.full(int(m.sum()), useg)
        kind = np.full(int(m.sum()), "", dtype=object)
        located = [k.get("at_fraction") is not None or k.get("at_m") is not None for k in blocks]
        for k, loc in zip(blocks, located):
            ins = (c[m] >= k["k1"]) & (c[m] <= k["k2"])
            uu[ins] = u0 + (unc["located_m"] if loc else unc["excess_factor"] * (k["k2"] - k["k1"]) * spacing)
            kind[ins] = k.get("kind", "slack")
        src[m], slack[m], u[m] = how, kind, uu
        rows.append(dict(segment=key, col_from=a.col, col_to=b.col, path_source=how, path_len_m=plen,
                         fibre_m=fibre, excess_m=fibre - plen,
                         slack_cols=";".join(f"{k['k1']:g}-{k['k2']:g}" for k in blocks),
                         slack_kind=";".join(k.get("kind", "slack") for k in blocks), slack_m=sl,
                         excess_rest_m=fibre - sl - plen,
                         slack_at_m=";".join(f"{kf[1 + 2 * j] * plen:.3f}" for j in range(len(blocks))),
                         slack_placed_by=";".join(k.get("placed_by", "given") if loc else "uniform_rest"
                                                  for k, loc in zip(blocks, located)),
                         pos_unc_m=useg))
    missing = set(by_seg) - used
    if missing:
        raise ValueError(f"slack blocks name segments that do not exist: {sorted(missing)}; the segments are "
                         f"{[r['segment'] for r in rows]}")
    return lat, lon, src, slack, u, rows, A


# ------------------------------------------------------------------------------------------------- building
def piece_range(p):
    if "cols" in p:
        return float(p["cols"][0]), float(p["cols"][1])
    if p["type"] == "anchored":
        A = anchors_of(p)
        return float(A.col.iloc[0]), float(A.col.iloc[-1])
    raise ValueError(f"piece {p.get('segment')} needs 'cols'")


def frame(cfg):
    pr = cfg.get("projection") or {}
    if "lat0" in pr:
        return LocalXY(pr["lat0"], pr["lon0"], pr.get("kx"), pr.get("ky"))
    q = []
    for p in cfg["pieces"]:
        q += [tuple(p[k]) for k in ("at", "from", "to") if k in p]
        if p["type"] == "anchored":
            A = read_anchors(p["anchors"])
            q += list(zip(A.lat, A.lon))
        elif p["type"] in ("path", "ratio"):
            q += list(zip(*read_polyline(p["route"])))
    q = np.array(q, float)
    return LocalXY.around(q[:, 0], q[:, 1], kx=pr.get("kx"), ky=pr.get("ky"))


def place(p, cq, P, spacing, S=None):
    """(lat, lon, path_source, slack, unc, info) for the columns cq of piece p."""
    t, n = p["type"], len(cq)
    lo, hi = piece_range(p)
    src = np.full(n, p.get("path_source", t), dtype=object)
    slack = np.full(n, p.get("slack_label", ""), dtype=object)
    info = {}
    if t == "point":
        lat, lon = np.full(n, float(p["at"][0])), np.full(n, float(p["at"][1]))
        info = dict(ground_m=0.0)
    elif t == "line":
        e0, e1 = map(float, p.get("ends", (lo, hi)))
        f = (cq - e0) / (e1 - e0)
        lat = p["from"][0] + f * (p["to"][0] - p["from"][0])
        lon = p["from"][1] + f * (p["to"][1] - p["from"][1])
        info = dict(ground_m=float(P.dist(lat[0], lon[0], lat[-1], lon[-1])))
    elif t == "path":
        x, y = P.xy(*read_polyline(p["route"]))
        s = arclength(x, y)
        e0, e1 = map(float, p.get("ends", (lo, hi)))
        q = (cq - e0) / (e1 - e0) * s[-1]
        lat, lon = P.latlon(np.interp(q, s, x), np.interp(q, s, y))
        info = dict(route_m=float(s[-1]), fibre_m=(e1 - e0) * spacing, fibre_over_route=(e1 - e0) * spacing / s[-1],
                    ends=[e0, e1], ground_m=float(np.clip(q[-1], 0, s[-1]) - np.clip(q[0], 0, s[-1])))
    elif t == "anchored":
        lat, lon, src, slack, u, rows, A = place_anchored(cq, p, P, spacing)
        return lat, lon, src, slack, u, dict(rows=rows, anchors=A, ground_m=float(sum(r["path_len_m"] for r in rows)))
    elif t == "ratio":
        r, left_out = p.get("ratio", "anchored"), []
        if r == "anchored":
            if S is None or not len(S):
                raise ValueError("ratio 'anchored' needs an anchored piece before it is placed")
            ok = (S.excess_rest_m <= float(p.get("max_excess_rest_m", 100.0))).to_numpy()
            r = float((S.fibre_m - S.slack_m)[ok].sum() / S.path_len_m[ok].sum())
            left_out = S.segment[~ok].tolist()
        r = float(r)
        x, y = P.xy(*read_polyline(p["route"]))
        s = arclength(x, y)
        c0, s0 = float(p["start_col"]), float(p.get("s0_m", 0.0))
        sq = s0 + (cq - c0) * spacing / r
        info = dict(fibre_over_path=r, segments_left_out=left_out, route_m=float(s[-1]),
                    channels_beyond_route_end=int((sq > s[-1] + 1e-9).sum()),
                    feature_cols={k: float(c0 + (v - s0) * r / spacing) for k, v in (p.get("features") or {}).items()})
        if p.get("cap_at_route_end", True):
            sq = np.minimum(sq, s[-1])
        info["_s"] = sq
        info["ground_m"] = float(sq[-1] - sq[0])
        lat, lon = P.latlon(np.interp(sq, s, x), np.interp(sq, s, y))
    else:
        raise ValueError(f"unknown piece type {t}")
    return lat, lon, src, slack, unc_from_rules(cq, p), info


def build(cfg):
    n, spacing = int(cfg["n_channels"]), float(cfg["spacing_m"])
    c = np.arange(n, dtype=float)
    P = frame(cfg)
    lat, lon, unc = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    seg, src, slack = (np.full(n, "", dtype=object) for _ in range(3))
    owner, strike_ok = np.full(n, -1), np.zeros(n, bool)
    pieces = cfg["pieces"]
    masks = []
    for ip, p in enumerate(pieces):                       # which channels each piece owns
        lo, hi = piece_range(p)
        inc = p.get("include_end", ip == len(pieces) - 1 or p["type"] == "anchored")
        m = (owner < 0) & (c >= lo) & ((c <= hi) if inc else (c < hi))
        owner[m] = ip
        masks.append((m, lo, hi))
    if (owner < 0).any():
        gaps = c[owner < 0].astype(int)
        raise ValueError(f"{len(gaps)} channels belong to no piece, e.g. {gaps[:10].tolist()}")
    S, A, info_by_piece, ground = pd.DataFrame(), None, {}, {}
    order = [i for i, p in enumerate(pieces) if p["type"] != "ratio"] + \
            [i for i, p in enumerate(pieces) if p["type"] == "ratio"]     # ratio pieces need the anchored ratio
    for ip in order:
        p, (m, lo, hi) = pieces[ip], masks[ip]
        cq = np.r_[lo, c[m], hi]                          # the piece's boundaries too, for its ground length
        la, lo_, sr, sk, uu, info = place(p, cq, P, spacing, S)
        lat[m], lon[m], src[m], slack[m], unc[m] = la[1:-1], lo_[1:-1], sr[1:-1], sk[1:-1], uu[1:-1]
        seg[m] = p.get("segment", p["type"])
        strike_ok[m] = p.get("strike", p["type"] != "point")
        ground[ip] = info.pop("ground_m")
        if p["type"] == "anchored":
            S, A = pd.DataFrame(info["rows"]), info["anchors"]
        else:
            if p["type"] == "ratio":
                sq = info.pop("_s")
                info.update(s_last_col_m=float(sq[-2]), route_left_after_last_col_m=float(info["route_m"] - sq[-2]))
            info_by_piece[ip] = info
    x, y = P.xy(lat, lon)
    s_path = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    st = cfg.get("strike") or {}
    valid = strike_ok & ((slack == "") | (not st.get("exclude_slack", True)))
    stk = strike(x, y, valid, int(st.get("half", 6)), float(st.get("min_chord_m", 20.0)))
    T = pd.DataFrame(dict(raw_col=c.astype(int)))
    for tb in cfg.get("tables", []):
        if tb.get("index_column"):
            step, off = int(tb["step"]), int(tb.get("offset", 0))
            T[tb["index_column"]] = np.where((c - off) % step == 0, (c - off) // step, -1).astype(int)
    lab = cfg.get("label")
    if lab:
        T[lab.get("column", "label_m")] = float(lab["offset_m"]) + float(lab["step_m"]) * c
    T[cfg.get("distance_column", "dist_m")] = float(cfg.get("first_channel_distance_m", 0.0)) + spacing * c
    T["segment"], T["path_source"], T["slack"] = seg, src, slack
    T["lat"], T["lon"], T["s_path_m"], T["strike_deg"], T["pos_unc_m"] = lat, lon, s_path, stk, unc
    rows = []                                             # per segment label
    for sg in pd.unique(seg):
        ips = [ip for ip, p in enumerate(pieces) if p.get("segment", p["type"]) == sg]
        fib = sum((masks[ip][2] - masks[ip][1]) * spacing for ip in ips)
        gr = sum(ground[ip] for ip in ips)
        g = T[T.segment == sg]
        rows.append(dict(segment=sg, path_source="/".join(pd.unique(g.path_source)),
                         raw_col_first=int(g.raw_col.min()), raw_col_last=int(g.raw_col.max()), n_channels=len(g),
                         col_from=min(masks[ip][1] for ip in ips), col_to=max(masks[ip][2] for ip in ips),
                         fibre_m=fib, ground_m=gr, fibre_over_ground=fib / gr if gr > 0 else np.nan,
                         pos_unc_min_m=g.pos_unc_m.min(), pos_unc_median_m=g.pos_unc_m.median(),
                         pos_unc_max_m=g.pos_unc_m.max()))
    G = pd.DataFrame(rows)
    summary = dict(name=cfg.get("name", ""), n_channels=n, spacing_m=spacing,
                   projection=dict(lat0=P.lat0, lon0=P.lon0, kx=P.kx, ky=P.ky),
                   segments=G.to_dict("records"),
                   pieces={pieces[ip].get("segment", str(ip)): v for ip, v in info_by_piece.items()})
    if len(S):
        summary["anchored"] = dict(
            n_anchors=len(A), n_segments=len(S), by_path=S.path_source.value_counts().to_dict(),
            anchor_fix={r["name"]: dict(col_pick=r["col_pick"], col=r["col"]) for r in A.to_dict("records")
                        if abs(r["col"] - r["col_pick"]) > 1e-9},
            merged=[r for r in A.name if "+" in r],
            anchors=A[["name", "col", "col_pick", "lat", "lon"]].to_dict("records"),
            slack_blocks=S[S.slack_cols != ""][["segment", "slack_cols", "slack_kind", "slack_m", "excess_m",
                                                 "excess_rest_m", "slack_at_m", "slack_placed_by"]].to_dict("records"))
    return T, S, G, summary


def compare(T, old_path):
    """how far every channel moved relative to an earlier map with the same channel numbering."""
    O = pd.read_csv(old_path).set_index("raw_col").reindex(T.raw_col)
    P = LocalXY.around(T.lat, T.lon)
    d = P.dist(O.lat.to_numpy(), O.lon.to_numpy(), T.lat.to_numpy(), T.lon.to_numpy())
    out = dict(against=os.path.basename(old_path), n_compared=int(np.isfinite(d).sum()),
               moved_gt_0p5_m=int((d > 0.5).sum()), moved_gt_10_m=int((d > 10).sum()),
               max_m=float(np.nanmax(d)), max_at_col=int(T.raw_col.iloc[int(np.nanargmax(d))]), by_segment={})
    for sg in pd.unique(T.segment):
        q = d[(T.segment == sg).to_numpy()]
        q = q[np.isfinite(q)]
        if len(q):
            out["by_segment"][sg] = dict(n_gt_0p5_m=int((q > 0.5).sum()), max_m=float(q.max()),
                                         median_m=float(np.median(q)))
    return out, d


def load_config(path):
    cfg = json.load(open(path))
    base = os.path.dirname(os.path.abspath(path))
    for p in cfg["pieces"]:
        for k in ("anchors", "paths", "route"):
            if isinstance(p.get(k), str) and not os.path.isabs(p[k].split("?")[0]):
                p[k] = os.path.join(base, p[k])
    return cfg


def write(T, S, G, summary, cfg, out, prefix):
    os.makedirs(out, exist_ok=True)
    for tb in cfg.get("tables") or [dict(name="", step=1)]:
        step, off = int(tb.get("step", 1)), int(tb.get("offset", 0))
        name = f"{prefix}_{tb['name']}.csv" if tb.get("name") else f"{prefix}.csv"
        T[(T.raw_col - off) % step == 0].to_csv(os.path.join(out, name), index=False, float_format=FMT)
    G.to_csv(os.path.join(out, f"{prefix}_segments.csv"), index=False, float_format="%.6g")
    if len(S):
        S.to_csv(os.path.join(out, f"{prefix}_anchored_segments.csv"), index=False, float_format="%.6g")
    json.dump(summary, open(os.path.join(out, f"{prefix}_summary.json"), "w"), indent=1,
              default=lambda v: v.item() if hasattr(v, "item") else str(v))


def main():
    ap = argparse.ArgumentParser(description="Build a DAS channel map from a JSON configuration.")
    ap.add_argument("config")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="channel_map")
    ap.add_argument("--compare", help="earlier channel map CSV (raw_col, lat, lon): report how far channels moved")
    a = ap.parse_args()
    cfg = load_config(a.config)
    T, S, G, summary = build(cfg)
    if a.compare:
        summary["compare"], _ = compare(T, a.compare)
    write(T, S, G, summary, cfg, a.out, a.prefix)
    pd.set_option("display.width", 220)
    print(G.round(2).to_string(index=False))
    print(json.dumps(summary["pieces"], indent=1))
    if a.compare:
        print("compare:", json.dumps(summary["compare"], indent=1))


if __name__ == "__main__":
    main()
