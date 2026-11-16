#!/usr/bin/env python3
"""Road traffic as a ruler: is a weakly coupled run a coil at ONE point of the road or a stretch along it, and
where on the road does a coil sit?

A car reaches the channels one after another; the delay between two channels = road length between them / speed.
A coil adds no road length: from the channel before the run (a - 1) to the one after it (b + 1) a car needs about
one channel's time, and every channel of the coil lights up at the moment the car passes. A stretch along the
road that is merely badly coupled adds its length / speed. Two ways to measure it:

  ridge  stacked cross-correlations (many hours) of the car-activity envelope (e.g. log 2-20 Hz envelope at 5 Hz
         minus its running median, positive part) of a reference channel A = a - before with every channel A ..
         b + after: the car ridge is followed outward from A on each side of zero lag; road channels in the run =
         (lag after the run - lag before it) / (s per channel) - 1: ~0 for a coil, ~n = b - a + 1 for a stretch.
         Run the same on ordinary stretches of the same length as controls.
  cars   single cars (tracks: arrival time per channel per car, from any car tracker): per car, road channels in
         the run from line fits of the arrival times over nfit channels before / after the run; and the point of
         the road where the coil sits: assuming the car's speed is constant between the two anchors A0, A1 of
         the segment (their road positions s(A0), s(A1) from the map), the moment the coil lights up maps to
         x = s(A0) + (s(A1) - s(A0)) (t_light - t(A0)) / (t(A1) - t(A0)); medians per driving direction; the
         mean of the two directions cancels any time offset common to both, half their difference is a lower
         bound of the error (a speed bias shared by both directions - cars brake at corners and junctions - is
         NOT seen this way: a few m on straight roads, more near corners). Do not use cars to move ordinary
         channels: "constant speed within a segment" fails at corners by 10-30 m.

    python3 vehicle_coil.py ridge --cc 'day_*.npz' --run 750,768 [--run ...] [--control 716,734] --fs 5 \
        --maxlag 45 --before 12 --after 15 --spacing 8.1676 --out ridge.csv
    python3 vehicle_coil.py cars --tracks 'pass_*.npz' --segments channel_map_anchored_segments.csv \
        --map channel_map_8m.csv --coil 750,768 [--coil ...] --out coil_positions.csv [--samples samples.csv]
ridge input: npz files with cc_<a>_<b> (n_channels x n_lags, channels a-before .. b+after) summed over nsum
windows. cars input: npz files with tc (n_cars, n_cols) arrival times (s, NaN where not followed), cols, dir (+1
towards higher channels / -1), optional tcoil / coilpk (n_cars, n_coils: light-up time and peak of the mean
envelope of each coil's channels) with coils (n_coils, 2), and selection fields score, gap_same, slowest,
quake_frac (see --select).
"""
import argparse
import glob
import json

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------------------------------- ridge
def ridge_track(CC, cs, a, b, sign, lags, step0=0.8, half_win=2.5, nmad=3.0):
    """the car ridge on one side of zero lag, followed outward from the reference channel cs[0]; NaN where lost."""
    A = cs[0]
    tau = np.full(len(cs), np.nan)
    tau[0] = 0.0
    m = (np.sign(lags) == sign) | (lags == 0)
    step, last, prev = step0, 0.0, A
    for i in range(1, len(cs)):
        c = cs[i]
        if a <= c <= b:
            continue
        if c > b and prev < a:          # first channel after the run: anything from "coil" to beyond "stretch"
            lo, hi = last + 0.2 * step, last + (c - prev + b - a + 1) * step + 3
        else:
            lo, hi = last + step * (c - prev) - half_win, last + step * (c - prev) + half_win
        w = m & (np.abs(lags) >= max(lo, 0.2)) & (np.abs(lags) <= hi)
        if not w.any():
            continue
        cc = CC[i]
        j = np.flatnonzero(w)[np.argmax(cc[w])]
        med = np.median(cc[m])
        if cc[j] > med + nmad * 1.4826 * np.median(np.abs(cc[m] - med)):
            tau[i] = abs(lags[j])
            if c < a and c - A >= 2:
                step = tau[i] / (c - A)
            last, prev = tau[i], c
    return tau


def ridge_verdict(tau, cs, a, b, s_range=(0.3, 2.5)):
    """speed before the run (line through 0 at the reference), line after it, road channels in the run."""
    A = cs[0]
    L = (cs >= A + 2) & (cs < a) & np.isfinite(tau)
    R = (cs > b) & np.isfinite(tau)
    out = dict(s_per_col=np.nan, road_cols=np.nan, n_left=int(L.sum()), n_right=int(R.sum()))
    if L.sum() < 3 or R.sum() < 3:
        return out
    s = float(np.sum(tau[L] * (cs[L] - A)) / np.sum((cs[L] - A) ** 2))
    if not s_range[0] <= s <= s_range[1]:            # not a car's ridge
        return out
    pr = np.polyfit(cs[R] - (b + 1), tau[R], 1)
    s2 = (s + pr[0]) / 2 if pr[0] > 0 else s
    entry = s * (a - 1 - A)
    out.update(s_per_col=s, s_after=float(pr[0]), lag_entry=entry, lag_exit=float(pr[1]),
               road_cols=float((pr[1] - entry) / s2 - 1))
    return out


# ------------------------------------------------------------------------------------------------------ cars
def road_columns(tc, cols, a, b, nfit=10):
    """road channels inside the run [a, b] for one car: (t(b+1) - t(a-1)) / (local s per channel) - 1; the local s
    per channel is the mean slope of line fits over nfit channels before a-1 and after b+1."""
    idx = {int(c): i for i, c in enumerate(cols)}
    if (a - 1) not in idx or (b + 1) not in idx:
        return np.nan
    ta, tb = tc[idx[a - 1]], tc[idx[b + 1]]
    if not (np.isfinite(ta) and np.isfinite(tb)):
        return np.nan
    sl = []
    for rng in (range(a - nfit, a), range(b + 1, b + 1 + nfit)):
        cc = np.array([c for c in rng if c in idx and np.isfinite(tc[idx[c]])])
        if len(cc) >= 4:
            sl.append(abs(np.polyfit(cc, tc[[idx[c] for c in cc]], 1)[0]))
    if not sl or np.mean(sl) <= 0:
        return np.nan
    return abs(tb - ta) / np.mean(sl) - 1


def t_at(tc, cols, A, skip, lo, hi, half=3):
    """arrival time at the fractional channel A from a line fit over followed road channels within +-half (not
    across a coil); NaN if fewer than 3."""
    idx = {int(c): i for i, c in enumerate(cols)}
    cs = [c for c in range(int(np.floor(A)) - half, int(np.ceil(A)) + half + 1)
          if lo <= c <= hi and c in idx and not skip[c] and np.isfinite(tc[idx[c]])
          and not skip[int(np.ceil(min(c, A))):int(np.floor(max(c, A))) + 1].any()]
    if len(cs) < 3:
        return np.nan
    cs = np.array(cs)
    return float(np.polyfit(cs - A, tc[[idx[c] for c in cs]], 1)[1])


def coil_positions(files, segs, smap, coils, select, min_cover=0.7, slack_frac=0.2, light_min=0.3):
    """per car crossing of each coil: light-up position on the road (x from the segment's first anchor), the
    midpoint and the channels before / after; then medians per direction and the two-direction mean."""
    lo = int(np.ceil(segs.col_from.min()))
    hi = int(np.floor(segs.col_to.max()))
    skip = np.zeros(hi + 3, bool)
    for a, b in coils:
        skip[a:b + 1] = True
    s = smap.set_index("raw_col").s_path_m

    def s_at(x):
        i = int(np.floor(x))
        return float(s[i] + (x - i) * (s[i + 1] - s[i]))
    G = segs.assign(s0=[s_at(v) for v in segs.col_from], s1=[s_at(v) for v in segs.col_to]).reset_index(drop=True)

    def seg_of(c):
        q = G[(G.col_from < c) & (G.col_to > c)]
        return int(q.index[0]) if len(q) else -1
    coil_seg = {(a, b): seg_of(a) for a, b in coils}
    rows, nsel = [], 0
    for f in sorted(files):
        z = np.load(f)
        tc_all, cols = z["tc"].astype(float), z["cols"]
        sel = np.isfinite(tc_all).sum(1) >= select.get("ncols", 30)
        for k, op in (("score", np.greater_equal), ("gap_same", np.greater_equal), ("slowest", np.less_equal)):
            if k in z.files and k in select:
                sel &= op(z[k], select[k])
        if "quake_frac" in z.files and "quake_frac" in select:
            sel &= z["quake_frac"] <= select["quake_frac"]
        zc = [tuple(map(int, r)) for r in z["coils"]] if "coils" in z.files else []
        idx = {int(c): i for i, c in enumerate(cols)}
        nsel += int(sel.sum())
        for i in np.flatnonzero(sel):
            tc, dr = tc_all[i], int(z["dir"][i])
            for (a, b) in coils:
                j = coil_seg[(a, b)]
                if j < 0:
                    continue
                g = G.iloc[j]
                road = [c for c in range(int(np.ceil(g.col_from)), int(np.floor(g.col_to)) + 1)
                        if not skip[c] and g.col_from < c < g.col_to and c in idx]
                if not road or np.isfinite(tc[[idx[c] for c in road]]).mean() < min_cover:
                    continue
                t0, t1 = t_at(tc, cols, g.col_from, skip, lo, hi), t_at(tc, cols, g.col_to, skip, lo, hi)
                T = t1 - t0
                if not (np.isfinite(T) and dr * T > 0.2):
                    continue
                L = g.s1 - g.s0
                x = L * (tc[[idx[c] for c in road]] - t0) / T
                if np.nanmin(x) < -slack_frac * L or np.nanmax(x) > (1 + slack_frac) * L:
                    continue
                if (a - 1) not in idx or (b + 1) not in idx:
                    continue
                ta, tb = tc[idx[a - 1]], tc[idx[b + 1]]
                if not (np.isfinite(ta) and np.isfinite(tb)):
                    continue
                n_road = max(int(np.sum(~skip[np.arange(int(np.ceil(g.col_from)), int(np.floor(g.col_to)) + 1)])), 1)
                rc = abs(tb - ta) / (abs(T) / n_road) - 1
                if rc >= (b - a + 1) / 2:                 # two cars joined at a junction: not this coil
                    continue
                x_light = np.nan
                if (a, b) in zc and "tcoil" in z.files:
                    q = zc.index((a, b))
                    if float(z["coilpk"][i, q]) > light_min:
                        x_light = L * (float(z["tcoil"][i, q]) - t0) / T
                rows.append(dict(coil=f"{a}-{b}", segment=g.segment, dir=dr, speed_mps=L / abs(T), x_light=x_light,
                                 x_mid=L * (0.5 * (ta + tb) - t0) / T, x_before=L * (ta - t0) / T,
                                 x_after=L * (tb - t0) / T, road_cols=rc,
                                 road_cols_local=road_columns(tc, cols, a, b)))
    K = pd.DataFrame(rows)
    out = []
    for (a, b) in coils:
        j = coil_seg[(a, b)]
        g = G.iloc[j]
        L = g.s1 - g.s0
        rec = dict(coil=f"{a}-{b}", segment=g.segment, seg_len_m=L,
                   uniform_m=L * ((a - 0.5) - g.col_from) / ((g.col_to - g.col_from) - (b - a + 1)))
        for lab, dr in (("up", 1), ("down", -1)):
            q = K[(K.coil == f"{a}-{b}") & (K.dir == dr)] if len(K) else K
            for key in ("x_light", "x_mid", "road_cols_local"):
                v = q[key].dropna() if len(q) else pd.Series(dtype=float)
                med = float(v.median()) if len(v) else np.nan
                mad = float((v - med).abs().median()) if len(v) else np.nan
                rec[f"{key}_{lab}"] = med
                rec[f"{key}_{lab}_se"] = 1.253 * 1.4826 * mad / np.sqrt(len(v)) if len(v) else np.nan
                rec[f"n_{key}_{lab}"] = len(v)
        for key in ("x_light", "x_mid"):
            rec[f"{key}_m"] = 0.5 * (rec[f"{key}_up"] + rec[f"{key}_down"])
            rec[f"{key}_sys_m"] = 0.5 * abs(rec[f"{key}_up"] - rec[f"{key}_down"])
        rec["at_fraction"] = rec["x_light_m"] / L
        out.append(rec)
    return pd.DataFrame(out), K, nsel


def main():
    ap = argparse.ArgumentParser(description="coil at one point? where on the road? (vehicle traffic)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ridge")
    r.add_argument("--cc", required=True, help="glob of npz files with cc_<a>_<b> and nsum")
    r.add_argument("--run", action="append", default=[], help="a,b of a weak run (repeat)")
    r.add_argument("--control", action="append", default=[], help="a,b of an ordinary stretch (repeat)")
    r.add_argument("--fs", type=float, default=5.0)
    r.add_argument("--maxlag", type=float, default=45.0)
    r.add_argument("--before", type=int, default=12)
    r.add_argument("--after", type=int, default=15)
    r.add_argument("--spacing", type=float, required=True)
    r.add_argument("--out", required=True)
    c = sub.add_parser("cars")
    c.add_argument("--tracks", required=True, help="glob of npz files with car tracks")
    c.add_argument("--segments", required=True, help="anchored-segment table (segment, col_from, col_to)")
    c.add_argument("--map", required=True, help="channel map CSV (raw_col, s_path_m)")
    c.add_argument("--coil", action="append", required=True, help="a,b channels of a block (repeat)")
    c.add_argument("--select", default='{"ncols": 30, "score": 1.0, "gap_same": 20, "slowest": 3, "quake_frac": 0}')
    c.add_argument("--out", required=True)
    c.add_argument("--samples")
    a = ap.parse_args()
    if a.cmd == "ridge":
        files = sorted(glob.glob(a.cc))
        lags = np.arange(-int(a.maxlag * a.fs), int(a.maxlag * a.fs) + 1) / a.fs
        rows = []
        for kind, lst in (("run", a.run), ("control", a.control)):
            for s in lst:
                ra, rb = map(int, s.split(","))
                CC, n = 0, 0
                for f in files:
                    z = np.load(f)
                    if int(z["nsum"]):
                        CC = CC + z[f"cc_{ra}_{rb}"]
                        n += int(z["nsum"])
                CC = CC / n
                cs = np.arange(ra - a.before, rb + a.after + 1)
                for sign, d in ((1, "up"), (-1, "down")):
                    v = ridge_verdict(ridge_track(CC, cs, ra, rb, sign, lags), cs, ra, rb)
                    rows.append(dict(kind=kind, col_from=ra, col_to=rb, n_cols=rb - ra + 1, direction=d,
                                     speed_mps=a.spacing / v["s_per_col"] if v["s_per_col"] > 0 else np.nan, **v))
        T = pd.DataFrame(rows)
        T.to_csv(a.out, index=False, float_format="%.4g")
        pd.set_option("display.width", 200)
        print(T.round(2).to_string(index=False))
    else:
        coils = [tuple(map(int, s.split(","))) for s in a.coil]
        CP, K, nsel = coil_positions(glob.glob(a.tracks), pd.read_csv(a.segments, dtype={"segment": str}),
                                     pd.read_csv(a.map), coils, json.loads(a.select))
        CP.to_csv(a.out, index=False, float_format="%.5g")
        if a.samples:
            K.to_csv(a.samples, index=False, float_format="%.5g")
        print(f"cars selected: {nsel}")
        pd.set_option("display.width", 200)
        print(CP[["coil", "segment", "seg_len_m", "uniform_m", "x_light_up", "x_light_down", "x_light_m",
                  "x_light_sys_m", "road_cols_local_up", "road_cols_local_down", "n_x_light_up",
                  "n_x_light_down"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
