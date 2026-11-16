#!/usr/bin/env python3
"""The README demo: build the synthetic cable's channel map end to end, check it against the known truth, draw it.

Runs make_synthetic.py -> road_path.py -> build_channel_map.py (twice: with the coil block in the config, and
without it, as if the slack had not been found) and compares both maps with the true channel positions.
Writes the data to examples/synthetic/data/ and the figure to docs/demo.png (needs matplotlib).

    python3 examples/synthetic/run_demo.py [--fig docs/demo.png]
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "das-channel-mapping", "scripts")
sys.path.insert(0, SCRIPTS)
from cmap_geo import LocalXY, point_to_polyline  # noqa: E402

SEGCOL = dict(internal="0.3", cabin="0.45", land="tab:orange", coil="m", beach="goldenrod", sea="tab:blue",
              far_land="tab:green")


def run(*args):
    subprocess.run([sys.executable, *args], check=True, stdout=subprocess.DEVNULL)


def errors(data, out):
    T = pd.read_csv(os.path.join(data, "truth.csv"))
    M = pd.read_csv(os.path.join(data, out, "channel_map_all.csv"))
    P = LocalXY.around(T.lat, T.lon)
    M["err_m"] = P.dist(T.lat.to_numpy(), T.lon.to_numpy(), M.lat.to_numpy(), M.lon.to_numpy())
    return M, T, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--fig", default=os.path.join(ROOT, "docs", "demo.png"))
    a = ap.parse_args()
    d = a.data
    run(os.path.join(HERE, "make_synthetic.py"), "--out", d)
    run(os.path.join(SCRIPTS, "road_path.py"), "--config", os.path.join(d, "config.json"), "--piece", "land",
        "--osm", os.path.join(d, "osm.json"), "--reference", os.path.join(d, "reference_route.csv"),
        "--out", os.path.join(d, "paths.csv"))
    run(os.path.join(SCRIPTS, "build_channel_map.py"), os.path.join(d, "config.json"), "--out", os.path.join(d, "out"))
    cfg = json.load(open(os.path.join(d, "config.json")))
    land = next(p for p in cfg["pieces"] if p["type"] == "anchored")
    k1, k2 = land["slack"][0]["cols"]
    land["slack"] = []
    json.dump(cfg, open(os.path.join(d, "config_noslack.json"), "w"), indent=1)
    run(os.path.join(SCRIPTS, "build_channel_map.py"), os.path.join(d, "config_noslack.json"), "--out",
        os.path.join(d, "out_noslack"))

    M, T, P = errors(d, "out")
    N, _, _ = errors(d, "out_noslack")
    g = M.groupby("segment", sort=False)
    tab = pd.DataFrame(dict(channels=g.size(), error_median_m=g.err_m.median(), error_max_m=g.err_m.max(),
                            pos_unc_median_m=g.pos_unc_m.median(),
                            inside_pos_unc=g.apply(lambda q: f"{np.mean(q.err_m <= q.pos_unc_m):.0%}")))
    print("Built map vs the known truth (metres):")
    print(tab.drop(index="internal").round(1).to_string())
    A = pd.read_csv(os.path.join(d, "anchors.csv"))
    seg = (A.col.iloc[4], A.col.iloc[5])
    sm = M.raw_col.between(*seg)
    c1, c2 = int(k1 + 0.5), int(k2 - 0.5)
    print(f"\nSegment with the 41 m coil (anchors 5-6, channels {seg[0]:.0f}-{seg[1]:.0f}): max error "
          f"{N.err_m[sm].max():.0f} m if the coil is spread evenly, {M.err_m[sm].max():.1f} m with the coil block "
          f"(channels {c1}-{c2} at one point).")
    if not a.fig:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    xy = lambda q: P.xy(q.lat.to_numpy(), q.lon.to_numpy())  # noqa: E731
    osm = json.load(open(os.path.join(d, "osm.json")))
    roads = [P.xy(np.array([v["lat"] for v in w["geometry"]]), np.array([v["lon"] for v in w["geometry"]]))
             for w in osm["elements"]]
    fig = plt.figure(figsize=(13, 8.8))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1], height_ratios=[1.2, 1], hspace=0.36, wspace=0.16,
                          left=0.06, right=0.98, top=0.93, bottom=0.07)
    # (a) the whole cable
    ax = fig.add_subplot(gs[0, 0])
    for x, y in roads:
        ax.plot(x, y, "-", color="0.82", lw=1.2, zorder=1)
    for s, colr in SEGCOL.items():
        x, y = xy(M[M.segment == s])
        ax.plot(x, y, ".", color=colr, ms=3, zorder=3)
    ax.plot(*P.xy(A.lat.to_numpy(), A.lon.to_numpy()), "o", mfc="none", mec="r", ms=7, mew=1.4, zorder=4)
    x, y = xy(M[M.slack.fillna("") != ""].iloc[[0]])
    ax.plot(x, y, "s", mfc="none", mec="k", ms=9, mew=1.4, zorder=5)
    ax.annotate("41 m coil, see (b)", (x[0], y[0]), xytext=(12, 10), textcoords="offset points", fontsize=8.5)
    for c in range(100, len(M), 100):
        x, y = xy(M.iloc[[c]])
        ax.annotate(str(c), (x[0], y[0]), xytext=(4, 4), textcoords="offset points", fontsize=8, color="0.3")
    ax.set_aspect("equal")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.legend(handles=[Line2D([], [], ls="none", marker="o", ms=6, color=SEGCOL[s], label=s.replace("_", " "))
                       for s in ("cabin", "land", "coil", "beach", "sea", "far_land")] +
              [Line2D([], [], ls="none", marker="o", ms=7, mfc="none", mec="r", label="tap-test anchor"),
               Line2D([], [], color="0.82", lw=1.2, label="OSM roads (one is a decoy)")],
              fontsize=8, loc="lower left", ncol=2)
    ax.set_title("(a) The built map: 729 channels (numbers every 100), placed from 9 tap-test anchors,\n"
                 "the OSM road, a 3 km sea route between two waterlines and a far end by the fibre / road ratio",
                 fontsize=10)
    # (b) the segment with the coil, along the road
    ax = fig.add_subplot(gs[0, 1])
    rx, ry = roads[0]
    cc = np.arange(int(np.ceil(seg[0])), int(np.floor(seg[1])) + 1)
    s0 = point_to_polyline(*P.xy(A.lat.to_numpy()[4:5], A.lon.to_numpy()[4:5]), rx, ry)[1][0]
    along = {k: point_to_polyline(*xy(Q.iloc[cc]), rx, ry)[1] - s0 for k, Q in (("T", T), ("N", N), ("M", M))}
    ax.axvspan(c1 - 0.5, c2 + 0.5, color="0.9", lw=0)
    ax.plot(cc, along["T"], "o", mfc="none", mec="k", ms=7, label="true position")
    ax.plot(cc, along["N"], "x-", color="tab:blue", ms=5, lw=0.8, label="built, coil spread evenly")
    ax.plot(cc, along["M"], ".-", color="tab:orange", ms=7, lw=1, label="built, coil block at one point (the map)")
    j = int(np.argmax(np.abs(along["N"] - along["T"])))
    ax.annotate("", (cc[j], along["N"][j]), (cc[j], along["T"][j]),
                arrowprops=dict(arrowstyle="<->", color="tab:blue", lw=1))
    ax.annotate(f"{abs(along['N'][j] - along['T'][j]):.0f} m off", (cc[j], (along["N"][j] + along["T"][j]) / 2),
                xytext=(cc[j] + 3, along["T"][j] - 35), color="tab:blue", fontsize=9,
                arrowprops=dict(arrowstyle="-", color="tab:blue", lw=0.6))
    ax.text((c1 + c2) / 2, along["T"][0] + 5, f"channels {c1}-{c2}:\n41 m of fibre\nat one point", ha="center",
            fontsize=8.5, va="bottom")
    ax.set_xlabel("channel")
    ax.set_ylabel("position along the road\nfrom anchor 5 (m)")
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("(b) Anchors 5-6: the coil adds fibre but no road.\nSpread evenly, it pulls the channels "
                 "along the road", fontsize=10)
    # (c) error along the cable
    ax = fig.add_subplot(gs[1, :])
    for s, colr in SEGCOL.items():
        q = M[M.segment == s]
        if len(q) and s != "internal":
            ax.axvspan(q.raw_col.min() - 0.5, q.raw_col.max() + 0.5, color=colr, alpha=0.08, lw=0)
            if len(q) > 30:
                ax.text((q.raw_col.min() + q.raw_col.max()) / 2, 66, s.replace("_", " "), ha="center", va="top",
                        fontsize=9, color=colr)
    ax.text(306, 66, "coil,\nbeach", ha="center", va="top", fontsize=8, color="m")
    ax.step(M.raw_col, M.pos_unc_m, where="mid", color="0.45", lw=1, ls="--",
            label="pos_unc_m: the map's own uncertainty (rules, ~1 sigma)")
    ax.plot(N.raw_col, N.err_m, "-", color="tab:blue", lw=1, label="error, coil spread evenly")
    ax.plot(M.raw_col, M.err_m, "-", color="k", lw=1.3, label="error of the map (coil block at one point)")
    ax.set_xlim(0, len(M) - 1)
    ax.set_ylim(0, 68)
    ax.set_xlabel("channel")
    ax.set_ylabel("distance to the\ntrue position (m)")
    ax.legend(fontsize=8.5, loc="center left", bbox_to_anchor=(0.43, 0.62))
    ax.set_title("(c) Error against the known truth: inside pos_unc_m on every channel.  The synthetic cable "
                 "obeys the method's own assumptions,\nso these errors are a best case; on a real cable expect "
                 "pos_unc_m-sized errors (see Limitations)", fontsize=10)
    os.makedirs(os.path.dirname(os.path.abspath(a.fig)), exist_ok=True)
    fig.savefig(a.fig, dpi=100)
    print(f"figure: {a.fig}")


if __name__ == "__main__":
    main()
