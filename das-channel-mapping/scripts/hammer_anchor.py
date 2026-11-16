#!/usr/bin/env python3
"""Hammer / tap-test anchors: find the blows of each shot point, stack them, read the anchor channel and the
fibre-geometry anomalies around it, and test which along-fibre distance convention the shot log uses.

Subcommands
  detect       blows of each shot point in a continuous high-frequency envelope (time x channel):
               R = envelope / per-channel median of the whole test; impulsive bins only (log10 envelope above
               the median of the same channel 0.3-1.0 s before and after by >= imp: vehicles change over
               seconds, blows do not); peaks of max_c log10 R above log10(thr), >= 0.5 s apart; peak channel
               refined by a parabola through log R. The shot point is the STATIONARY blow sequence: for every
               strong blow (impulsiveness >= strong) the group of blows within 1 channel and 40 s of it, scored
               sum R * impulsiveness * Gaussian(t - logged time, sigma); best group -> anchor channel (median)
               and MAD; the best group > 3 channels away is reported (runner-up score ratio: ambiguity).
               Footsteps and cars drift by more than a channel within 40 s and form no group.
  stack        per shot point, every blow window (e.g. [-1.0, +1.5] s): band-pass (15-150 Hz), |Hilbert|,
               12.5 ms running mean, / median of the pre-blow window = SNR; aligned on the onset at the anchor
               channel (first time >= 30 % of the peak), refined by cross-correlating log envelopes (+-30 ms) with
               the strongest blow; blows weaker than 0.3 x the strongest dropped (weak blows, footsteps);
               geometric-mean stack. Per channel: peak SNR, onset delay. Reports the footprint (contiguous
               channels with stack SNR >= 6), the near range (>= 0.25 x the anchor) and its strength-weighted
               centroid (a wide near range with the pick at one end = anchor to revisit), secondary maxima
               (>= 0.25 x, separated by a dip < 0.5 x: the fibre comes back near the shot point = loop) and
               simultaneous channels (outside the footprint, SNR >= 6, |delay| <= 25 ms: fibre lying at the shot
               point although far along the fibre = coil / doubled fibre).
  conventions  picked channels vs the logged along-fibre distances under several conventions (offset + step x c):
               the right one leaves small residuals that do not grow with distance.

    python3 hammer_anchor.py detect --env env.npz --log shots.csv --out picks.csv [--blows-out blows.csv]
    python3 hammer_anchor.py stack --blows blows.npz --picks picks.csv --fs 400 --t-start -1.0 --out stack.csv \
        [--delays delays.csv] [--map channel_map.csv --gps shots.csv]
    python3 hammer_anchor.py conventions --picks picks.csv --log shots.csv \
        --convention header=-207.208,8.16762 --convention nominal=-215,8
Inputs: env.npz holds env (n_t, n_ch), t (s, absolute), col0; shots.csv holds name, t_log_s (UTC seconds of the
logged blow time; any clock), d_logged_m (logged along-fibre distance), lat, lon; blows.npz holds one array per
blow named <shot>_<k> (n_t, n_ch) with <shot>_<k>_c0 (its first channel). Anchors stay a judgement call: show the
stacks to the user before writing ANY change of an anchor into the map.
"""
import argparse
import json
import math
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import ndimage, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# -------------------------------------------------------------------------------------------------- detect
def detect_shot(E, t, col0, t_log, bg, thr=8.0, imp=0.6, strong=1.2, sigma_s=90.0, fs_env=None,
                group_cols=1.0, group_s=40.0):
    """blows of one shot point in the envelope window E (n_t, n_ch) with times t; bg = per-channel median of the
    whole test. Returns (summary dict, blows DataFrame)."""
    fs_env = fs_env or 1.0 / np.median(np.diff(t))
    n0, n1 = int(round(0.3 * fs_env)), int(round(1.0 * fs_env))
    pad = n1
    L = np.log10(np.maximum(E / bg, 1e-12))
    lE = np.log10(np.maximum(np.pad(E, ((pad, pad), (0, 0)), mode="edge"), 1e-12))
    nbh = np.concatenate([np.stack([np.roll(lE, s, 0) for s in range(n0, n1 + 1)]),
                          np.stack([np.roll(lE, -s, 0) for s in range(n0, n1 + 1)])])
    impul = (lE - np.median(nbh, axis=0))[pad:pad + len(L)]
    Li = np.where(impul >= imp, L, -1.0)
    m = Li.max(1)
    pk, _ = signal.find_peaks(m, height=math.log10(thr), distance=max(int(0.5 * fs_env), 1))
    cand = []
    for i in pk:
        j0, j1 = max(i - 1, 0), min(i + 2, len(L))
        c = int(np.argmax(Li[j0:j1].max(0)))
        prof = L[j0:j1].max(0)
        cr = float(c)
        if 0 < c < len(prof) - 1:
            y0, y1, y2 = prof[c - 1], prof[c], prof[c + 1]
            den = y0 - 2 * y1 + y2
            if den < 0:
                cr = c + 0.5 * (y0 - y2) / den
        cand.append((t[i], col0 + c, col0 + cr, m[i], impul[i, c]))
    cand = np.array(cand) if cand else np.zeros((0, 5))
    out = dict(n_candidates=len(cand), col=np.nan, col_mad=np.nan, n_blows=0, runner_up_col=np.nan,
               runner_up_score_ratio=np.nan, status="none")
    keep = np.zeros(len(cand), bool)
    st = cand[:, 4] >= strong if len(cand) else np.zeros(0, bool)
    if st.sum():
        wt = 10 ** cand[:, 3] * cand[:, 4] * np.exp(-0.5 * ((cand[:, 0] - t_log) / sigma_s) ** 2) * st
        groups = [(np.abs(cand[:, 2] - cand[i, 2]) <= group_cols) & (np.abs(cand[:, 0] - cand[i, 0]) <= group_s) & st
                  for i in np.flatnonzero(st)]
        sc = np.array([wt[g].sum() for g in groups])
        gb = groups[int(np.argmax(sc))]
        cmed = float(np.median(cand[gb, 2]))
        keep = (np.abs(cand[:, 2] - cmed) <= group_cols) & (np.abs(cand[:, 0] - np.median(cand[gb, 0])) <= 1.5 * group_s)
        other = [(s, float(np.median(cand[g, 2]))) for s, g in zip(sc, groups) if abs(np.median(cand[g, 2]) - cmed) > 3]
        out.update(col=cmed, col_mad=float(np.median(np.abs(cand[keep, 2] - cmed))), n_blows=int(keep.sum()),
                   status="ok" if keep.sum() >= 3 else "weak",
                   t_first_blow=float(cand[keep, 0].min()), t_last_blow=float(cand[keep, 0].max()))
        if other:
            s2, alt = max(other)
            out.update(runner_up_col=alt, runner_up_score_ratio=float(s2 / sc.max()))
    B = pd.DataFrame(cand, columns=["t", "col", "col_refined", "log10R", "impulsive"])
    B["in_sequence"] = keep
    return out, B


# --------------------------------------------------------------------------------------------------- stack
def env_snr(x, fs, t_axis, band=(15.0, 150.0), smooth_s=0.0125, noise=(-0.9, -0.2)):
    sos = signal.butter(4, band, "bandpass", fs=fs, output="sos")
    e = np.abs(signal.hilbert(signal.sosfiltfilt(sos, x, axis=0), axis=0))
    e = ndimage.uniform_filter1d(e, max(int(round(smooth_s * fs)), 1), axis=0)
    nz = (t_axis > noise[0]) & (t_axis < noise[1])
    return e / np.median(e[nz], axis=0)


def onset(e, t_axis, w=(-0.1, 0.35), frac=0.3):
    m = (t_axis > w[0]) & (t_axis < w[1])
    s = e[m]
    pk = s.max(0)
    return t_axis[m][np.argmax(s >= frac * pk, axis=0)], pk


def stack_shot(windows, fs, t_axis, cols, pick_col, band=(15.0, 150.0), keep_frac=0.3, foot_snr=6.0,
               near_frac=0.25, sec_frac=0.25, sim_snr=6.0, sim_dt=0.025, max_lag_s=0.03):
    """stack the blow windows (list of (n_t, n_ch) arrays on channels `cols`) of one shot point."""
    i0 = int(np.argmin(np.abs(cols - pick_col)))
    E, pk0 = [], []
    for x in windows:
        e = env_snr(np.asarray(x, float), fs, t_axis, band)
        t0, p0 = onset(e[:, [i0]], t_axis, (-0.15, 0.4))
        E.append(np.roll(e, -int(round(t0[0] * fs)), axis=0))
        pk0.append(p0[0])
    pk0 = np.array(pk0)
    keep = pk0 >= keep_frac * pk0.max()
    ref = np.log10(np.maximum(E[int(np.argmax(pk0))][:, i0], 1))
    w = (t_axis > -0.1) & (t_axis < 0.3)
    lags = np.arange(-int(round(max_lag_s * fs)), int(round(max_lag_s * fs)) + 1)
    E2 = []
    for e in (e for e, k in zip(E, keep) if k):
        x = np.log10(np.maximum(e[:, i0], 1))
        cc = [np.dot(np.roll(x, -lag)[w] - x[w].mean(), ref[w] - ref[w].mean()) for lag in lags]
        E2.append(np.roll(e, -int(lags[int(np.argmax(cc))]), axis=0))
    E2 = np.array(E2)
    S = 10 ** np.mean(np.log10(np.maximum(E2, 1)), axis=0)
    on_b, pk_b = map(np.array, zip(*[onset(e, t_axis) for e in E2]))
    ta, pk = onset(S, t_axis)
    ta = ta - np.median(ta[max(i0 - 1, 0):i0 + 2])
    on_b = on_b - np.median(on_b[:, max(i0 - 1, 0):i0 + 2], axis=1, keepdims=True)

    def grow(thr):
        lo = hi = i0
        while lo > 0 and pk[lo - 1] >= thr:
            lo -= 1
        while hi < len(cols) - 1 and pk[hi + 1] >= thr:
            hi += 1
        return lo, hi
    lo, hi = grow(foot_snr)
    foot = np.zeros(len(cols), bool)
    foot[lo:hi + 1] = True
    a0, b0 = grow(near_frac * pk[i0])
    wsum = pk[a0:b0 + 1]
    sim = ~foot & (pk >= sim_snr) & (np.abs(ta) <= sim_dt) & (np.mean(pk_b >= sim_snr / 2, axis=0) >= 0.5)
    sec = [i for i in range(1, len(cols) - 1) if abs(i - i0) >= 3 and pk[i] >= sec_frac * pk[i0]
           and pk[i] >= pk[i - 1] and pk[i] >= pk[i + 1] and pk[min(i, i0):max(i, i0) + 1].min() < 0.5 * pk[i]]
    j = int(np.argmax(pk))
    jr = float(j)
    if 0 < j < len(pk) - 1:
        y0, y1, y2 = np.log10(pk[j - 1:j + 2])
        den = y0 - 2 * y1 + y2
        if den < 0:
            jr = j + 0.5 * (y0 - y2) / den
    summary = dict(pick_col=float(pick_col), n_blows=len(windows), n_used=int(keep.sum()), peak_snr=float(pk[i0]),
                   stack_peak_col=float(cols[0] + jr), foot_from=int(cols[lo]), foot_to=int(cols[hi]),
                   foot_halfwidth_cols=(hi - lo) / 2, near_from=int(cols[a0]), near_to=int(cols[b0]),
                   near_width_cols=int(b0 - a0 + 1),
                   near_centroid_col=float(np.sum(cols[a0:b0 + 1] * wsum) / np.sum(wsum)),
                   secondary_cols=" ".join(str(int(cols[i])) for i in sec),
                   secondary_ratio=" ".join(f"{pk[i] / pk[i0]:.2f}" for i in sec),
                   simultaneous_cols=" ".join(str(int(c)) for c in cols[sim]))
    mad = np.array([np.median(np.abs(on_b[pk_b[:, i] >= foot_snr, i] - np.median(on_b[pk_b[:, i] >= foot_snr, i])))
                    if (pk_b[:, i] >= foot_snr).sum() >= 2 else np.nan for i in range(len(cols))])
    per_col = pd.DataFrame(dict(col=cols.astype(int), offset=(cols - cols[i0]).astype(int), peak_snr=pk,
                                delay_s=ta, delay_mad_s=mad, in_footprint=foot, simultaneous=sim))
    return summary, per_col, S


def moveout(per_col, map_dist_m):
    """onset delay vs map distance from the shot point inside the footprint: speed by least squares through 0
    and the residual in metres per channel (how well the map's spacing agrees with the travel times). Only good
    to ~10 m with ~ms timing: a check, not a way to place channels."""
    dd = np.asarray(map_dist_m, float) - np.asarray(map_dist_m, float)[np.argmin(np.abs(per_col.offset.to_numpy()))]
    tau = np.where(per_col.in_footprint, per_col.delay_s, np.nan)
    ok = np.isfinite(tau) & (dd >= 4.0)
    if ok.sum() < 2 or np.sum(dd[ok] * tau[ok]) <= 0:
        return np.nan, np.full(len(dd), np.nan)
    v = float(np.sum(dd[ok] ** 2) / np.sum(dd[ok] * tau[ok]))
    return v, np.where(ok, (tau - dd / v) * v, np.nan)


def equal_ratio_column(c_prev, c_next, path_prev_m, path_next_m):
    """the anchor channel that gives both neighbouring segments the same fibre / path ratio (for an anchor whose
    strong response is wide with the pick at one end; accept it only if it falls inside that response)."""
    return (c_prev * path_next_m + c_next * path_prev_m) / (path_prev_m + path_next_m)


# ----------------------------------------------------------------------------------------------- conventions
def convention_test(col, d_logged, conventions, spacing):
    """residual (picked - expected channel) in metres of fibre for each convention name: (offset_m, step_m)."""
    out = {}
    for name, (off, step) in conventions.items():
        exp = (np.asarray(d_logged, float) - off) / step
        r = (np.asarray(col, float) - exp) * spacing
        ok = np.isfinite(r)
        sl = np.polyfit(np.asarray(d_logged, float)[ok], r[ok], 1)[0] if ok.sum() > 2 else np.nan
        out[name] = dict(median_m=float(np.median(r[ok])), mad_m=float(np.median(np.abs(r[ok] - np.median(r[ok])))),
                         n=int(ok.sum()), n_within_2_channels=int((np.abs(r[ok]) <= 2 * spacing).sum()),
                         trend_m_per_km=float(sl * 1000), residual_m=r.tolist())
    return out


# ------------------------------------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="hammer / tap-test anchors")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--env", required=True)
    d.add_argument("--log", required=True)
    d.add_argument("--search-m", type=float, default=400.0, help="search +- this around the logged distance")
    d.add_argument("--convention", action="append", default=[],
                   help="name=offset,step to convert logged distances to channels (all are searched)")
    d.add_argument("--window-s", type=float, default=150.0, help="+- seconds around the logged time")
    d.add_argument("--thr", type=float, default=8.0)
    d.add_argument("--imp", type=float, default=0.6)
    d.add_argument("--out", required=True)
    d.add_argument("--blows-out")
    s = sub.add_parser("stack")
    s.add_argument("--blows", required=True)
    s.add_argument("--picks", required=True, help="CSV name, col")
    s.add_argument("--fs", type=float, required=True)
    s.add_argument("--t-start", type=float, required=True, help="time of the first sample relative to the blow")
    s.add_argument("--band", default="15,150")
    s.add_argument("--out", required=True)
    s.add_argument("--delays")
    s.add_argument("--map", help="channel map CSV (raw_col, lat, lon) for the moveout check")
    s.add_argument("--gps", help="CSV name, lat, lon of the shot points (for the moveout check)")
    c = sub.add_parser("conventions")
    c.add_argument("--picks", required=True)
    c.add_argument("--log", required=True)
    c.add_argument("--convention", action="append", required=True, help="name=offset,step")
    c.add_argument("--spacing", type=float, required=True)
    c.add_argument("--out")
    a = ap.parse_args()

    if a.cmd == "detect":
        z = np.load(a.env)
        E, t, col0 = z["env"], z["t"], int(z["col0"])
        bg = np.median(E[::10], axis=0)
        L = pd.read_csv(a.log)
        conv = {k: tuple(map(float, v.split(","))) for k, v in (x.split("=") for x in a.convention)} or {"index": (0.0, 1.0)}
        rows, blows = [], []
        for _, h in L.iterrows():
            iw = np.flatnonzero((t >= h.t_log_s - a.window_s) & (t <= h.t_log_s + a.window_s))
            if "d_logged_m" in h and np.isfinite(h.d_logged_m):
                cc = [(h.d_logged_m + sgn * a.search_m - off) / st for off, st in conv.values() for sgn in (-1, 1)]
                c0, c1 = max(int(np.floor(min(cc))) - col0, 0), min(int(np.ceil(max(cc))) - col0, E.shape[1] - 1)
            else:
                c0, c1 = 0, E.shape[1] - 1
            res, B = detect_shot(E[iw, c0:c1 + 1], t[iw], col0 + c0, h.t_log_s, bg[c0:c1 + 1], a.thr, a.imp)
            rows.append(dict(name=h["name"], **res))
            B.insert(0, "name", h["name"])
            blows.append(B)
        pd.DataFrame(rows).to_csv(a.out, index=False)
        if a.blows_out:
            pd.concat(blows).to_csv(a.blows_out, index=False)
        print(pd.DataFrame(rows).round(2).to_string(index=False))
    elif a.cmd == "stack":
        z = np.load(a.blows)
        P = pd.read_csv(a.picks)
        P["name"] = P["name"].astype(str)
        band = tuple(map(float, a.band.split(",")))
        keys = [k for k in z.files if not k.endswith(("_c0", "_t0"))]
        shots = {}
        for k in keys:
            shots.setdefault(re.sub(r"_\d+$", "", k), []).append(k)
        M = pd.read_csv(a.map).set_index("raw_col") if a.map else None
        G = pd.read_csv(a.gps).assign(name=lambda q: q["name"].astype(str)).set_index("name") if a.gps else None
        rows, per = [], []
        for sh, ks in sorted(shots.items()):
            name = str(int(re.sub(r"\D", "", sh))) if re.sub(r"\D", "", sh) else sh
            if name not in set(P.name):
                continue
            ks = sorted(ks)
            c0 = int(z[ks[0] + "_c0"])
            W = [z[k].astype(float) for k in ks]
            cols = c0 + np.arange(W[0].shape[1])
            t_axis = a.t_start + np.arange(W[0].shape[0]) / a.fs
            summ, pc, _ = stack_shot(W, a.fs, t_axis, cols, float(P.set_index("name").col[name]), band)
            if M is not None and G is not None and name in G.index:
                from cmap_geo import LocalXY
                q = M.reindex(cols)
                X = LocalXY.around(q.lat, q.lon)
                dist = X.dist(G.lat[name], G.lon[name], q.lat.to_numpy(), q.lon.to_numpy())
                v, res = moveout(pc, dist)
                pc["map_dist_m"], pc["resid_m"] = dist, res
                summ.update(v_mps=v, resid_median_abs_m=float(np.nanmedian(np.abs(res))) if np.isfinite(res).any() else np.nan)
            rows.append(dict(name=name, **summ))
            pc.insert(0, "name", name)
            per.append(pc)
        R = pd.DataFrame(rows)
        R.to_csv(a.out, index=False)
        if a.delays:
            pd.concat(per).to_csv(a.delays, index=False)
        pd.set_option("display.width", 220)
        print(R.round(2).to_string(index=False))
    else:
        P, L = pd.read_csv(a.picks), pd.read_csv(a.log)
        P["name"], L["name"] = P["name"].astype(str), L["name"].astype(str)
        Q = P.merge(L[["name", "d_logged_m"]], on="name")
        conv = {k: tuple(map(float, v.split(","))) for k, v in (x.split("=") for x in a.convention)}
        res = convention_test(Q.col, Q.d_logged_m, conv, a.spacing)
        for k, v in res.items():
            print(k, {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk != "residual_m"})
        if a.out:
            json.dump(dict(names=Q.name.tolist(), **res), open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
