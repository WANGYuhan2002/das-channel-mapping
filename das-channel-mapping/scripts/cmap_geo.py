#!/usr/bin/env python3
"""Geometry helpers shared by the das-channel-mapping scripts.

Everything works in a local metric frame: x east, y north, in metres, around a reference point (lat0, lon0).
The default scale is the WGS84 length of one degree of longitude / latitude at lat0, which is accurate to
better than 0.1 % over a few tens of km. Pass kx / ky to reproduce an older pipeline that used other constants
(a common shortcut, 111320 m per degree for latitude too, makes north-south distances ~0.3 % too long at 38 N).
"""
import math

import numpy as np


def metres_per_degree(lat0):
    """(metres per degree of longitude, metres per degree of latitude) on the WGS84 ellipsoid at latitude lat0."""
    p = math.radians(lat0)
    my = 111132.954 - 559.822 * math.cos(2 * p) + 1.175 * math.cos(4 * p)
    mx = 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p) + 0.118 * math.cos(5 * p)
    return mx, my


class LocalXY:
    """local equirectangular frame around (lat0, lon0)."""

    def __init__(self, lat0, lon0, kx=None, ky=None):
        mx, my = metres_per_degree(lat0)
        self.lat0, self.lon0 = float(lat0), float(lon0)
        self.kx = float(kx) if kx else mx
        self.ky = float(ky) if ky else my

    @classmethod
    def around(cls, lat, lon, **kw):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        ok = np.isfinite(lat) & np.isfinite(lon)
        return cls(float(np.mean(lat[ok])), float(np.mean(lon[ok])), **kw)

    def xy(self, lat, lon):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky

    def latlon(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return self.lat0 + y / self.ky, self.lon0 + x / self.kx

    def dist(self, lat1, lon1, lat2, lon2):
        x1, y1 = self.xy(lat1, lon1)
        x2, y2 = self.xy(lat2, lon2)
        return np.hypot(x2 - x1, y2 - y1)


def arclength(x, y):
    """cumulative arc length of a polyline (starts at 0)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]


def at_s(x, y, s_query):
    """points at arc lengths s_query along a polyline (clipped to its ends)."""
    s = arclength(x, y)
    return np.interp(s_query, s, x), np.interp(s_query, s, y)


def at_fraction(x, y, frac):
    """points at fractions (0..1) of the arc length of a polyline, and the total length."""
    s = arclength(x, y)
    q = np.asarray(frac, float) * s[-1]
    return np.interp(q, s, x), np.interp(q, s, y), float(s[-1])


def densify(p, step=1.0):
    """polyline p (n, 2) with extra vertices so that no step is longer than `step` m."""
    p = np.asarray(p, float)
    out = [p[:1]]
    for a, b in zip(p[:-1], p[1:]):
        n = max(int(np.ceil(np.hypot(*(b - a)) / step)), 1)
        out.append(a + np.linspace(0, 1, n + 1)[1:, None] * (b - a))
    return np.vstack(out)


def hausdorff(p, q, step=1.0):
    """symmetric Hausdorff distance between two polylines (n, 2) in metres."""
    from scipy.spatial import cKDTree
    p, q = densify(p, step), densify(q, step)
    return float(max(cKDTree(q).query(p)[0].max(), cKDTree(p).query(q)[0].max()))


def point_to_polyline(px, py, x, y):
    """distance from points (px, py) to a polyline (x, y), and the arc length of the nearest point."""
    px, py = np.atleast_1d(np.asarray(px, float)), np.atleast_1d(np.asarray(py, float))
    x, y = np.asarray(x, float), np.asarray(y, float)
    s = arclength(x, y)
    dx, dy = np.diff(x), np.diff(y)
    L2 = np.maximum(dx ** 2 + dy ** 2, 1e-12)
    d_out, s_out = np.empty(len(px)), np.empty(len(px))
    for i, (u, v) in enumerate(zip(px, py)):
        t = np.clip(((u - x[:-1]) * dx + (v - y[:-1]) * dy) / L2, 0, 1)
        d = np.hypot(x[:-1] + t * dx - u, y[:-1] + t * dy - v)
        k = int(np.argmin(d))
        d_out[i], s_out[i] = d[k], s[k] + t[k] * math.sqrt(L2[k])
    return d_out, s_out


def segment_crossing(p1, p2, x, y, label):
    """first intersection of the segment p1 -> p2 with the polyline (x, y); returns the polyline label (e.g. the
    channel's along-fibre label) linearly interpolated at the crossing, or NaN."""
    best = (np.inf, np.nan)
    d = np.asarray(p2, float) - np.asarray(p1, float)
    for i in range(len(x) - 1):
        e = np.array([x[i + 1] - x[i], y[i + 1] - y[i]])
        den = d[0] * e[1] - d[1] * e[0]
        if den == 0:
            continue
        w = np.array([x[i] - p1[0], y[i] - p1[1]])
        t = (w[0] * e[1] - w[1] * e[0]) / den
        u = (w[0] * d[1] - w[1] * d[0]) / den
        if 0 <= t <= 1 and 0 <= u <= 1 and t < best[0]:
            best = (t, label[i] + u * (label[i + 1] - label[i]))
    return best[1]


def strike(x, y, valid, half=6, min_chord=20.0):
    """local azimuth (degrees clockwise from north, 0-360) of the chord from channel i - half to i + half; NaN
    where the window leaves the valid run or the chord is shorter than min_chord m."""
    x, y, valid = np.asarray(x, float), np.asarray(y, float), np.asarray(valid, bool)
    out = np.full(len(x), np.nan)
    for i in range(half, len(x) - half):
        a, b = i - half, i + half
        if not valid[a:b + 1].all():
            continue
        dx, dy = x[b] - x[a], y[b] - y[a]
        if math.hypot(dx, dy) > min_chord:
            out[i] = math.degrees(math.atan2(dx, dy)) % 360
    return out


def read_polyline(spec):
    """a polyline given as [[lat, lon], ...], a CSV with lat / lon columns (optionally filtered by key=value
    pairs after a '?', e.g. 'paths.csv?seg=3'), or a GeoJSON LineString file. Returns (lat, lon) arrays."""
    import json
    import pandas as pd
    if isinstance(spec, (list, tuple)):
        a = np.asarray(spec, float)
        return a[:, 0], a[:, 1]
    path, _, query = str(spec).partition("?")
    if path.endswith((".geojson", ".json")):
        g = json.load(open(path))
        if g.get("type") == "FeatureCollection":
            g = g["features"][0]
        g = g.get("geometry", g)
        a = np.asarray(g["coordinates"], float)
        return a[:, 1], a[:, 0]
    t = pd.read_csv(path)
    for kv in filter(None, query.split("&")):
        k, v = kv.split("=")
        t = t[t[k].astype(str) == v]
    return t.lat.to_numpy(float), t.lon.to_numpy(float)
