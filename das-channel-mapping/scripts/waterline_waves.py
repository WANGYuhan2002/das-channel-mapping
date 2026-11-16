#!/usr/bin/env python3
"""Where the fibre leaves the sea: the waterline (and the end of a beach) from ocean-wave loading.

Wave pressure only acts on fibre under water; it is strongest in shallow water and the surf zone and vanishes on
land. So the extra low-frequency power in storm hours (swell ~0.07-0.15 Hz, wind sea ~0.18-0.35 Hz) has a step
where the cable comes out of the water. Two estimators:
  step       the largest one-channel drop of the storm wave power, scanning landward, inside a window: the edge
             lies between the two channels (best on the finest channel spacing, e.g. RAW 8 m rather than 16 m).
             A second step further landward can mark where the fibre leaves a beach (a plateau of wave noise,
             correlated with the sea state, between the two).
  half_rise  the channel where the power is half way (in dB) from the land level to the near-shore peak, also
             at 25 / 75 %: definition-dependent, so report the range, and bootstrap it over days if you have them.
Choose the land band, the peak band and the step windows by LOOKING at the profiles first (storm, calm,
storm - calm along the cable): they are visual judgements to agree with the user.

    python3 waterline_waves.py --table bandpower.csv --landward +1 --land 1800,1860 --peak 1740,1790 \
        --window 1758,1772 [--window 1770,1786] [--bands swell,windsea] [--ref 1700,1719] --out waterline.json
bandpower.csv: raw_col, <band>_storm_db, <band>_calm_db [, hourly columns <band>_h<k>_db for the sea-state
correlation]. band_power() turns hourly decimated strain-rate series into such columns (Welch, Hann segments).
--landward: +1 if land lies at higher channel numbers at this end, -1 if at lower.
"""
import argparse
import json

import numpy as np
import pandas as pd
from scipy import signal

BANDS = {"swell": (0.07, 0.15), "windsea": (0.18, 0.35), "short": (0.35, 0.7)}


def band_power(x, fs, bands=BANDS, nperseg=1024):
    """dB band power per channel of one hour of a decimated series x (n_t, n_ch) (Welch, 50 % overlap)."""
    f, P = signal.welch(np.asarray(x, float), fs, nperseg=nperseg, axis=0)
    return {b: 10 * np.log10(P[(f >= f0) & (f <= f1)].mean(0)) for b, (f0, f1) in bands.items()}


def step(c, y, win, landward=1):
    """largest one-channel drop of y going landward inside win = (c_lo, c_hi); returns (edge channel between
    the two channels, drop in dB)."""
    c, y = np.asarray(c, float), np.asarray(y, float)
    i = np.flatnonzero((c >= win[0]) & (c < win[1]))
    i = i[i + 1 < len(c)]
    d = (y[i + 1] - y[i]) * landward               # landward change
    k = int(np.argmin(d))
    return float(c[i[k]] + 0.5), float(d[k])


def half_rise(c, y, land, peak, frac=0.5, landward=1):
    """first channel, scanning seaward from the land band, where y reaches land + frac (peak - land)."""
    c, y = np.asarray(c, float), np.asarray(y, float)
    lo = np.median(y[(c >= land[0]) & (c <= land[1])])
    pk = (c >= peak[0]) & (c <= peak[1])
    lev = lo + frac * (np.max(y[pk]) - lo)
    ipk = np.flatnonzero(pk)[np.argmax(y[pk])]
    if landward > 0:                               # land at higher channels: scan downward from the land band
        start = int(np.flatnonzero(c <= land[0])[-1])
        for i in range(start, ipk, -1):
            if y[i] >= lev:
                return float(c[i] + (lev - y[i]) / (y[i + 1] - y[i])) if y[i + 1] != y[i] else float(c[i])
    else:
        start = int(np.flatnonzero(c >= land[1])[0])
        for i in range(start, ipk):
            if y[i] >= lev:
                return float(c[i] - (lev - y[i]) / (y[i - 1] - y[i])) if y[i - 1] != y[i] else float(c[i])
    return float("nan")


def seastate_r(T, band, ref):
    """correlation over the hours of each channel's band power with the mean of a reference group in the sea."""
    hc = sorted(k for k in T.columns if k.startswith(f"{band}_h") and k.endswith("_db"))
    if len(hc) < 5:
        return None
    W = T[hc].to_numpy().T
    r0 = W[:, (T.raw_col >= ref[0]).to_numpy() & (T.raw_col <= ref[1]).to_numpy()].mean(1)
    return np.array([np.corrcoef(r0, W[:, j])[0, 1] for j in range(W.shape[1])])


def main():
    ap = argparse.ArgumentParser(description="waterline from ocean-wave loading")
    ap.add_argument("--table", required=True)
    ap.add_argument("--bands", default="swell,windsea", help="bands averaged for the step (storm power, dB)")
    ap.add_argument("--landward", type=int, default=1, choices=(1, -1))
    ap.add_argument("--land", required=True, help="c_lo,c_hi of the land level")
    ap.add_argument("--peak", required=True, help="c_lo,c_hi of the near-shore peak")
    ap.add_argument("--window", action="append", required=True, help="c_lo,c_hi of a step (repeat for a beach end)")
    ap.add_argument("--ref", help="c_lo,c_hi of a sea reference group for the sea-state correlation")
    ap.add_argument("--spacing", type=float, default=float("nan"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    T = pd.read_csv(a.table)
    c = T.raw_col.to_numpy(float)
    bands = a.bands.split(",")
    wave = np.mean([T[f"{b}_storm_db"].to_numpy() for b in bands], axis=0)
    land, peak = tuple(map(float, a.land.split(","))), tuple(map(float, a.peak.split(",")))
    res = dict(bands=bands, landward=a.landward, steps=[])
    for w in a.window:
        e, d = step(c, wave, tuple(map(float, w.split(","))), a.landward)
        res["steps"].append(dict(window=w, edge_col=e, drop_db=d))
    if len(res["steps"]) >= 2:
        e1, e2 = sorted(s["edge_col"] for s in res["steps"][:2])
        m = (c > e1) & (c < e2)
        res["between_steps"] = dict(fibre_m=(e2 - e1) * a.spacing, cols=[e1, e2],
                                    **{f"{b}_excess_db": float(np.median((T[f"{b}_storm_db"] - T[f"{b}_calm_db"])[m]))
                                       for b in bands})
    for b in bands:
        for frac in (0.25, 0.5, 0.75):
            res[f"{b}_halfrise_{int(frac * 100)}_col"] = half_rise(c, T[f"{b}_storm_db"].to_numpy(), land, peak, frac,
                                                                   a.landward)
    if a.ref:
        r = seastate_r(T, bands[-1], tuple(map(float, a.ref.split(","))))
        if r is not None:
            res["seastate_r_median_land"] = float(np.median(r[(c >= land[0]) & (c <= land[1])]))
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
