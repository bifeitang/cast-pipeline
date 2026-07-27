#!/usr/bin/env python3
"""Data-descriptor Figure 3 -- template brain + cohort GM/WM/CSF probability montage.

Like Figure 2, the published cast_tissue_montage.png was uploaded to Overleaf by hand and
had no generator in this repository. This script is that generator.

Inputs are the slice archives written by FIG3's align_tpms.sbatch, which warps the RELEASED
cohort tissue-probability maps into the same rigid display frame as the montage brains
(reference = age-11 male template) and then calls
03_validation/montage/extract_slices.py:

    <slices>/slices_age{AGE}_{sex}.npz     keys: brain_ax_55, gm_ax_55, wm_ax_55, csf_ax_55

Layout, measured from the published figure (2681x1703):
  * 14 columns (ages 5-18) x 8 rows
  * rows are M brain, M GM, M WM, M CSF, then the same four for F
  * 162x198 px panels, 17 px column gaps from x=175, 4 px row gaps from y=70
  * brains in gray with percentile 1-99 windowing (_robust_norm); probability maps in
    magma on a FIXED 0-1 scale, because they are probabilities and must stay comparable
    across ages, sexes and tissues
  * white canvas, black panels, ages as column titles, "Age (years)" above them

Usage:  make_figure_DD3_tissue_montage.py <slices_dir> <out.png>
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AGES = list(range(5, 19))
LEVEL = 55
ROWS = [("male", "brain"), ("male", "gm"), ("male", "wm"), ("male", "csf"),
        ("female", "brain"), ("female", "gm"), ("female", "wm"), ("female", "csf")]
LABEL = {"brain": "brain", "gm": "GM prob", "wm": "WM prob", "csf": "CSF prob"}
FIG_W, FIG_H, DPI = 2681, 1703, 200
PW, PH, GX, GY, LEFT, TOP = 162, 198, 17, 4, 175, 70


def robust_norm(a):
    flat = a[np.isfinite(a)]
    nz = flat[flat != 0]
    ref = nz if nz.size > 1000 else flat.ravel()
    vmin, vmax = float(np.percentile(ref, 1)), float(np.percentile(ref, 99))
    if vmax <= vmin:
        vmin, vmax = float(ref.min()), float(ref.max())
    return np.clip((np.clip(a, vmin, vmax) - vmin) / (vmax - vmin + 1e-6), 0, 1)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    sdir, out = sys.argv[1], sys.argv[2]

    def load(age, sex, what):
        p = os.path.join(sdir, f"slices_age{age}_{sex}.npz")
        if not os.path.exists(p):
            raise SystemExit(f"missing slice archive: {p}")
        z = np.load(p)
        key = f"{what}_ax_{LEVEL}"
        if key not in z:
            raise SystemExit(f"{p}: no '{key}' (has {sorted(z.files)})")
        return np.rot90(np.asarray(z[key], dtype=np.float32))

    data = {(a, s, w): load(a, s, w) for a in AGES for s, w in
            {(s, w) for s, w in ROWS}}
    shapes = {v.shape for v in data.values()}
    if len(shapes) != 1:
        raise SystemExit(f"panels are not on a common grid: {shapes}")

    # common bounding box over every BRAIN panel, padded to this figure's panel aspect
    acc = None
    for a in AGES:
        for s in ("male", "female"):
            sl = data[(a, s, "brain")]
            pos = sl[sl > 0]
            m = sl > 0.25 * np.percentile(pos, 95) if pos.size else sl > 0
            acc = m if acc is None else (acc | m)
    ys, xs = np.where(acc)
    cy, cx = (ys.min() + ys.max()) / 2.0, (xs.min() + xs.max()) / 2.0
    bh = ys.max() - ys.min() + 1
    bw = bh * (PW / PH)
    y0, y1 = int(round(cy - bh / 2)), int(round(cy + bh / 2))
    x0, x1 = int(round(cx - bw / 2)), int(round(cx + bw / 2))
    print(f"common crop rows {y0}:{y1} cols {x0}:{x1} "
          f"(aspect {(y1 - y0) / (x1 - x0):.3f} vs panel {PH / PW:.3f})")

    def crop(sl):
        out_ = np.zeros((y1 - y0, x1 - x0), np.float32)
        sy0, sy1 = max(0, y0), min(sl.shape[0], y1)
        sx0, sx1 = max(0, x0), min(sl.shape[1], x1)
        out_[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = sl[sy0:sy1, sx0:sx1]
        return out_

    fig = plt.figure(figsize=(FIG_W / DPI, FIG_H / DPI), dpi=DPI, facecolor="white")
    for ri, (sex, what) in enumerate(ROWS):
        py0 = TOP + ri * (PH + GY)
        for ci, age in enumerate(AGES):
            px0 = LEFT + ci * (PW + GX)
            ax = fig.add_axes([px0 / FIG_W, 1 - (py0 + PH) / FIG_H, PW / FIG_W, PH / FIG_H])
            img = crop(data[(age, sex, what)])
            if what == "brain":
                ax.imshow(robust_norm(img), cmap="gray", vmin=0, vmax=1,
                          interpolation="bilinear", aspect="auto")
            else:
                ax.imshow(img, cmap="magma", vmin=0, vmax=1,
                          interpolation="bilinear", aspect="auto")
            ax.set_facecolor("black")
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            if ri == 0:
                ax.set_title(str(age), color="black", fontsize=12, pad=4)
        fig.text((LEFT - 10) / FIG_W, 1 - (py0 + PH / 2.0) / FIG_H,
                 f"{sex[0].upper()} {LABEL[what]}", color="black", fontsize=10,
                 va="center", ha="right")
    fig.text((LEFT + 7 * (PW + GX)) / FIG_W, 1 - 14 / FIG_H, "Age (years)",
             color="black", fontsize=12, va="center", ha="center")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
