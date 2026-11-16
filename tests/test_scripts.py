"""Tests of the das-channel-mapping scripts on synthetic data (no real data anywhere).

    python3 -m pytest -q tests/
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "das-channel-mapping", "scripts")
EXAMPLE = os.path.join(ROOT, "examples", "synthetic")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, EXAMPLE)

import build_channel_map as B  # noqa: E402
import hammer_anchor as H  # noqa: E402
import quake_coupling as Q  # noqa: E402
import waterline_waves as W  # noqa: E402
import vehicle_coil as V  # noqa: E402
import make_delivery as MD  # noqa: E402


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("syn"))
    run(os.path.join(EXAMPLE, "make_synthetic.py"), "--out", d)
    run(os.path.join(SCRIPTS, "road_path.py"), "--config", os.path.join(d, "config.json"), "--piece", "land",
        "--osm", os.path.join(d, "osm.json"), "--reference", os.path.join(d, "reference_route.csv"),
        "--out", os.path.join(d, "paths.csv"), "--report", os.path.join(d, "paths_report.json"))
    run(os.path.join(SCRIPTS, "build_channel_map.py"), os.path.join(d, "config.json"), "--out", os.path.join(d, "out"))
    return d


def test_end_to_end_against_truth(synthetic):
    import compare_truth
    out, M = compare_truth.compare(synthetic)
    assert out.loc["land", "err_median_m"] < 3.0
    assert out.loc["land", "err_max_m"] < 8.0
    assert out.loc["sea", "err_max_m"] < 10.0
    for sg in ("cabin", "land", "coil", "beach", "sea", "far_land"):
        assert out.loc[sg, "within_2sigma"] == 1.0, sg
    rep = json.load(open(os.path.join(synthetic, "paths_report.json")))
    assert rep["by_path"] == {"osm_road": 8}                    # the decoy parallel road is never taken
    summ = json.load(open(os.path.join(synthetic, "out", "channel_map_summary.json")))
    r = summ["pieces"]["far_land"]["fibre_over_path"]
    assert abs(r - 1.02) < 0.01                                 # the land fibre / road ratio is recovered
    T = pd.read_csv(os.path.join(synthetic, "out", "channel_map_all.csv"))
    blk = T[T.slack == "quake_coil"]
    assert len(blk) == 5 and blk.s_path_m.nunique() == 1         # the coil sits at one point
    dec = pd.read_csv(os.path.join(synthetic, "out", "channel_map_dec2.csv"))
    assert (dec.raw_col % 2 == 0).all() and (dec.j2 == dec.raw_col // 2).all()


def test_block_fractions():
    # one block, no point given: the rest of the segment is uniform in channel
    cols, fr = B.block_fractions(0.0, 20.0, [dict(k1=5.0, k2=10.0)], 100.0)
    assert np.allclose(fr, [0, 1 / 3, 1 / 3, 1])
    # one block at a given fraction
    cols, fr = B.block_fractions(0.0, 20.0, [dict(k1=5.0, k2=10.0, at_fraction=0.6)], 100.0)
    assert np.allclose(fr, [0, 0.6, 0.6, 1])
    # two blocks, the second at a given point in metres: the first one is placed by the uniform rest before it
    cols, fr = B.block_fractions(0.0, 30.0, [dict(k1=5.0, k2=8.0), dict(k1=20.0, k2=25.0, at_m=80.0)], 100.0)
    assert np.isclose(fr[3], 0.8) and np.isclose(fr[1], 0.8 * 5 / (5 + 12))
    with pytest.raises(ValueError):
        B.block_fractions(0.0, 30.0, [dict(k1=5.0, k2=8.0, at_fraction=0.9), dict(k1=20.0, k2=25.0, at_fraction=0.2)],
                          100.0)


def synthetic_blows(rng, pick=40.3, n_blows=8, n_ch=80, fs=400.0):
    t = -1.0 + np.arange(1000) / fs
    cols = np.arange(n_ch)
    W_ = []
    for k in range(n_blows):
        amp = np.exp(-0.5 * ((cols - pick) / 1.6) ** 2) * (1 + 0.3 * rng.standard_normal())
        x = rng.standard_normal((len(t), n_ch)) * 0.05
        t0 = 0.002 * rng.standard_normal()
        burst = np.exp(-np.clip(t - t0, 0, None) / 0.03) * (t >= t0) * np.sin(2 * np.pi * 60 * (t - t0))
        delay = np.abs(cols - pick) * 8.0 / 1500.0
        for j in range(n_ch):
            x[:, j] += 20 * amp[j] * np.interp(t - delay[j], t, burst, left=0)
        W_.append(x)
    return W_, fs, t, cols


def test_hammer_stack_finds_the_anchor():
    rng = np.random.default_rng(0)
    W_, fs, t, cols = synthetic_blows(rng)
    summ, pc, S = H.stack_shot(W_, fs, t, cols, 40.0)
    assert abs(summ["stack_peak_col"] - 40.3) < 0.5
    assert summ["foot_from"] < 40 < summ["foot_to"] and summ["simultaneous_cols"] == ""
    assert summ["n_used"] >= 6


def test_hammer_detect_stationary_sequence():
    rng = np.random.default_rng(1)
    fs, n_ch = 20.0, 60
    t = np.arange(0, 400, 1 / fs)
    E = 1 + 0.1 * rng.random((len(t), n_ch))
    for tb in np.arange(150, 210, 6.0):                        # blows on channel 31 every 6 s
        i = int(tb * fs)
        E[i, 29:34] += np.array([5, 30, 120, 30, 5])
    for k, tb in enumerate(np.arange(100, 140, 2.0)):          # footsteps drifting along the cable
        i = int(tb * fs)
        E[i, 5 + k] += 60
    bg = np.median(E, axis=0)
    res, Bl = H.detect_shot(E, t, 0, 180.0, bg)
    assert res["status"] == "ok" and abs(res["col"] - 31) < 0.5 and res["n_blows"] >= 8


def test_convention_test():
    rng = np.random.default_rng(2)
    c = np.linspace(40, 900, 30)
    d = -207.2 + 8.1676 * c + rng.normal(0, 3, len(c))          # the log used the header distance
    r = H.convention_test(c, d, dict(header=(-207.2, 8.1676), nominal=(-215.0, 8.0)), 8.1676)
    assert abs(r["header"]["median_m"]) < 3 and abs(r["header"]["trend_m_per_km"]) < 2
    assert abs(r["nominal"]["trend_m_per_km"]) > 15                 # wrong convention: error grows with distance


def test_quake_weak_runs():
    rng = np.random.default_rng(3)
    n = 300
    snr = 50 * np.exp(0.2 * rng.standard_normal(n))
    sig, noi = snr.copy(), np.ones(n)
    sig[120:131] *= 0.05
    snr[120:131] *= 0.05                                       # a coil: signal gone, noise normal
    noi[200:206] *= 8
    snr[200:206] /= 8                                          # a noisy stretch: not a coupling problem
    Wr, w, runs, ref = Q.weak_runs(snr, sig, noi)
    kinds = dict(zip(Wr.col_from, Wr.kind))
    assert kinds.get(120) == "weak coupling" and Wr.set_index("col_from").n_cols[120] == 11
    assert kinds.get(200) == "noisy"


def test_waterline_step_and_half_rise():
    c = np.arange(100, 200, dtype=float)
    y = np.where(c < 150, 20.0, 2.0) + np.where(c < 140, -3.0, 0.0)   # surf / plateau / land
    e, d = W.step(c, y, (140, 160), landward=1)
    assert e == 149.5 and d < -15
    hr = W.half_rise(c, y, land=(170, 190), peak=(140, 150), frac=0.5, landward=1)
    assert 149 <= hr <= 150
    e2, _ = W.step(c[::-1], y[::-1], (140, 160), landward=-1)          # same profile, land at lower channels
    assert e2 == 149.5 or e2 == 150.5


def test_vehicle_coil_vs_stretch():
    cols = np.arange(0, 60)
    a, b = 25, 34                                               # a 10-channel run
    s_per_col = 0.8
    t_coil = np.where(cols < a, cols * s_per_col, np.where(cols > b, (cols - (b - a + 1)) * s_per_col,
                                                           (a - 0.5) * s_per_col))
    t_stretch = cols * s_per_col
    assert abs(V.road_columns(t_coil, cols, a, b)) < 0.2
    assert abs(V.road_columns(t_stretch, cols, a, b) - (b - a + 1)) < 0.2


def test_vehicle_ridge_on_synthetic_correlation():
    lags = np.arange(-225, 226) / 5.0
    a, b = 30, 40
    cs = np.arange(a - 12, b + 16)
    road = np.where(cs < a, cs - cs[0], np.where(cs > b, cs - cs[0] - (b - a + 1), np.nan))   # coil: no road length
    CC = np.zeros((len(cs), len(lags)))
    for i, r in enumerate(road):
        if np.isfinite(r):
            CC[i] += np.exp(-0.5 * ((lags - 0.7 * r) / 0.3) ** 2)
    v = V.ridge_verdict(V.ridge_track(CC, cs, a, b, 1, lags), cs, a, b)
    assert abs(v["road_cols"]) < 0.5 and abs(v["s_per_col"] - 0.7) < 0.05


def test_delivery(synthetic, tmp_path):
    out = os.path.join(synthetic, "out")
    T = pd.read_csv(os.path.join(out, "channel_map_all.csv"))
    S = pd.read_csv(os.path.join(out, "channel_map_anchored_segments.csv"), dtype={"segment": str, "slack_cols": str,
                                                                                   "slack_at_m": str,
                                                                                   "slack_placed_by": str})
    D = pd.DataFrame(MD.dictionary(T, "map", MD.STD, {}))
    assert (D.unit != "?").sum() >= len(D) - 1                  # every standard column described (j2 is custom)
    I = MD.slack_inventory(T, S, 8.2)
    q = I[I.slack == "quake_coil"].iloc[0]
    assert q.placed_by == "vehicles" and q.spread_m < 1e-6
    C = MD.change_table(T, T)
    assert C.move_m.max() < 1e-6
    d = tmp_path / "pkg"
    d.mkdir()
    (d / "a.csv").write_text("x\n1\n")
    assert MD.manifest(str(d)) == 1 and "a.csv" in (d / "md5sums.txt").read_text()
    run(os.path.join(SCRIPTS, "make_delivery.py"), "gis", "--map", os.path.join(out, "channel_map_all.csv"),
        "--summary", os.path.join(out, "channel_map_summary.json"), "--out", str(tmp_path / "gis"))
    fc = json.load(open(tmp_path / "gis" / "channel_map_features.geojson"))
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert {"segment", "anchor", "slack"} <= kinds
