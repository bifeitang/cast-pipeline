#!/usr/bin/env python3
"""Data-descriptor Figure 2 -- the 28-template axial montage.

The originally published montage.png was uploaded to Overleaf by hand and had no
generator in this repository; nothing here reproduced it. This script is that generator.

Inputs are the rigidly-aligned montage slice archives produced by
03_validation/montage/{run_align_montage.sbatch, extract_slices.py}:

    <aligned>/age{AGE}_{sex}/slices_age{AGE}_{sex}.npz

All 28 templates are resampled onto ONE common reference grid (the age-11 male template,
224x320x213 @ 0.8 mm) by a rigid 6-dof transform, so a fixed voxel index is the same
physical location in every panel and no scaling is applied -- brain growth across age is
therefore real and visible.

Style (reverse-engineered from the published figure and held to deliberately):
  * 14 columns (ages 5-18) x 2 rows (Male top, Female bottom)
  * one COMMON bounding box for all 28 panels, sized to the union of all brains and
    padded to the published 177:218 panel aspect. Because the box is shared and the
    grid is common, a bigger brain occupies more of its panel -- true relative size.
  * axial level brain_ax_55, which of the five archived levels best matches the
    published panels' brain aspect ratio across the 27 panels the age-11-female
    rebuild did not touch
  * per-panel percentile 1-99 windowing over nonzero voxels, i.e. `_robust_norm`
    from 03_validation/montage/make_template_montage.py. Per-panel windowing is
    required: the age-11-female template was rebuilt in 2026-07 and does not share
    the absolute intensity scale of its 27 siblings, so any shared absolute window
    would render it incorrectly.
  * white figure background, black panel background, ages as column titles, rotated
    Male/Female row labels, no suptitle and no axis labels (the LaTeX caption carries
    that information -- duplicating it in the image is what made an earlier
    regeneration attempt unusable).

Usage:
    make_figure_DD2_montage.py <aligned_dir> <out.png> [reference_montage.png]

If a reference montage is supplied its panel geometry is measured and reproduced exactly
(useful for a drop-in replacement); otherwise a 2618x552 layout is synthesised.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AGES = list(range(5, 19))
SEXES = ["male", "female"]
LEVEL = "brain_ax_55"
FIG_W, FIG_H, DPI = 2618, 552, 200


def _runs(mask, minlen):
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= minlen:
                out.append((start, i))
            start = None
    if start is not None and len(mask) - start >= minlen:
        out.append((start, len(mask)))
    return out


def panel_geometry(reference):
    """Measure (columns, rows, W, H) from a reference montage, or synthesise a layout."""
    if reference and os.path.exists(reference):
        from PIL import Image
        ref = np.asarray(Image.open(reference).convert("L"), dtype=np.float32) / 255.0
        h, w = ref.shape
        dark = ref < 0.35
        cols, rows = _runs(dark.any(axis=0), 60), _runs(dark.any(axis=1), 60)
        if len(cols) == len(AGES) and len(rows) == len(SEXES):
            return cols, rows, w, h
        print(f"[warn] {reference}: found {len(cols)} cols / {len(rows)} rows; synthesising")
    # measured off the published montage.png: 14x177px panels + 5px column gaps starting
    # at x=53, two 218px rows separated by 44px starting at y=51, in a 2618x552 canvas.
    # `top` must leave room for the age titles, which are drawn ABOVE the axes.
    pw, ph, gx, gy, left, top = 177, 218, 5, 44, 53, 51
    cols = [(left + i * (pw + gx), left + i * (pw + gx) + pw) for i in range(len(AGES))]
    rows = [(top + j * (ph + gy), top + j * (ph + gy) + ph) for j in range(len(SEXES))]
    return cols, rows, FIG_W, FIG_H


def robust_norm(a):
    """percentile 1-99 over nonzero voxels; identical to make_template_montage.py"""
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
    aligned, out = sys.argv[1], sys.argv[2]
    reference = sys.argv[3] if len(sys.argv) > 3 else None

    def load(age, sex):
        p = os.path.join(aligned, f"age{age}_{sex}", f"slices_age{age}_{sex}.npz")
        if not os.path.exists(p):
            raise SystemExit(f"missing slice archive: {p}")
        z = np.load(p)
        if LEVEL not in z:
            raise SystemExit(f"{p}: no '{LEVEL}' (has {sorted(z.files)})")
        return np.rot90(np.asarray(z[LEVEL], dtype=np.float32))

    slices = {(a, s): load(a, s) for a in AGES for s in SEXES}
    shapes = {v.shape for v in slices.values()}
    if len(shapes) != 1:
        raise SystemExit(f"panels are not on a common grid: {shapes}")

    cols, rows, W, H = panel_geometry(reference)
    pan_w, pan_h = cols[0][1] - cols[0][0], rows[0][1] - rows[0][0]

    # common bounding box = union of all brains, padded to the panel aspect
    acc = None
    for sl in slices.values():
        pos = sl[sl > 0]
        m = sl > 0.25 * np.percentile(pos, 95) if pos.size else sl > 0
        acc = m if acc is None else (acc | m)
    ys, xs = np.where(acc)
    cy, cx = (ys.min() + ys.max()) / 2.0, (xs.min() + xs.max()) / 2.0
    bh = ys.max() - ys.min() + 1
    bw = bh * (pan_w / pan_h)
    y0, y1 = int(round(cy - bh / 2)), int(round(cy + bh / 2))
    x0, x1 = int(round(cx - bw / 2)), int(round(cx + bw / 2))
    print(f"panel {pan_w}x{pan_h}px; common crop rows {y0}:{y1} cols {x0}:{x1} "
          f"(aspect {(y1 - y0) / (x1 - x0):.3f} vs panel {pan_h / pan_w:.3f})")

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor="white")
    for ri, sex in enumerate(SEXES):
        py0, py1 = rows[ri]
        for ci, age in enumerate(AGES):
            px0, px1 = cols[ci]
            ax = fig.add_axes([px0 / W, 1 - py1 / H, (px1 - px0) / W, (py1 - py0) / H])
            sl = slices[(age, sex)]
            crop = np.zeros((y1 - y0, x1 - x0), np.float32)
            sy0, sy1 = max(0, y0), min(sl.shape[0], y1)
            sx0, sx1 = max(0, x0), min(sl.shape[1], x1)
            crop[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = sl[sy0:sy1, sx0:sx1]
            ax.imshow(robust_norm(crop), cmap="gray", vmin=0, vmax=1,
                      interpolation="bilinear", aspect="auto")
            ax.set_facecolor("black")
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            if ri == 0:
                ax.set_title(str(age), color="black", fontsize=15, pad=6)
        fig.text(cols[0][0] / W - 0.011, 1 - (py0 + py1) / 2.0 / H, sex.capitalize(),
                 color="black", fontsize=15, va="center", ha="center", rotation=90)
    fig.savefig(out, dpi=DPI, facecolor="white")
    print("wrote", out)


if __name__ == "__main__":
    main()
