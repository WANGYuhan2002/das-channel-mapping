#!/usr/bin/env python3
"""Delivery package of a channel map: data dictionary, slack inventory, per-channel change table, GIS files,
md5 manifest. Reads the outputs of build_channel_map.py; never edits them.

  dictionary  one row per column of the channel table (and of the anchored-segment table): unit, dtype, number of
              empty cells, meaning, how it is computed, when it is empty. Standard columns are described here;
              project-specific ones come from --extra (JSON {column: {unit, meaning, how, empty}}).
  slack       every slack block in the map (channel range, fibre, point, uncertainty, what placed it, fibre - road
              before and after the block) and the segments whose extra fibre is spread evenly
  change      how far every channel moved between two map versions, split along / across the new path
  gis         GeoJSON (one Point per channel, properties = table columns, [lon, lat] per RFC 7946), a feature
              file (segment lines, anchors, slack blocks, extra points such as waterlines) and a KML for Google Earth
  manifest    md5sums.txt (GNU format, paths relative to the folder) of every file of a delivery folder

    python3 make_delivery.py dictionary --map out/channel_map_8m.csv [--segments out/channel_map_anchored_segments.csv] \
        [--extra extra_columns.json] --out delivery/data_dictionary.csv
    python3 make_delivery.py slack --map out/channel_map_8m.csv --segments out/channel_map_anchored_segments.csv \
        --spacing 8.1676 --out delivery/slack_inventory.csv
    python3 make_delivery.py change --old old_map.csv --new out/channel_map_8m.csv --out delivery/map_change.csv
    python3 make_delivery.py gis --map out/channel_map_8m.csv [--summary out/channel_map_summary.json] \
        [--points extra_points.json] --name "my cable" --out delivery/
    python3 make_delivery.py manifest --dir delivery/
"""
import argparse
import hashlib
import json
import math
import os
import pathlib
import sys
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmap_geo import LocalXY  # noqa: E402

STD = {
    "raw_col": ("-", "channel index c of the recorded data (0 .. n-1)", "column number", "never"),
    "sorted_j": ("-", "index of a decimated product (e.g. every 2nd channel)", "j = (c - offset) / step for the kept "
                 "channels, -1 otherwise", "-1 for channels not in that product"),
    "fo_nom_m": ("m", "nominal along-fibre LABEL used by earlier projects", "offset + step x c; a label, not a fibre "
                 "length", "never"),
    "label_m": ("m", "nominal along-fibre label", "offset + step x c", "never"),
    "dist_header_m": ("m", "true along-fibre distance from the file header", "start distance + c x spacing (spacing "
                      "= nominal x fibre-length multiplier)", "never; negative inside the interrogator"),
    "dist_m": ("m", "true along-fibre distance", "first-channel distance + c x spacing", "never"),
    "segment": ("-", "part of the cable (e.g. internal, cabin, land, coil, beach, sea)", "piece of the build config",
                "never"),
    "path_source": ("-", "where the position comes from (point, straight line, road path, operator route, stretched "
                    "route, hand-drawn route, ratio)", "piece / segment path", "never"),
    "slack": ("-", "slack block the channel belongs to (kind); every channel of a block sits at ONE point, so they "
              "are not a line array", "slack blocks of the config", "not slack"),
    "lat": ("deg N", "latitude (WGS84) of the centre of the channel's gauge", "placement rules", "never"),
    "lon": ("deg E", "longitude (WGS84) of the centre of the channel's gauge", "placement rules", "never"),
    "s_path_m": ("m", "ground length along the mapped path from channel 0", "sum of distances between consecutive "
                 "channel positions; does not grow inside a slack block", "never"),
    "strike_deg": ("deg", "local strike, clockwise from north (0-360)", "azimuth of the chord from channel c-h to c+h",
                   "points, slack blocks, chords shorter than the minimum, the ends"),
    "pos_unc_m": ("m", "position uncertainty (~1 sigma)", "rules of references/uncertainty.md", "where no rule "
                  "applies (e.g. inside the interrogator)"),
    "elev_m": ("m", "ground elevation (land) or seafloor elevation (sea, negative below sea level)", "bilinear in "
               "the DEM / bathymetry grid at the channel position", "outside the grids"),
    "elev_src": ("-", "elevation source", "-", "outside the grids"),
    "elev_unc_m": ("m", "elevation uncertainty from the position uncertainty", "std of the grid within pos_unc_m",
                   "outside the grids"),
}
STD_SEG = {
    "segment": ("-", "the two anchors of the segment, e.g. 14-15 (merged anchors joined with +)", "-", "never"),
    "col_from": ("-", "channel of the first anchor (fractional)", "pick, or anchor fix", "never"),
    "col_to": ("-", "channel of the second anchor; channels col_from <= c < col_to belong to the segment", "-", "never"),
    "path_source": ("-", "path between the anchors", "road_path.py choice", "never"),
    "path_len_m": ("m", "ground length of the path between the two anchor points", "along the path", "never"),
    "fibre_m": ("m", "fibre between the two anchors", "(col_to - col_from) x spacing", "never"),
    "excess_m": ("m", "fibre - path", "-", "never"),
    "slack_cols": ("-", "slack block edges (fractional channels)", "config", "no block"),
    "slack_kind": ("-", "kind of block", "config", "no block"),
    "slack_m": ("m", "fibre in the blocks", "(k2 - k1) x spacing", "0 without a block"),
    "excess_rest_m": ("m", "fibre - blocks - path: spread evenly; negative = fibre shorter than the road", "-", "never"),
    "slack_at_m": ("m", "block point along the path from the first anchor", "given or uniform rest", "no block"),
    "slack_placed_by": ("-", "what placed the block (e.g. vehicles; uniform_rest)", "config", "no block"),
    "pos_unc_m": ("m", "uncertainty of the channels outside the blocks", "base + factor x |excess_rest_m|", "never"),
}


def dictionary(T, name, std, extra):
    rows = []
    for c in T.columns:
        unit, mean, how, empty = (extra.get(c) or {}).get("unit"), None, None, None
        if c in extra:
            e = extra[c]
            unit, mean, how, empty = e.get("unit", "-"), e.get("meaning", ""), e.get("how", ""), e.get("empty", "")
        elif c in std:
            unit, mean, how, empty = std[c]
        else:
            unit, mean, how, empty = "?", "(describe in --extra)", "", ""
        v = T[c]
        n_empty = int(v.isna().sum() + ((v.astype(str) == "") & v.notna()).sum())
        rows.append(dict(table=name, column=c, unit=unit, dtype=str(v.dtype), n_empty=n_empty, meaning=mean,
                         how_computed=how, empty_where=empty))
    return rows


def slack_inventory(T, S, spacing):
    rows = []
    sp = T.slack.fillna("").astype(str)
    for kind in sorted(set(sp) - {""}):
        m = (sp == kind).to_numpy()
        lab = np.cumsum(np.r_[True, np.diff(np.flatnonzero(m)) > 1])     # contiguous runs
        for k in np.unique(lab):
            idx = np.flatnonzero(m)[lab == k]
            g = T.iloc[idx]
            rec = dict(slack=kind, raw_col_first=int(g.raw_col.min()), raw_col_last=int(g.raw_col.max()),
                       n_channels=len(g), lat=float(g.lat.mean()), lon=float(g.lon.mean()),
                       spread_m=float(LocalXY.around(g.lat, g.lon).dist(g.lat.min(), g.lon.min(), g.lat.max(),
                                                                         g.lon.max())),
                       pos_unc_m=float(g.pos_unc_m.median()), segment=str(g.segment.iloc[0]))
            if S is not None and len(S):
                q = S[(S.col_from <= g.raw_col.min()) & (S.col_to >= g.raw_col.max())]
                if len(q):
                    r = q.iloc[0]
                    blocks = [tuple(map(float, x.split("-"))) for x in str(r.slack_cols).split(";") if x]
                    ats = [float(x) for x in str(r.slack_at_m).split(";") if x]
                    bys = str(r.slack_placed_by).split(";")
                    for j, (k1, k2) in enumerate(blocks):
                        if k1 <= g.raw_col.min() and k2 >= g.raw_col.max():
                            n_before = k1 - r.col_from
                            n_after = r.col_to - k2
                            rec.update(anchored_segment=r.segment, block_cols=f"{k1:g}-{k2:g}",
                                       block_fibre_m=(k2 - k1) * spacing, at_m_from_first_anchor=ats[j],
                                       placed_by=bys[j], segment_path_m=r.path_len_m, segment_excess_m=r.excess_m,
                                       excess_rest_m=r.excess_rest_m,
                                       uniform_rest_at_m=r.path_len_m * n_before / (n_before + n_after),
                                       fibre_minus_road_before_m=(n_before * spacing - ats[j]) if len(blocks) == 1 else np.nan,
                                       fibre_minus_road_after_m=(n_after * spacing - (r.path_len_m - ats[j])) if len(blocks) == 1 else np.nan)
            rows.append(rec)
    if S is not None and len(S):
        spread = S[S.slack_cols.fillna("") == ""]
        rows.append(dict(slack="(spread evenly)", segment="anchored segments without a block",
                         n_channels=int(sum(np.floor(spread.col_to) - np.ceil(spread.col_from) + 1)),
                         segment_excess_m=float(spread.excess_m.sum()),
                         excess_rest_m=float(spread.excess_m.sum()),
                         note=f"{len(spread)} segments, fibre - path {spread.excess_m.min():.1f} .. {spread.excess_m.max():.1f} m"))
    return pd.DataFrame(rows)


def change_table(O, N):
    O = O.set_index("raw_col").reindex(N.raw_col)
    P = LocalXY.around(N.lat, N.lon)
    ox, oy = P.xy(O.lat.to_numpy(), O.lon.to_numpy())
    nx_, ny = P.xy(N.lat.to_numpy(), N.lon.to_numpy())
    ex, ey = ox - nx_, oy - ny
    st = np.radians(N.strike_deg.to_numpy()) if "strike_deg" in N else np.full(len(N), np.nan)
    tx, ty = np.sin(st), np.cos(st)
    out = pd.DataFrame(dict(raw_col=N.raw_col, segment=N.segment, old_lat=O.lat.to_numpy(), old_lon=O.lon.to_numpy(),
                            new_lat=N.lat, new_lon=N.lon, move_m=np.hypot(ex, ey), move_along_m=ex * tx + ey * ty,
                            move_cross_m=-ex * ty + ey * tx))
    for c in ("slack", "pos_unc_m"):
        if c in N:
            out[f"new_{c}"] = N[c].to_numpy()
        if c in O:
            out[f"old_{c}"] = O[c].to_numpy()
    return out


def clean(v):
    if isinstance(v, (float, np.floating)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, str) and v == "":
        return None
    return v


def channel_fc(T, name):
    feats = []
    for r in T.to_dict("records"):
        p = {k: clean(v) for k, v in r.items() if k not in ("lat", "lon")}
        feats.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[float(r["lon"]), float(r["lat"])]),
                          properties=p))
    return dict(type="FeatureCollection", name=name, features=feats)


def cable_features(T, summary, points):
    out = []
    for sg in pd.unique(T.segment):
        g = T[T.segment == sg]
        nxt = T[T.raw_col == g.raw_col.max() + 1]
        lon = np.r_[g.lon.to_numpy(), nxt.lon.to_numpy()]
        lat = np.r_[g.lat.to_numpy(), nxt.lat.to_numpy()]
        keep = np.r_[True, (np.diff(lon) != 0) | (np.diff(lat) != 0)]
        coords = [[float(a), float(b)] for a, b in zip(lon[keep], lat[keep])]
        if len(coords) < 2:
            coords = coords * 2
        out.append(dict(geom=dict(type="LineString", coordinates=coords),
                        props=dict(kind="segment", segment=sg, raw_col_first=int(g.raw_col.min()),
                                   raw_col_last=int(g.raw_col.max()), pos_unc_min_m=clean(g.pos_unc_m.min()),
                                   pos_unc_max_m=clean(g.pos_unc_m.max()))))
    for r in (summary or {}).get("anchored", {}).get("anchors", []):
        out.append(dict(geom=dict(type="Point", coordinates=[float(r["lon"]), float(r["lat"])]),
                        props=dict(kind="anchor", label=f"anchor {r['name']}", name=r["name"], raw_col=clean(r["col"]))))
    sp = T.slack.fillna("").astype(str)
    for kind in sorted(set(sp) - {""}):
        m = (sp == kind).to_numpy()
        lab = np.cumsum(np.r_[True, np.diff(np.flatnonzero(m)) > 1])
        for k in np.unique(lab):
            g = T.iloc[np.flatnonzero(m)[lab == k]]
            out.append(dict(geom=dict(type="Point", coordinates=[float(g.lon.mean()), float(g.lat.mean())]),
                            props=dict(kind="slack", slack=kind, raw_col_first=int(g.raw_col.min()),
                                       raw_col_last=int(g.raw_col.max()),
                                       label=f"{kind}: channels {g.raw_col.min()}-{g.raw_col.max()} at one point")))
    for p in points or []:
        out.append(dict(geom=dict(type="Point", coordinates=[float(p["lon"]), float(p["lat"])]),
                        props=dict(kind=p.get("kind", "point"), label=p.get("label", ""),
                                   **{k: v for k, v in p.items() if k not in ("lat", "lon", "kind", "label")})))
    return out


def write_kml(T, feats, path, name, every=10):
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
         f"<name>{escape(name)}</name>",
         "<description>Each channel at the centre of its gauge (WGS84).</description>",
         '<Style id="line"><LineStyle><color>ff00a5ff</color><width>3</width></LineStyle></Style>',
         '<Style id="pt"><IconStyle><scale>0.5</scale></IconStyle></Style>']

    def table(d):
        rows = "".join(f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>" for k, v in d.items()
                       if v is not None)
        return f"<![CDATA[<table>{rows}</table>]]>"
    for f in feats:
        g, p = f["geom"], f["props"]
        if g["type"] == "LineString":
            co = " ".join(f"{x:.8f},{y:.8f},0" for x, y in g["coordinates"])
            L.append(f"<Placemark><name>{escape(str(p.get('segment', '')))}</name><styleUrl>#line</styleUrl>"
                     f"<description>{table(p)}</description><LineString><coordinates>{co}</coordinates>"
                     "</LineString></Placemark>")
        else:
            x, y = g["coordinates"]
            L.append(f"<Placemark><name>{escape(str(p.get('label', '')))}</name><styleUrl>#pt</styleUrl>"
                     f"<description>{table(p)}</description><Point><coordinates>{x:.8f},{y:.8f},0</coordinates>"
                     "</Point></Placemark>")
    L.append("<Folder><name>every channel</name>")
    for r in T.to_dict("records"):
        nm = str(r["raw_col"]) if r["raw_col"] % every == 0 else ""
        L.append(f"<Placemark><name>{nm}</name><styleUrl>#pt</styleUrl><description>"
                 f"{table({k: clean(v) for k, v in r.items()})}</description><Point><coordinates>"
                 f"{r['lon']:.8f},{r['lat']:.8f},0</coordinates></Point></Placemark>")
    L += ["</Folder>", "</Document></kml>"]
    open(path, "w").write("\n".join(L))


def manifest(folder):
    base = pathlib.Path(folder)
    files = sorted(p for p in base.rglob("*") if p.is_file() and not p.name.startswith(".") and p.name != "md5sums.txt")
    with open(base / "md5sums.txt", "w") as f:
        for p in files:
            f.write(f"{hashlib.md5(p.read_bytes()).hexdigest()}  {p.relative_to(base).as_posix()}\n")
    return len(files)


def main():
    ap = argparse.ArgumentParser(description="delivery package of a channel map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dictionary")
    d.add_argument("--map", required=True)
    d.add_argument("--segments")
    d.add_argument("--extra")
    d.add_argument("--out", required=True)
    s = sub.add_parser("slack")
    s.add_argument("--map", required=True)
    s.add_argument("--segments")
    s.add_argument("--spacing", type=float, required=True)
    s.add_argument("--out", required=True)
    c = sub.add_parser("change")
    c.add_argument("--old", required=True)
    c.add_argument("--new", required=True)
    c.add_argument("--out", required=True)
    g = sub.add_parser("gis")
    g.add_argument("--map", required=True, action="append", help="one or more channel tables (e.g. 8m and 16m)")
    g.add_argument("--summary")
    g.add_argument("--points", help="JSON list of extra points {lat, lon, kind, label, ...} (waterlines, nodes)")
    g.add_argument("--name", default="DAS channel map")
    g.add_argument("--out", required=True)
    g.add_argument("--prefix", default="channel_map")
    m = sub.add_parser("manifest")
    m.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd == "dictionary":
        extra = json.load(open(a.extra)) if a.extra else {}
        rows = dictionary(pd.read_csv(a.map), os.path.basename(a.map), STD, extra)
        if a.segments:
            rows += dictionary(pd.read_csv(a.segments), os.path.basename(a.segments), STD_SEG, extra)
        D = pd.DataFrame(rows)
        D.to_csv(a.out, index=False)
        print(D[["table", "column", "unit", "n_empty", "meaning"]].to_string(index=False))
        unk = D[D.unit == "?"]
        if len(unk):
            print("describe these columns with --extra:", unk.column.tolist())
    elif a.cmd == "slack":
        T = pd.read_csv(a.map)
        S = pd.read_csv(a.segments, dtype={"segment": str, "slack_cols": str, "slack_at_m": str,
                                           "slack_placed_by": str}) if a.segments else None
        I = slack_inventory(T, S, a.spacing)
        I.to_csv(a.out, index=False, float_format="%.6g")
        pd.set_option("display.width", 220)
        print(I.round(2).to_string(index=False))
    elif a.cmd == "change":
        C = change_table(pd.read_csv(a.old), pd.read_csv(a.new))
        C.to_csv(a.out, index=False, float_format="%.8g")
        mv = C.move_m
        print(dict(moved_gt_0p5_m=int((mv > 0.5).sum()), moved_gt_10_m=int((mv > 10).sum()), max_m=float(mv.max()),
                   max_at=int(C.raw_col[mv.idxmax()])))
    elif a.cmd == "gis":
        os.makedirs(a.out, exist_ok=True)
        summ = json.load(open(a.summary)) if a.summary else None
        pts = json.load(open(a.points)) if a.points else []
        for f in a.map:
            T = pd.read_csv(f)
            nm = os.path.splitext(os.path.basename(f))[0]
            json.dump(channel_fc(T, nm), open(os.path.join(a.out, nm + ".geojson"), "w"))
        T = pd.read_csv(a.map[0])
        feats = cable_features(T, summ, pts)
        json.dump(dict(type="FeatureCollection", name=f"{a.prefix}_features",
                       features=[dict(type="Feature", geometry=f["geom"], properties=f["props"]) for f in feats]),
                  open(os.path.join(a.out, f"{a.prefix}_features.geojson"), "w"))
        write_kml(T, feats, os.path.join(a.out, f"{a.prefix}.kml"), a.name)
        print("written to", a.out)
    else:
        print(manifest(a.dir), "files in", os.path.join(a.dir, "md5sums.txt"))


if __name__ == "__main__":
    main()
