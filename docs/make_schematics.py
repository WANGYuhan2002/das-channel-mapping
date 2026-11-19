#!/usr/bin/env python3
"""Schematic figures of the README (synthetic; nothing here is measured data).

    python3 docs/make_schematics.py          # writes docs/fig1_excess_fibre.png and docs/fig2_spatial_jump.png

One stretch of cable along a road, drawn with the numbers of a real case (channel spacing 8.17 m; a loop of 3
channels = 25 m of fibre; a coil of 19 channels = 155 m of fibre in a manhole between two tap-test shots):

fig1  (a) the scene: road, fibre, loop, coil, tap-test shots, a vehicle, an earthquake;
      (b) what an earthquake shows channel by channel: the amplitude drops on the loop and the coil;
      (c) what passing vehicles show: their tracks jump across the loop and the coil.
fig2  what happens if the excess fibre stays in the channel map: (a) position of each channel, (b) position error,
      (c, d) the arrivals of an earthquake against mapped position, before and after the excess fibre is taken out.
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, ConnectionPatch, Polygon, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DX = 8.17                                   # m of fibre per channel
SHOT = dict(A=3, B=18, C=58)                # tap-test shots: anchor channel of each
SLACK = [(11, 13, "loop"), (31, 49, "coil")]   # first channel, last channel, kind
N1 = 67                                     # channels shown in figure 1
COL = dict(fibre="#1f4e9c", slack="#d62728", shot="#1b7837", car="#01857a", quake="#8c510a", soil="#f1e7d3",
           rock="#e3d5ba", road="#555555", guide="#0a3d78", P="#2166ac", S="#e08214", grey="#6b6b6b")

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.labelsize": 11.5, "xtick.labelsize": 10.5,
                     "ytick.labelsize": 10.5, "savefig.facecolor": "white", "mathtext.fontset": "dejavusans"})


# ------------------------------------------------------------------ geometry
def true_x(c):
    """position along the road (m, from shot A) of channel c: the fibre inside a loop or coil does not advance."""
    c = np.asarray(c, float)
    x = (c - SHOT["A"]) * DX
    for a, b, _ in SLACK:
        x = x - np.clip(c - (a - 0.5), 0, b - a + 1) * DX
    return x


def is_slack(c):
    c = np.asarray(c)
    m = np.zeros(c.shape, bool)
    for a, b, _ in SLACK:
        m |= (c >= a) & (c <= b)
    return m


def map_spacing(c):
    """map 1: channel number x channel spacing, counted from shot A."""
    return (np.asarray(c, float) - SHOT["A"]) * DX


def map_anchors(c):
    """map 2: tap-test anchors only; channels spread evenly between two shots, at the channel spacing outside."""
    c = np.asarray(c, float)
    ca = np.array([SHOT[k] for k in "ABC"], float)
    xa = true_x(ca)
    x = np.interp(c, ca, xa)
    x = np.where(c < ca[0], xa[0] + (c - ca[0]) * DX, x)
    return np.where(c > ca[-1], xa[-1] + (c - ca[-1]) * DX, x)


def block_x(a, b):
    return float(true_x(0.5 * (a + b)))


def panel_title(ax, letter, text, y=1.0, fontsize=11.5, pad=6):
    ax.set_title(r"$\bf{(" + letter + r")}$ " + text, loc="left", fontsize=fontsize, pad=pad, y=y)


def box(color="0.2", fc="white", alpha=0.92, pad=0.25):
    return dict(boxstyle=f"round,pad={pad}", fc=fc, ec=color, lw=0.8, alpha=alpha)


# ------------------------------------------------------------------ figure 1
def fig1():
    FW, FH = 11.0, 10.85
    fig = plt.figure(figsize=(FW, FH))
    L, W = 0.070, 0.885

    def axes(top_in, h_in):
        return fig.add_axes([L, 1 - (top_in + h_in) / FH, W, h_in / FH])

    hS = 3.05
    axS = axes(0.62, hS)                    # scene
    axR = axes(4.87, 0.80)                  # channel ruler (the fans from the scene end on it)
    axQ = axes(6.05, 1.95)                  # earthquake
    axV = axes(8.38, 1.85)                  # vehicles
    c0, c1 = -1.5, N1 + 0.5
    xs0, xs1 = (c0 - SHOT["A"]) * DX, (c1 - SHOT["A"]) * DX
    ys0, ys1 = -3.45, 2.62
    axS.set_xlim(xs0, xs1)
    axS.set_ylim(ys0, ys1)
    axS.axis("off")
    ux = (xs1 - xs0) / (FW * W)                         # m per inch
    uy = (ys1 - ys0) / hS                               # y units per inch

    def D(pts, x, y, s=1.0):
        """points given in inches around the anchor (x, y) -> data coordinates."""
        p = np.atleast_2d(np.asarray(pts, float)) * s
        return np.c_[x + p[:, 0] * ux, y + p[:, 1] * uy]

    c = np.arange(N1)
    xt = true_x(c)
    slack = is_slack(c)
    yf = -0.72                                          # depth of the fibre in the drawing
    road_top = 0.17

    # ground, bedrock, road
    axS.add_patch(Rectangle((xs0, ys0), xs1 - xs0, -ys0, fc=COL["soil"], ec="none", zorder=0))
    xr = np.linspace(xs0, xs1, 200)
    yr = -2.55 + 0.10 * np.sin(xr / 55.0) + 0.05 * np.sin(xr / 17.0)
    axS.fill_between(xr, ys0, yr, color=COL["rock"], lw=0, zorder=0.5)
    axS.plot(xr, yr, color="#c9b68f", lw=0.8, zorder=0.6)
    axS.add_patch(Rectangle((xs0, 0), xs1 - xs0, road_top, fc=COL["road"], ec="none", zorder=3))

    # earthquake: source below the right end, wavefronts through the ground
    xq, yq = xs1 - 1.05 * ux, ys0 + 0.20 * uy
    th = np.radians(np.linspace(8, 179, 400))
    for r in np.arange(0.45, 12.0, 0.55):
        xa, ya = xq + r * ux * np.cos(th), yq + r * uy * np.sin(th)
        ya = np.where((ya < -0.03) & (xa > xs0) & (xa < xs1), ya, np.nan)
        axS.plot(xa, ya, color=COL["quake"], lw=1.2, alpha=max(0.16, 0.62 - 0.05 * r), zorder=1)
    axS.plot(xq, yq, marker="*", ms=20, color=COL["quake"], mec="white", mew=0.8, zorder=6)
    axS.text(xq, yq + 0.33 * uy, "earthquake", fontsize=10.5, color=COL["quake"], va="bottom", ha="center",
             fontweight="bold", bbox=dict(fc=COL["rock"], ec="none", pad=1.0, alpha=0.85), zorder=6)

    # fibre: straight along the road, into the loop box and the coil manhole
    def helix(xc, rx_in, ry_in, turns, pitch_in, n_dots):
        th_ = np.linspace(np.pi, np.pi + 2 * np.pi * turns, int(200 * turns))
        k = (th_ - np.pi) / (2 * np.pi)
        pts = np.c_[rx_in * np.cos(th_), -ry_in * np.sin(th_) - pitch_in * k]
        thd = np.pi + 2 * np.pi * turns * (np.arange(n_dots) + 0.5) / n_dots
        kd = (thd - np.pi) / (2 * np.pi)
        dots = np.c_[rx_in * np.cos(thd), -ry_in * np.sin(thd) - pitch_in * kd]
        return D(pts, xc, yf), D(dots, xc, yf)

    segs, last, shapes = [], xs0, {}
    for a, b, kind in SLACK:
        xb = block_x(a, b)
        if kind == "coil":
            rx, ry, turns, pitch, wall, depth = 0.235, 0.075, 4.5, 0.125, 0.085, 0.86
        else:
            rx, ry, turns, pitch, wall, depth = 0.125, 0.060, 1.5, 0.085, 0.07, 0.42
        line, dots = helix(xb, rx, ry, turns, pitch, b - a + 1)
        up = np.array([[line[-1, 0], line[-1, 1]], [line[-1, 0] + 0.035 * ux, 0.5 * (line[-1, 1] + yf)],
                       [line[-1, 0], yf]])
        shapes[kind] = dict(x=xb, rx=rx, wall=wall, depth=depth, line=line, dots=dots, up=up,
                            w=(rx + wall) * ux, bottom=yf - depth * uy - 0.16 * uy)
        segs.append(([last, line[0, 0]], [yf, yf]))
        last = line[-1, 0]
    segs.append(([last, xs1], [yf, yf]))
    for kind, s in shapes.items():                      # boxes first, then fibre
        axS.add_patch(Rectangle((s["x"] - s["w"], s["bottom"]), 2 * s["w"], -s["bottom"], fc="#fbfbfb", ec="#3a3a3a",
                                lw=1.3, zorder=2))
        axS.add_patch(Rectangle((s["x"] - 0.8 * s["w"], road_top - 0.02), 1.6 * s["w"], 0.10, fc="#222222",
                                ec="none", zorder=4))
    for xx, yy in segs:
        axS.plot(xx, yy, color=COL["fibre"], lw=2.0, zorder=5, solid_capstyle="butt")
    for kind, s in shapes.items():
        axS.plot(s["line"][:, 0], s["line"][:, 1], color=COL["slack"], lw=1.7, zorder=5)
        axS.plot(s["up"][:, 0], s["up"][:, 1], color=COL["slack"], lw=1.7, zorder=5)
        axS.plot(s["dots"][:, 0], s["dots"][:, 1], "o", ms=3.6, color=COL["slack"], mec="white", mew=0.4, zorder=7)
    axS.plot(xt[~slack], np.full((~slack).sum(), yf), "o", ms=4.3, color="black", mec="white", mew=0.5, zorder=7)
    xmore = xt[-1] + DX * np.arange(1, 40)              # the cable goes on: channels not shown in (b), (c)
    xmore = xmore[xmore < xs1 - 4]
    axS.plot(xmore, np.full(len(xmore), yf), "o", ms=3.4, color="0.55", mec="white", mew=0.4, zorder=6)
    sl, sc = shapes["loop"], shapes["coil"]
    axS.text(sl["x"], road_top + 0.17 * uy, "loop", ha="center", va="bottom", fontsize=10.5, color=COL["slack"],
             fontweight="bold")
    axS.text(sc["x"], road_top + 0.17 * uy, "coil in a\nmanhole", ha="center", va="bottom", fontsize=10.5,
             color=COL["slack"], fontweight="bold", linespacing=1.05)

    # tap-test shots (hammer + GPS point)
    def hammer(x):
        head = np.array([[-0.065, -0.036], [0.065, -0.036], [0.065, 0.036], [-0.065, 0.036]])
        ang = np.radians(-38)
        R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
        hc = np.array([0.045, 0.125])
        axS.add_patch(Polygon(D(head @ R.T + hc, x, road_top), closed=True, fc=COL["shot"], ec="white", lw=0.6,
                              zorder=8))
        hl = D([hc, hc + np.array([0.215, 0.165])], x, road_top)
        axS.plot(hl[:, 0], hl[:, 1], color=COL["shot"], lw=2.6, solid_capstyle="round", zorder=7.5)
        for dxi, dyi in [(-0.10, 0.055), (-0.125, 0.0), (-0.075, 0.115)]:
            p = D([[dxi * 0.55, 0.02 + dyi * 0.55], [dxi, 0.02 + dyi]], x, road_top)
            axS.plot(p[:, 0], p[:, 1], color=COL["shot"], lw=1.1, zorder=7.5)

    for k, cc in SHOT.items():
        x = float(true_x(cc))
        hammer(x)
        axS.text(x + 0.10 * ux, road_top + 0.36 * uy, k, ha="center", va="bottom", fontsize=12.5,
                 fontweight="bold", color=COL["shot"])
    xA, xB, xC = (float(true_x(SHOT[k])) for k in "ABC")

    def road_len(x0, x1, y, text):
        axS.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<|-|>", color=COL["shot"], lw=1.2,
                                                           shrinkA=0, shrinkB=0, mutation_scale=11))
        for xx in (x0, x1):
            axS.plot([xx, xx], [y - 0.12, y + 0.12], color=COL["shot"], lw=1.2)
        axS.text(0.5 * (x0 + x1), y + 0.10, text, ha="center", va="bottom", fontsize=10.3, color=COL["shot"])

    road_len(xA, xB, 1.92, f"road A–B: {xB - xA:.0f} m")
    road_len(xB, xC, 1.92, f"road B–C: {xC - xB:.0f} m")

    # vehicle on the road, heading right
    def car(x, s=1.0, color=COL["car"]):
        body = [(-0.31, 0.055), (-0.31, 0.125), (-0.285, 0.15), (-0.20, 0.158), (-0.125, 0.238), (0.06, 0.238),
                (0.165, 0.158), (0.27, 0.142), (0.31, 0.112), (0.31, 0.055)]
        win = [(-0.108, 0.162), (-0.082, 0.214), (0.048, 0.214), (0.128, 0.162)]
        axS.add_patch(Polygon(D(body, x, road_top, s), closed=True, fc=color, ec="white", lw=0.8, zorder=8))
        axS.add_patch(Polygon(D(win, x, road_top, s), closed=True, fc="#e8f4f2", ec="none", zorder=8.5))
        tt = np.linspace(0, 2 * np.pi, 40)
        for wx in (-0.19, 0.19):
            axS.add_patch(Polygon(D(np.c_[wx + 0.048 * np.cos(tt), 0.048 + 0.048 * np.sin(tt)], x, road_top, s),
                                  closed=True, fc="#1a1a1a", ec="white", lw=0.6, zorder=9))
    xcar = (19.4 - SHOT["A"]) * DX
    car(xcar, 1.10)
    axS.annotate("", (xcar + 0.70 * ux, road_top + 0.17 * uy), (xcar + 0.40 * ux, road_top + 0.17 * uy),
                 arrowprops=dict(arrowstyle="-|>", color=COL["car"], lw=1.8, mutation_scale=13))
    axS.text(xcar - 0.02 * ux, road_top + 0.34 * uy, "vehicle", ha="center", va="bottom", fontsize=10.5,
             color=COL["car"], fontweight="bold")

    # legend of the scene (sky, right)
    lw_in, dy = 3.62, 0.195 * uy
    lx, ly = xs1 - lw_in * ux, ys1 - 0.20 * uy
    axS.add_patch(Rectangle((lx, ly - 4 * dy - 0.15 * uy), lw_in * ux - 1.0, 4 * dy + 0.30 * uy, fc="white",
                            ec="0.6", lw=0.8, zorder=10))
    rows = [("fibre", "optical fibre in a duct under the road"),
            ("chan", "channel: one every 8.17 m of fibre"),
            ("slack", "channel inside a loop or a coil"),
            ("shot", "tap-test shot: hammer blow at a GPS point"),
            ("quake", "earthquake wavefront")]
    for i, (kind, text) in enumerate(rows):
        y = ly - i * dy
        xk = lx + 0.27 * ux
        if kind == "fibre":
            axS.plot([xk - 0.15 * ux, xk + 0.15 * ux], [y, y], color=COL["fibre"], lw=2.0, zorder=11)
        elif kind == "chan":
            axS.plot(xk, y, "o", ms=4.6, color="black", mec="white", mew=0.5, zorder=11)
        elif kind == "slack":
            axS.plot(xk, y, "o", ms=4.6, color=COL["slack"], mec="white", mew=0.5, zorder=11)
        elif kind == "shot":
            axS.plot(xk, y, "v", ms=7.5, color=COL["shot"], zorder=11)
        else:
            ta = np.radians(np.linspace(50, 130, 30))
            axS.plot(xk + 0.22 * ux * np.cos(ta), y - 0.17 * uy + 0.22 * uy * np.sin(ta), color=COL["quake"], lw=1.4,
                     zorder=11)
        axS.text(lx + 0.52 * ux, y, text, ha="left", va="center", fontsize=9.8, zorder=11)
    panel_title(axS, "a", "A DAS cable under a road, seen from the side (not to scale). Spare fibre is stored in a "
                "loop and in a coil:\nall of their channels are at one point of the road.", y=1.0, pad=4)

    # ---------- channel ruler: what the interrogator counts
    axR.set_xlim(c0, c1)
    axR.set_ylim(0, 1)
    axR.axis("off")
    yd, yt_, ya_, yl_ = 0.66, 0.90, 0.36, 0.13
    for a, b, kind in SLACK:
        axR.add_patch(Rectangle((a - 0.5, yd - 0.13), b - a + 1, 1.0 - (yd - 0.13), fc=COL["slack"], ec="none",
                                alpha=0.14))
    axR.plot(c[~slack], np.full((~slack).sum(), yd), "o", ms=4.3, color="black", zorder=5)
    axR.plot(c[slack], np.full(slack.sum(), yd), "o", ms=4.3, color=COL["slack"], zorder=5)
    for k, cc in SHOT.items():
        axR.plot(cc, yt_, "v", ms=9, color=COL["shot"], zorder=6, clip_on=False)
    nAB, nBC = SHOT["B"] - SHOT["A"], SHOT["C"] - SHOT["B"]
    eAB, eBC = nAB * DX - (xB - xA), nBC * DX - (xC - xB)
    for ca, cb, text in [(SHOT["A"], SHOT["B"], f"fibre A–B: {nAB * DX:.0f} m → {eAB:.0f} m in excess"),
                         (SHOT["B"], SHOT["C"], f"fibre B–C: {nBC} channels × 8.17 m = {nBC * DX:.0f} m   →   "
                          f"{eBC:.0f} m in excess")]:
        axR.annotate("", (ca, ya_), (cb, ya_), arrowprops=dict(arrowstyle="<|-|>", color=COL["fibre"], lw=1.2,
                                                               shrinkA=0, shrinkB=0, mutation_scale=11))
        for xx in (ca, cb):
            axR.plot([xx, xx], [ya_ - 0.09, yd - 0.08], color=COL["fibre"], lw=1.0)
        axR.text(0.5 * (ca + cb), yl_, text, ha="center", va="center", fontsize=10.3, color=COL["fibre"],
                 bbox=dict(fc="white", ec="none", pad=1.0, alpha=0.85))

    # ---------- guides from the scene to the ruler
    def P_fig(ax, x, y):
        return fig.transFigure.inverted().transform(ax.transData.transform((x, y)))

    for a, b, kind in SLACK:
        s = shapes[kind]
        apex = P_fig(axS, s["x"], s["bottom"])
        p1, p2 = P_fig(axR, a - 0.5, 1.0), P_fig(axR, b + 0.5, 1.0)
        fig.add_artist(Polygon([apex, p2, p1], closed=True, fc=COL["slack"], ec="none", alpha=0.14,
                               transform=fig.transFigure, zorder=1))
        for p in (p1, p2):
            fig.add_artist(plt.Line2D([apex[0], p[0]], [apex[1], p[1]], color=COL["slack"], lw=1.0,
                                      transform=fig.transFigure, zorder=1.5))
    for k, cc in SHOT.items():
        fig.add_artist(ConnectionPatch(xyA=(float(true_x(cc)), -0.02), coordsA=axS.transData, xyB=(cc, yt_ + 0.07),
                                       coordsB=axR.transData, axesA=axS, axesB=axR, color=COL["shot"], lw=1.2,
                                       ls=(0, (4, 2.5)), zorder=2))
    xl = P_fig(axR, 10.2, 0)[0]                         # texts in the gap between the scene and the ruler
    fig.text(xl, 1 - 4.40 / FH, "3 channels =\n25 m of fibre\nat one point", ha="right", va="center",
             fontsize=9.8, color=COL["slack"], linespacing=1.1)
    xm = P_fig(axR, 38.4, 0)[0]
    fig.text(xm, 1 - 4.57 / FH, "19 channels =\n155 m of fibre\nat one point", ha="center",
             va="center", fontsize=9.8, color=COL["slack"], linespacing=1.1)
    xr_ = P_fig(axR, c1, 0)[0]
    fig.text(xr_, 1 - 4.05 / FH, f"beyond the coil, every channel\nis {eAB + eBC:.0f} m further along the\n"
             "fibre than along the road", ha="right", va="center", fontsize=9.8, color=COL["guide"],
             linespacing=1.15)

    # ---------- (b) earthquake record section, one trace per channel
    rng = np.random.default_rng(7)
    fs, T = 100.0, 10.0
    t = np.arange(0, T, 1 / fs)
    tP, tS = 1.8, 4.3

    def band_noise(n, lo, hi):
        f = np.fft.rfftfreq(n, 1 / fs)
        s = np.fft.rfft(rng.standard_normal(n))
        s[(f < lo) | (f > hi)] = 0
        y = np.fft.irfft(s, n)
        return y / np.std(y)

    carrier = band_noise(len(t) + 400, 0.8, 3.2)
    env = (0.30 * np.exp(-(t - tP) / 1.6) * (t >= tP) + 1.0 * np.exp(-(t - tS) / 2.4) * (t >= tS))
    axQ.set_xlim(c0, c1)
    axQ.set_ylim(T, 0)
    for a, b, kind in SLACK:
        axQ.axvspan(a - 0.5, b + 0.5, color=COL["slack"], alpha=0.10, lw=0)
    for i in c:
        sh = int(round((xt[i] / 9000.0 + 0.010 * rng.standard_normal()) * fs)) + 200
        u = env * carrier[sh:sh + len(t)] * np.exp(0.20 * rng.standard_normal())
        u = u * (0.055 if slack[i] else 1.0) + 0.016 * band_noise(len(t), 0.8, 8.0)
        u = np.clip(u * 0.50, -1.5, 1.5)
        col = COL["slack"] if slack[i] else "0.12"
        axQ.plot(i + u, t, color=col, lw=0.6)
        axQ.fill_betweenx(t, i, i + u, where=u > 0, color=col, lw=0, alpha=0.85)
    axQ.set_ylabel("Time (s)")
    axQ.set_xticklabels([])
    for lab, tt in (("P", tP), ("S", tS)):
        axQ.annotate(lab, (c1 - 0.1, tt), (c1 + 2.0, tt), ha="left", va="center", fontsize=11.5, fontweight="bold",
                     color=COL["quake"], annotation_clip=False,
                     arrowprops=dict(arrowstyle="-|>", color=COL["quake"], lw=1.3, shrinkA=1, shrinkB=0))
    axQ.text(40, 0.95, "coil: the amplitude drops", ha="center", va="center", fontsize=10.5, color=COL["slack"],
             bbox=box(COL["slack"]), zorder=9)
    axQ.annotate("loop", (12, 0.95), (7.0, 0.95), ha="center", va="center", fontsize=10.5, color=COL["slack"],
                 bbox=box(COL["slack"]), zorder=9,
                 arrowprops=dict(arrowstyle="-|>", color=COL["slack"], lw=1.1, shrinkB=2))
    panel_title(axQ, "b", "Earthquake, one trace per channel: the amplitude drops on the channels of the loop and of "
                "the coil.")

    # ---------- (c) vehicles: signal strength against channel and time
    Tv, fv = 70.0, 10.0
    tv = np.arange(0, Tv, 1 / fv)
    ci = np.arange(-3, N1 + 3)
    xi, si = true_x(ci), is_slack(ci)
    cars = [(+1, 12.5, 2.0, xi[0] - 5.0), (-1, 15.0, 39.0, xi[-1] + 5.0)]       # direction, m/s, start s, start m
    img = 0.05 * np.abs(rng.standard_normal((len(tv), len(ci))))
    for d, v, t0, x0 in cars:
        xc_t = x0 + d * v * (tv - t0)
        resp = np.exp(-0.5 * ((xc_t[:, None] - xi[None, :]) / 7.5) ** 2)
        img += resp * np.where(si, 0.62, 1.0)[None, :] * (tv[:, None] >= t0)
    axV.imshow(img, aspect="auto", origin="upper", cmap="magma", vmin=0, vmax=1.0,
               extent=[ci[0] - 0.5, ci[-1] + 0.5, Tv, 0], interpolation="bilinear")
    axV.set_xlim(c0, c1)
    axV.set_ylim(Tv, 0)
    axV.set_ylabel("Time (s)")
    axV.set_xlabel("Channel number along the fibre (one channel every 8.17 m of fibre)")
    for a, b, kind in SLACK:
        for e in (a - 0.5, b + 0.5):
            axV.axvline(e, color=COL["slack"], lw=1.0, ls=(0, (3, 2)))
    d, v, t0, x0 = cars[0]                               # the first vehicle if the coil channels lay along the road
    ca_, cb_ = SLACK[1][0], SLACK[1][1]
    t_at = lambda x: t0 + (x - x0) / v                                         # noqa: E731
    t_coil = t_at(block_x(ca_, cb_))
    would = lambda cc: t_at(true_x(ca_ - 1)) + (cc - (ca_ - 1)) * DX / v      # noqa: E731
    cc_ = np.array([ca_ - 1, c1], float)
    axV.plot(cc_, would(cc_), color="white", lw=1.3, ls=(0, (1, 2.2)))
    wb = dict(boxstyle="round,pad=0.25", fc="black", ec="white", lw=0.8, alpha=0.8)
    axV.annotate("jump: the vehicle passes all 19 coil channels\nat the same moment",
                 (0.5 * (ca_ + cb_), t_coil - 1.2), (44.0, 8.0), ha="center", va="center", fontsize=10.2,
                 color="white", bbox=wb, arrowprops=dict(arrowstyle="-|>", color="white", lw=1.1))
    axV.annotate("the track if these channels\nlay along the road", (41.5, would(41.5) + 0.6), (40.3, 42.5),
                 ha="center", va="center", fontsize=10.2, color="white", bbox=wb,
                 arrowprops=dict(arrowstyle="-|>", color="white", lw=1.1))
    axV.text(2.0, 14.5, "vehicle 1 →", color="white", fontsize=10.2, ha="left", va="center", bbox=wb)
    axV.text(60.5, 56.0, "← vehicle 2", color="white", fontsize=10.2, ha="center", va="center", bbox=wb)
    panel_title(axV, "c", "Passing vehicles, signal strength per channel: each track jumps across the loop and "
                "across the coil.")
    for ax in (axQ, axV):
        ax.tick_params(length=3.5)
    out = os.path.join(HERE, "fig1_excess_fibre.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out)
    print(f"  road A-B {xB - xA:.1f} m, fibre {nAB * DX:.1f} m, excess {eAB:.1f} m; road B-C {xC - xB:.1f} m, fibre "
          f"{nBC * DX:.1f} m, excess {eBC:.1f} m")


# ------------------------------------------------------------------ figure 2
def fig2():
    VP, VS = 3000.0, 1200.0                 # apparent velocities along the cable (m/s) of the synthetic arrivals
    n = 96
    c = np.arange(n)
    xt, x1, x2 = true_x(c), map_spacing(c), map_anchors(c)
    slack = is_slack(c)
    fig = plt.figure(figsize=(11.0, 9.8))
    gs = fig.add_gridspec(2, 2, left=0.075, right=0.925, top=0.858, bottom=0.063, hspace=0.37, wspace=0.34,
                          height_ratios=[1.0, 1.15])
    cmax = N1 - 1
    ls1, ls2 = (0, (5, 2)), (0, (6, 1.5, 1.2, 1.5))

    # (a) where each channel is
    a = fig.add_subplot(gs[0, 0])
    for lo, hi, kind in SLACK:
        a.axvspan(lo - 0.5, hi + 0.5, color=COL["slack"], alpha=0.10, lw=0)
    h1, = a.plot(c, x1, color=COL["grey"], lw=1.9, ls=ls1)
    h2, = a.plot(c, x2, color=COL["shot"], lw=1.9, ls=ls2)
    h0, = a.plot(c, xt, color="black", lw=2.4)
    hs, = a.plot(c[slack], xt[slack], "o", ms=3.8, color=COL["slack"], zorder=5)
    for k, cc in SHOT.items():
        ha_, = a.plot(cc, float(true_x(cc)), "v", ms=9, color=COL["shot"], zorder=6)
        a.text(cc - 1.2, float(true_x(cc)) + 22, k, color=COL["shot"], fontsize=11.5, fontweight="bold",
               ha="center", va="bottom")
    a.set_xlim(-1.5, cmax + 1.5)
    a.set_ylim(-45, 560)
    a.set_xlabel("Channel number along the fibre")
    a.set_ylabel("Position along the road from shot A (m)")
    cq = 62
    a.annotate("", (cq, float(true_x(cq))), (cq, float(map_spacing(cq))),
               arrowprops=dict(arrowstyle="<|-|>", color=COL["grey"], lw=1.3, shrinkA=0, shrinkB=0))
    a.text(cq - 1.0, 0.5 * float(true_x(cq) + map_spacing(cq)), f"{float(map_spacing(cq) - true_x(cq)):.0f} m",
           ha="right", va="center", fontsize=10.5, color=COL["grey"], fontweight="bold")
    a.text(42.5, float(true_x(40)) - 62, "19 channels,\none position", ha="center", va="top", fontsize=10,
           color=COL["slack"], linespacing=1.1)
    a.text(12, float(true_x(12)) - 30, "3 channels", ha="left", va="top", fontsize=10, color=COL["slack"])
    panel_title(a, "a", "Channel number is not position")
    fig.legend([h0, hs, ha_, h1, h2],
               ["where each channel is: the loop and the coil each at one point of the road",
                "channels inside the loop and inside the coil",
                "tap-test shots A, B, C: the channel at a GPS point",
                "map 1: position = channel number × channel spacing, counted from shot A",
                "map 2: the tap-test shots as anchors, the channels spread evenly between two shots"],
               loc="upper left", bbox_to_anchor=(0.070, 0.998), ncol=1, fontsize=10, frameon=False,
               handlelength=3.0, labelspacing=0.28)

    # (b) position error of the two maps that leave the excess fibre in
    b = fig.add_subplot(gs[0, 1])
    for lo, hi, kind in SLACK:
        b.axvspan(lo - 0.5, hi + 0.5, color=COL["slack"], alpha=0.10, lw=0)
    b.axhline(0, color="black", lw=2.2)
    b.plot(c, x1 - xt, color=COL["grey"], lw=1.9, ls=ls1)
    b.plot(c, x2 - xt, color=COL["shot"], lw=1.9, ls=ls2)
    for k, cc in SHOT.items():
        b.plot(cc, 0, "v", ms=9, color=COL["shot"], zorder=6)
    e2 = (x2 - xt)[: cmax + 1]
    i_lo, i_hi = int(np.argmin(e2)), int(np.argmax(e2))
    b.annotate(f"−{abs(e2[i_lo]):.0f} m", (i_lo, e2[i_lo]), (i_lo - 3.5, e2[i_lo] - 4), ha="right", va="center",
               fontsize=10.5, color=COL["shot"], fontweight="bold",
               arrowprops=dict(arrowstyle="-", color=COL["shot"], lw=0.9))
    b.annotate(f"+{e2[i_hi]:.0f} m", (i_hi, e2[i_hi]), (i_hi + 3.0, e2[i_hi] + 28), ha="left", va="center",
               fontsize=10.5, color=COL["shot"], fontweight="bold",
               arrowprops=dict(arrowstyle="-", color=COL["shot"], lw=0.9))
    e1 = (x1 - xt)[cmax]
    b.text(cmax + 0.8, e1 + 9, f"+{e1:.0f} m on every\nchannel that follows", ha="right", va="bottom", fontsize=10.5,
           color=COL["grey"], fontweight="bold", linespacing=1.1)
    b.text(16, e1 * 0.14 + 9, "+25 m", ha="center", va="bottom", fontsize=10.5, color=COL["grey"],
           fontweight="bold")
    b.set_xlim(-1.5, cmax + 1.5)
    b.set_ylim(-80, 245)
    b.set_xlabel("Channel number along the fibre")
    b.set_ylabel("Mapped position − true position (m)")
    b2 = b.twinx()
    b2.set_ylim(b.get_ylim())
    b2.set_ylabel("Arrival-time error for a wave travelling\nalong the cable at 1 km/s (ms)", fontsize=10.5)
    panel_title(b, "b", "Position error if the excess fibre stays in the map")

    # (c, d) the arrivals of an earthquake against mapped position
    fs = 2000.0
    t = np.arange(0, 0.66, 1 / fs)
    tP = 0.055 + (xt - xt[0]) / VP
    tS = 0.115 + (xt - xt[0]) / VS

    def ricker(tt, f0):
        q = (np.pi * f0 * tt) ** 2
        return (1 - 2 * q) * np.exp(-q)

    rng = np.random.default_rng(3)
    U = np.zeros((len(t), n))
    for i in c:
        amp = 0.07 if slack[i] else 1.0
        U[:, i] = amp * (0.55 * ricker(t - tP[i] - 0.011, 45.0) + 1.0 * ricker(t - tS[i] - 0.016, 30.0))
        U[:, i] += 0.012 * rng.standard_normal(len(t))
    xlim = (-40, 545)

    def section(ax, xmap, keep, title, letter):
        xm = xmap[keep]
        order = np.argsort(xm)
        edges = np.r_[xm[order][0] - DX / 2, 0.5 * (xm[order][1:] + xm[order][:-1]), xm[order][-1] + DX / 2]
        ax.pcolormesh(edges, t, np.maximum(U[:, keep][:, order][:-1, :], 0), cmap="Greys", vmin=0, vmax=0.62,
                      shading="flat", rasterized=True)
        xx = np.array(xlim, float)
        for v, t0, col in ((VP, 0.055, COL["P"]), (VS, 0.115, COL["S"])):
            ax.plot(xx, t0 + (xx - xt[0]) / v, color=col, lw=1.5, ls=(0, (4, 2.2)), zorder=4)
        ax.set_xlim(*xlim)
        ax.set_ylim(0.66, 0)
        ax.set_xlabel("Mapped position along the road from shot A (m)")
        ax.set_ylabel("Time (s)")
        panel_title(ax, letter, title)

    wb = dict(boxstyle="round,pad=0.25", fc="white", ec=COL["slack"], lw=0.8, alpha=0.96)
    cc_ = fig.add_subplot(gs[1, 0])
    all_ = np.ones(n, bool)
    section(cc_, x1, all_, "Earthquake arrivals placed with map 1: a flat step,\nthen every pick is out of place",
            "c")
    r = ~slack
    cc_.plot(x1[r], tP[r], "o", ms=3.0, color=COL["P"], zorder=6, label="P picks")
    cc_.plot(x1[r], tS[r], "o", ms=3.0, color=COL["S"], zorder=6, label="S picks")
    cc_.plot(x1[slack], tP[slack], "o", ms=3.4, mfc="white", mec=COL["slack"], mew=1.0, zorder=6)
    cc_.plot(x1[slack], tS[slack], "o", ms=3.4, mfc="white", mec=COL["slack"], mew=1.0, zorder=6,
             label="picks on the loop / coil channels")
    cc_.plot([], [], color="0.3", lw=1.5, ls=(0, (4, 2.2)), label="arrival times predicted\nfor these positions")
    cc_.legend(loc="lower left", fontsize=9.2, framealpha=0.96, borderaxespad=0.5, handlelength=2.4)
    lo, hi = SLACK[1][0], SLACK[1][1]
    xa_, xb_ = float(map_spacing(lo - 0.5)), float(map_spacing(hi + 0.5))
    tp_c, ts_c = float(tP[lo]), float(tS[lo])
    cc_.annotate("19 picks with the same arrival time,\nspread over 155 m: a jump in space",
                 (0.5 * (xa_ + xb_), tp_c - 0.008), (0.5 * (xa_ + xb_) + 62, 0.043), ha="center", va="center",
                 fontsize=10, color=COL["slack"], bbox=wb, linespacing=1.1,
                 arrowprops=dict(arrowstyle="-|>", color=COL["slack"], lw=1.1))
    cc_.annotate("", (xa_, ts_c + 0.024), (xb_, ts_c + 0.024),
                 arrowprops=dict(arrowstyle="<|-|>", color=COL["slack"], lw=1.4, shrinkA=0, shrinkB=0))
    cc_.text(0.5 * (xa_ + xb_), ts_c + 0.031, "155 m", ha="center", va="top", fontsize=10, color=COL["slack"],
             fontweight="bold")
    shift = float((x1 - xt)[cmax])
    for v, t0, col, xq, lab, dxl, dtl, ha in ((VP, 0.055, COL["P"], 515.0, "P", -8, 0.050, "right"),
                                              (VS, 0.115, COL["S"], 408.0, "S", 8, 0.045, "left")):
        t_pred, t_obs = t0 + (xq - xt[0]) / v, t0 + (xq - shift - xt[0]) / v
        cc_.annotate("", (xq, t_obs + 0.005), (xq, t_pred - 0.003),
                     arrowprops=dict(arrowstyle="<|-|>", color=col, lw=1.4, shrinkA=0, shrinkB=0))
        xl_, tl_ = (xq + dxl, 0.5 * (t_pred + t_obs) + 0.008 + dtl) if lab == "P" else (541.0, 0.488)
        cc_.text(xl_, tl_, f"{lab}: {1000 * shift / v:.0f} ms" + (" early" if lab == "P" else "\nearly"), ha="right",
                 va="center", fontsize=9.6, color=col, fontweight="bold", linespacing=1.05)

    d = fig.add_subplot(gs[1, 1])
    section(d, xt, r, "The same arrivals with the loop and the coil at their\npoints: continuous along the road",
            "d")
    d.plot(xt[r], tP[r], "o", ms=3.0, color=COL["P"], zorder=6)
    d.plot(xt[r], tS[r], "o", ms=3.0, color=COL["S"], zorder=6)
    xl_, xc_ = block_x(*SLACK[0][:2]), block_x(*SLACK[1][:2])
    for xb in (xl_, xc_):
        d.axvline(xb, color=COL["slack"], lw=1.2, ls=(0, (2, 2)), zorder=5)
    d.text(xl_, 0.026, "loop", ha="center", va="center", fontsize=10, color=COL["slack"], bbox=wb, zorder=7)
    d.text(xc_ + 8, 0.052, "coil: its 19 channels are at this\npoint; the map marks them as\nslack, to be left out",
           ha="left", va="center", fontsize=10, color=COL["slack"], bbox=wb, linespacing=1.1, zorder=7)
    out = os.path.join(HERE, "fig2_spatial_jump.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out)
    print(f"  map 2 error {e2.min():.1f} .. {e2.max():.1f} m; map 1 error beyond the coil {e1:.1f} m = "
          f"{1000 * e1 / VP:.0f} ms (P, {VP / 1000:g} km/s), {1000 * e1 / VS:.0f} ms (S, {VS / 1000:g} km/s)")


if __name__ == "__main__":
    fig1()
    fig2()
