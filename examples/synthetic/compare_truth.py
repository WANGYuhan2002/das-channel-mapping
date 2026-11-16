#!/usr/bin/env python3
"""Error of the built synthetic map against the truth, per segment, and how often it stays inside pos_unc_m.

    python3 compare_truth.py data/        (after make_synthetic.py, road_path.py and build_channel_map.py)
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "das-channel-mapping", "scripts"))
from cmap_geo import LocalXY  # noqa: E402


def compare(folder, table="channel_map_all.csv"):
    T = pd.read_csv(os.path.join(folder, "truth.csv"))
    M = pd.read_csv(os.path.join(folder, "out", table))
    P = LocalXY.around(T.lat, T.lon)
    M["err_m"] = P.dist(T.lat.to_numpy(), T.lon.to_numpy(), M.lat.to_numpy(), M.lon.to_numpy())
    M["true_segment"] = T.segment
    g = M.groupby("segment", sort=False)
    out = pd.DataFrame(dict(n=g.size(), err_median_m=g.err_m.median(), err_max_m=g.err_m.max(),
                            unc_median_m=g.pos_unc_m.median(),
                            within_1sigma=g.apply(lambda q: float(np.mean(q.err_m <= q.pos_unc_m))),
                            within_2sigma=g.apply(lambda q: float(np.mean(q.err_m <= 2 * q.pos_unc_m)))))
    return out, M


if __name__ == "__main__":
    out, M = compare(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data"))
    print(out.round(2).to_string())
    print("segment labels agree with the truth:", bool((M.segment == M.true_segment).mean() > 0.97))
