#!/usr/bin/env python3
"""Rebuild the delivered Kefalonia-Ithaca channel map (2024 seafloor DAS cable) from its real inputs, check it
and draw it.

  1. distance convention: shot picks vs the logged distances, read as the header distance and as the label
  2. paths: road_path.py on the OpenStreetMap extract and the operator's land route -> out/paths.csv
  3. build: build_channel_map.py data/config.json -> out/channel_map_8m.csv / _16m.csv, compared channel by
     channel with the delivered table (data/delivered_channel_map_8m.csv)
  4. figure (default docs/kefalonia.png; needs matplotlib)

    python3 examples/kefalonia/run_kefalonia.py [--out examples/kefalonia/out] [--fig docs/kefalonia.png]
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
DATA = os.path.join(HERE, "data")
sys.path.insert(0, SCRIPTS)
from cmap_geo import LocalXY  # noqa: E402
from hammer_anchor import convention_test  # noqa: E402

SEGCOL = dict(internal="0.3", cabin="0.45", land="tab:orange", coil="m", beach="goldenrod", sea="tab:blue",
              ithaca_land="tab:green")


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-3000:])
    return r.stdout


def step1_conventions(spacing):
    S = pd.read_csv(os.path.join(DATA, "shots.csv"))
    r = convention_test(S.col, S.d_logged_m, dict(header=(-207.20757, spacing), label=(-215.0, 8.0)), spacing)
    h, lab = r["header"], r["label"]
    rh, rl = np.array(h["residual_m"]), np.array(lab["residual_m"])
    names = S.name.astype(str).to_numpy()
    beach = int(np.flatnonzero(names == "34")[0]) if "34" in names else int(np.argmax(S.col.to_numpy()))
    coil = int(np.flatnonzero(names == "33")[0]) if "33" in names else None
    print("1. Distance convention of the shot log (45 shots, picked channel - channel implied by the logged distance):")
    print(f"   read as the header distance (-207.2 + 8.168 c): median {h['median_m']:+.1f} m, MAD {h['mad_m']:.1f} m, "
          f"{int((np.abs(rh) <= 21).sum())}/{len(rh)} within +-21 m"
          + (f"; the exception, shot #33 at {rh[coil]:+.0f} m, is the far end of the beach-manhole coil" if coil is not None else ""))
    print(f"   read as the label FO_nom (-215 + 8 c): the error grows along the cable, {rl[beach]:+.0f} m at the beach "
          f"(shot #{names[beach]}) -> the log uses the header distance")
    return S, r


def step2_paths(cfg_path, out):
    run(os.path.join(SCRIPTS, "road_path.py"), "--config", cfg_path, "--piece", "land",
        "--osm", os.path.join(DATA, "osm_highways.json"), "--reference", os.path.join(DATA, "operator_land_route.csv"),
        "--reference-name", "operator_route", "--out", os.path.join(out, "paths.csv"),
        "--report", os.path.join(out, "paths_report.json"))
    rep = json.load(open(os.path.join(out, "paths_report.json")))
    c = rep["check"]["final_vs_reference"]
    print(f"2. Paths between the 43 land anchors: {rep['by_path']}; OSM path vs operator route through the same "
          f"anchors: median {c['median_m']:.0f} m, p90 {c['p90_m']:.0f} m, max {c['max_m']:.0f} m ({c['n_channels']} channels)")
    return rep


def step3_build(cfg_path, out):
    delivered = os.path.join(DATA, "delivered_channel_map_8m.csv")
    run(os.path.join(SCRIPTS, "build_channel_map.py"), cfg_path, "--out", out, "--compare", delivered)
    G = pd.read_csv(os.path.join(out, "channel_map_segments.csv"))
    summ = json.load(open(os.path.join(out, "channel_map_summary.json")))
    print("3. Channel map (1872 channels):")
    G2 = G.assign(channels=G.raw_col_first.astype(str) + "-" + G.raw_col_last.astype(str))[
        ["segment", "channels", "fibre_m", "ground_m", "pos_unc_min_m", "pos_unc_median_m", "pos_unc_max_m"]]
    print(G2.round(1).to_string(index=False))
    print("   slack blocks (all channels of a block at one point of the road):")
    for b in summ["anchored"]["slack_blocks"]:
        print(f"     {b['slack_kind']:<10s} c {b['slack_cols']:<12s} {b['slack_m']:6.1f} m of fibre, {float(b['slack_at_m']):6.1f} m "
              f"after shot #{b['segment'].split('-')[0]} (placed by {b['slack_placed_by']})")
    it = summ["pieces"]["ithaca_land"]
    f = it["feature_cols"]
    print(f"   Ithaca land: fibre/road ratio {it['fibre_over_path']:.4f} (from Kefalonia), last channel {it['route_left_after_last_col_m']:.0f} m "
          f"of route before the node; drawn V at c {f['v_start']:.1f} / {f['v_tip']:.1f} / {f['v_end']:.1f}, hairpin 1 c "
          f"{f['hairpin1_start']:.1f}-{f['hairpin1_end']:.1f}")
    c = summ["compare"]
    print(f"   rebuilt vs delivered table: largest difference {c['max_m']:.2f} m, {c['moved_gt_10_m']} channels > 10 m "
          "(rounding in the 2024 files: positions kept to 5 decimals of a degree, land paths to ~0.1 m)")
    return summ


def figure(out, fig_path, summ):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    T = pd.read_csv(os.path.join(out, "channel_map_8m.csv"))
    Dv = pd.read_csv(os.path.join(DATA, "delivered_channel_map_8m.csv"))
    coast = pd.read_csv(os.path.join(DATA, "coastline.csv"))
    osm = json.load(open(os.path.join(DATA, "osm_highways.json")))["elements"]
    route = pd.read_csv(os.path.join(DATA, "ithaca_route.csv"))
    A = pd.DataFrame(summ["anchored"]["anchors"])
    P = LocalXY.around(T.lat, T.lon)
    asp = 1 / np.cos(np.radians(P.lat0))
    plt.rcParams.update({"font.size": 10.5, "axes.labelsize": 11, "xtick.labelsize": 10, "ytick.labelsize": 10})
    fig = plt.figure(figsize=(11, 9.8))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.3, 0.5, 0.5], width_ratios=[1.35, 1], hspace=0.5, wspace=0.2,
                          left=0.075, right=0.985, top=0.905, bottom=0.06)

    def title(ax, letter, text):
        ax.set_title(r"$\bf{(" + letter + r")}$ " + text, loc="left", fontsize=10.8)

    def base(ax):
        for _, g in coast.groupby("part"):
            ax.plot(g.lon, g.lat, "-", color="0.55", lw=0.8)
        for w in osm:
            q = np.array([(p["lon"], p["lat"]) for p in w["geometry"]])
            ax.plot(q[:, 0], q[:, 1], "-", color="0.82", lw=0.6, zorder=0)
        ax.set_aspect(asp)

    ax = fig.add_subplot(gs[0, 0])
    base(ax)
    for sg, g in T.groupby("segment", sort=False):
        ax.plot(g.lon, g.lat, ".", ms=2.2, color=SEGCOL.get(sg, "k"), label=sg)
    s_last = summ["pieces"]["ithaca_land"]["s_last_col_m"]
    xy = P.xy(route.lat.to_numpy(), route.lon.to_numpy())
    s = np.r_[0, np.cumsum(np.hypot(np.diff(xy[0]), np.diff(xy[1])))]
    rest = route[s >= s_last]
    ax.plot(np.r_[T.lon.iloc[-1], rest.lon], np.r_[T.lat.iloc[-1], rest.lat], "--", color="tab:purple", lw=1,
            label="drawn route after the last channel")
    ax.plot(route.lon.iloc[-1], route.lat.iloc[-1], "*", color="tab:purple", ms=9, label="telecom node")
    for c in range(0, 1872, 200):
        ax.annotate(str(c), (T.lon[c], T.lat[c]), xytext=(4, 4), textcoords="offset points", fontsize=9)
    ax.text(0.03, 0.06, "Kefalonia", transform=ax.transAxes, fontsize=12, color="0.35")
    ax.text(0.86, 0.9, "Ithaca", transform=ax.transAxes, fontsize=12, color="0.35")
    ax.set_xlim(T.lon.min() - 0.004, route.lon.max() + 0.004)
    ax.set_ylim(min(T.lat.min(), route.lat.min()) - 0.006, T.lat.max() + 0.004)
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], ls="", marker="o", ms=5, color=SEGCOL[k], label=k) for k in SEGCOL]
    hs += [Line2D([], [], ls="--", color="tab:purple", label="route beyond the last channel"),
           Line2D([], [], ls="", marker="*", ms=9, color="tab:purple", label="telecom node")]
    ax.legend(handles=hs, fontsize=8.6, loc="upper left", bbox_to_anchor=(0.36, 1.0), ncol=1, handletextpad=0.3,
              labelspacing=0.22)
    title(ax, "a", "All 1872 channels (numbers every 200), coloured by segment;\ngrey: coastline and "
          "OpenStreetMap roads")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")

    ax = fig.add_subplot(gs[0, 1])
    base(ax)
    land = T[T.segment.isin(["cabin", "land", "coil", "beach"])]
    for ps, col in (("osm_road", "tab:orange"), ("operator_route", "tab:cyan"), ("linear", "0.45"), ("hammer_33", "m")):
        g = land[land.path_source == ps]
        ax.plot(g.lon, g.lat, ".", ms=2.5, color=col, label=dict(osm_road="OSM road through the shots",
                                                                  operator_route="operator route",
                                                                  linear="straight line", hammer_33="manhole coil")[ps])
    ax.plot(A.lon, A.lat, "^", ms=5, mfc="none", mec="darkgreen", label="tap-test anchor")
    blocks = T[T.slack.fillna("") != ""]
    runs = blocks.assign(run_id=(blocks.raw_col.diff() != 1).cumsum()).groupby("run_id")
    fibre_of = {}                                  # block fibre from the build (edges may be half or whole channels)
    for b in summ["anchored"]["slack_blocks"]:
        k1, k2 = map(float, b["slack_cols"].split("-"))
        fibre_of[(int(np.ceil(k1)), int(np.floor(k2)))] = float(b["slack_m"])
    G = pd.read_csv(os.path.join(out, "channel_map_segments.csv")).set_index("segment")
    for i, (_, g) in enumerate(sorted(runs, key=lambda kv: -kv[1].lat.mean())):
        kind = g.slack.iloc[0]
        fib = fibre_of.get((int(g.raw_col.min()), int(g.raw_col.max())),
                           float(G.fibre_m.get("coil", len(g) * 8.168)) if kind == "beach_coil" else len(g) * 8.168)
        ax.plot(g.lon.mean(), g.lat.mean(), "o", ms=5 + fib / 12, mfc="none", mec="m" if kind == "beach_coil" else "red", mew=1.6)
        right = int(g.raw_col.min()) not in (681, 705, 844)      # label side with free space on this map
        ax.annotate(f"{g.raw_col.min()}–{g.raw_col.max()}: {fib:.0f} m", (g.lon.mean(), g.lat.mean()),
                    xytext=(12 if right else -12, 0), textcoords="offset points", fontsize=8.6, color="darkred",
                    ha="left" if right else "right", va="center")
    ax.set_xlim(land.lon.min() - 0.002, land.lon.max() + 0.0115)
    ax.set_ylim(land.lat.min() - 0.001, land.lat.max() + 0.001)
    ax.legend(fontsize=8.6, loc="center left", handletextpad=0.3, labelspacing=0.25, borderaxespad=0.3)
    title(ax, "b", "Kefalonia land: 43 tap-test anchors;\ncircles: blocks of excess fibre")
    ax.set_xlabel("Longitude (°E)")
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))

    c = T.raw_col.to_numpy()
    spacing = 8.16761589
    ax = fig.add_subplot(gs[1, :])
    for sg, g in T.groupby("segment", sort=False):
        ax.axvspan(g.raw_col.min() - 0.5, g.raw_col.max() + 0.5, color=SEGCOL.get(sg, "k"), alpha=0.08, lw=0)
    m = c >= 25
    ax.plot(c[m], ((c - 25) * spacing - (T.s_path_m - T.s_path_m[25]))[m], "k-", lw=1)
    ax.set_xlim(0, 1872)
    ax.set_ylabel("Fibre − ground (m)")
    title(ax, "c", "Fibre minus ground, summed from the interrogator: one step per block of excess fibre, a steady "
          "slope at sea (2.0 %)")
    ax = fig.add_subplot(gs[2, :])
    for sg, g in T.groupby("segment", sort=False):
        ax.axvspan(g.raw_col.min() - 0.5, g.raw_col.max() + 0.5, color=SEGCOL.get(sg, "k"), alpha=0.08, lw=0)
    ax.semilogy(c, T.pos_unc_m, "k-", lw=1, label="pos_unc_m (rules, ~1 sigma)")
    d = P.dist(Dv.lat.to_numpy(), Dv.lon.to_numpy(), T.lat.to_numpy(), T.lon.to_numpy())
    ax.semilogy(c, np.maximum(d, 1e-3), ".", ms=1.5, color="tab:red", label="rebuilt - delivered table")
    ax.set_xlim(0, 1872)
    ax.set_ylim(1e-3, 200)
    ax.set_xlabel("Channel number")
    ax.set_ylabel("Metres")
    ax.legend(fontsize=9, loc="lower right", ncol=2, markerscale=4)
    title(ax, "d", f"Position uncertainty of each channel; the rebuilt map matches the delivered one to "
          f"{d.max():.2f} m")
    fig.suptitle("Kefalonia–Ithaca seafloor DAS cable, 2024: the delivered channel map rebuilt from its real inputs",
                 fontsize=12, y=0.985)
    os.makedirs(os.path.dirname(os.path.abspath(fig_path)), exist_ok=True)
    fig.savefig(fig_path, dpi=170)
    print(f"4. Figure: {os.path.relpath(fig_path, ROOT)}")


def main():
    ap = argparse.ArgumentParser(description="rebuild the Kefalonia-Ithaca channel map from its real inputs")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--fig", default=os.path.join(ROOT, "docs", "kefalonia.png"))
    ap.add_argument("--no-fig", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cfg = json.load(open(os.path.join(DATA, "config.json")))
    for p in cfg["pieces"]:                       # absolute paths: inputs in data/, the paths file in out/
        for k in ("anchors", "route"):
            if isinstance(p.get(k), str):
                p[k] = os.path.join(DATA, p[k])
        if p.get("paths"):
            p["paths"] = os.path.join(a.out, "paths.csv")
    cfg_path = os.path.join(a.out, "config_used.json")
    json.dump(cfg, open(cfg_path, "w"), indent=1)
    step1_conventions(float(cfg["spacing_m"]))
    step2_paths(cfg_path, a.out)
    summ = step3_build(cfg_path, a.out)
    if not a.no_fig:
        figure(a.out, a.fig, summ)


if __name__ == "__main__":
    main()
