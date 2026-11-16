#!/usr/bin/env python3
"""Coupling of every channel from regional earthquakes: find the fibre that does not follow the ground (coils,
loose slack, fibre in a cabin or a manhole).

Idea: events tens of km away reach a few-km array with nearly the same strength on every channel (distance
effects of a few tens of %), so a narrow, deep gap in the earthquake SNR along the cable is fibre that does not
sense the ground strain, while its noise stays normal. Use 5-10 events from at least 2-3 directions.
Per event and channel (band-pass, e.g. 2-20 Hz; NO common-mode removal, which could put earthquake signal back
onto silent fibre): SNR = RMS over the signal window / RMS over the pre-event window; signal = sqrt(mean square
over the signal window - over the noise window); medians over the events. Weak: median SNR < weak x the median
SNR of the channels within +-nb that are not weak themselves (two passes); runs of >= 2 weak channels (single
non-weak channels inside a run bridged). Per run: signal and noise relative to the non-weak channels around:
'weak coupling' if signal < weak x and noise < noisy x; 'noisy' if noise >= noisy x (not a coupling problem).
With an anchored-segment table (build_channel_map.py output) each run gets the segment it falls in and that
segment's extra fibre: slack shows up as one weak run per segment with extra fibre, of about that length.
Hammer strength is NOT coupling: a blow on the lid of a manhole shakes the coil inside it.

    python3 quake_coupling.py --data quakes.npz --events events.csv --fs 50 --band 2,20 --out coupling.csv \
        --runs weak_runs.csv [--segments channel_map_anchored_segments.csv] [--ref-cols 43:899]
quakes.npz: per event tag an array (n_t, n_ch) and <tag>_t0 = epoch time of its first sample; events.csv: tag,
t_utc (ISO origin time). Bandpass is applied here unless --band none (data already filtered).
"""
import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import ndimage, signal


def event_stats(x, t, sig=(2.0, 45.0), noi=(-28.0, -1.0)):
    """SNR, signal and noise RMS per channel of one event (t relative to the origin time)."""
    s, n = (t >= sig[0]) & (t <= sig[1]), (t >= noi[0]) & (t <= noi[1])
    ps, pn = np.mean(x[s] ** 2, 0), np.mean(x[n] ** 2, 0)
    return np.sqrt(ps / pn), np.sqrt(np.maximum(ps - pn, 0)), np.sqrt(pn)


def weak_runs(snr, sig, noi, weak=0.2, nb=30, noisy=2.0, passes=2):
    """weak channels, runs of >= 2 (one-channel gaps bridged) and per run signal / noise relative to the
    non-weak channels within nb. Returns (runs DataFrame, weak mask, run mask, reference SNR)."""
    snr = np.asarray(snr, float)
    w = np.zeros(len(snr), bool)
    ref = np.full(len(snr), np.nan)
    for _ in range(passes):
        ref = np.array([np.median(snr[max(i - nb, 0):i + nb + 1][~w[max(i - nb, 0):i + nb + 1]]) for i in range(len(snr))])
        w = snr < weak * ref
    runs = ndimage.binary_closing(w, np.ones(3, bool)) | w
    out = []
    lab, n = ndimage.label(runs)
    for i in range(1, n + 1):
        idx = np.flatnonzero(lab == i)
        a, b = int(idx[0]), int(idx[-1])
        if b == a:
            continue
        around = np.r_[max(a - nb, 0):a, b + 1:min(b + 1 + nb, len(snr))]
        around = around[~runs[around]]
        sr = float(np.median(sig[a:b + 1]) / np.median(sig[around]))
        nr = float(np.median(noi[a:b + 1]) / np.median(noi[around]))
        out.append(dict(col_from=a, col_to=b, n_cols=b - a + 1, snr_median=float(np.median(snr[a:b + 1])),
                        signal_rel=sr, noise_rel=nr,
                        kind="weak coupling" if sr < weak and nr < noisy else ("noisy" if nr >= noisy else "weak?")))
    return pd.DataFrame(out), w, runs, ref


def attach_segments(W, S, spacing):
    """segment (anchored table: segment, col_from, col_to, excess_m) of every run and its extra fibre."""
    seg, exc = [], []
    for r in W.itertuples():
        q = S[(S.col_from <= r.col_from) & (S.col_to >= r.col_to)]
        seg.append(q.segment.iloc[0] if len(q) else "")
        exc.append(float(q.excess_m.iloc[0]) if len(q) else np.nan)
    W = W.copy()
    W["fibre_m"] = W.n_cols * spacing
    W["segment"], W["segment_excess_m"] = seg, exc
    return W


def slack_match(W, S, excess_min=30.0):
    """do the weak runs sit in the segments with extra fibre? Per segment: extra fibre and weak-run fibre; the
    chance that k runs land in those segments at random = (their share of the channels) ** k."""
    S = S.copy()
    S["n_ch"] = S.col_to - S.col_from
    wk = W[W.kind == "weak coupling"]
    S["weak_runs"] = [int(((wk.col_from >= a) & (wk.col_to <= b)).sum()) for a, b in zip(S.col_from, S.col_to)]
    S["weak_fibre_m"] = [float(wk.fibre_m[(wk.col_from >= a) & (wk.col_to <= b)].sum()) for a, b in zip(S.col_from, S.col_to)]
    big = S.excess_m > excess_min
    share = float(S.n_ch[big].sum() / S.n_ch.sum())
    k = int(S.weak_runs[big].clip(upper=1).sum())
    return S, dict(segments_with_excess=int(big.sum()), of_them_with_one_weak_run=int((S.weak_runs[big] == 1).sum()),
                   other_segments_with_weak_runs=int((S.weak_runs[~big] > 0).sum()), other_segments=int((~big).sum()),
                   channel_share_of_excess_segments=share, chance=share ** k if k else None)


def main():
    ap = argparse.ArgumentParser(description="earthquake coupling test")
    ap.add_argument("--data", required=True)
    ap.add_argument("--events", required=True)
    ap.add_argument("--fs", type=float, required=True)
    ap.add_argument("--band", default="2,20", help="'lo,hi' Hz or 'none'")
    ap.add_argument("--signal", default="2,45", help="signal window after the origin (s)")
    ap.add_argument("--noise", default="-28,-1", help="noise window (s)")
    ap.add_argument("--weak", type=float, default=0.2)
    ap.add_argument("--nb", type=int, default=30)
    ap.add_argument("--ref-cols", help="a:b channels whose median signal normalises the strength (e.g. land)")
    ap.add_argument("--segments", help="anchored-segment table to attach runs to segments")
    ap.add_argument("--spacing", type=float, default=np.nan, help="channel spacing (m) for run lengths")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", required=True)
    a = ap.parse_args()
    z = np.load(a.data)
    E = pd.read_csv(a.events)
    sw, nw = tuple(map(float, a.signal.split(","))), tuple(map(float, a.noise.split(",")))
    sos = None if a.band == "none" else signal.butter(4, tuple(map(float, a.band.split(","))), "bandpass", fs=a.fs,
                                                       output="sos")
    snr, sig, noi = {}, {}, {}
    for _, e in E.iterrows():
        x = z[e.tag].astype(np.float64)
        if sos is not None:
            x = signal.sosfiltfilt(sos, x, axis=0)
        t0 = datetime.fromisoformat(str(e.t_utc)).replace(tzinfo=timezone.utc).timestamp()
        t = float(z[e.tag + "_t0"]) - t0 + np.arange(len(x)) / a.fs
        snr[e.tag], sig[e.tag], noi[e.tag] = event_stats(x, t, sw, nw)
    n = len(next(iter(snr.values())))
    C = pd.DataFrame(dict(raw_col=np.arange(n), snr_median=pd.DataFrame(snr).median(1),
                          signal_median=pd.DataFrame(sig).median(1), noise_median=pd.DataFrame(noi).median(1)))
    if a.ref_cols:
        lo, hi = map(int, a.ref_cols.split(":"))
        C["strength_median"] = pd.DataFrame({k: v / np.median(v[lo:hi + 1]) for k, v in sig.items()}).median(1)
    for k in snr:
        C[f"snr_{k}"] = snr[k]
    W, w, runs, ref = weak_runs(C.snr_median.to_numpy(), C.signal_median.to_numpy(), C.noise_median.to_numpy(),
                                a.weak, a.nb)
    C["snr_ref"], C["weak"], C["weak_run"] = ref, w, runs
    if len(W):
        W["fibre_m"] = W.n_cols * a.spacing
    if a.segments and len(W):
        S = pd.read_csv(a.segments)
        W = attach_segments(W, S, a.spacing)
        S2, ev = slack_match(W, S)
        print("slack match:", ev)
    C.to_csv(a.out, index=False, float_format="%.5g")
    W.to_csv(a.runs, index=False, float_format="%.4g")
    pd.set_option("display.width", 200)
    print(W.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
