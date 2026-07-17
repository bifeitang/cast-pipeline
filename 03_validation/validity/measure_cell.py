#!/usr/bin/env python3
"""measure_cell.py -- one (subject, template) cell of the mismatch trend.

Given a template WM mask and a subject's white-surface vertices warped into that
template's space (affine), compute the gray-white interface distance summary.

Primary statistic = FULL-boundary MEDIAN: the cortical mode is ~84% of boundary
voxels, so the median sits firmly in cortex -- unbiased by the cerebellum/
brainstem tail AND immune to mismatch-clipping (no cut needed). Cortical mean /
%<2mm (cut) reported as secondary.

Usage: measure_cell.py <template_wm> <cell.npz> <subj_age> <tpl_age> <tpl_sex> <subj_id> [cut_mm]
Prints one JSON line.
"""
import sys, json
import numpy as np, nibabel as nib
from scipy import ndimage
from scipy.spatial import cKDTree

tpl_wm, npz, subj_age, tpl_age, tpl_sex, subj_id = sys.argv[1:7]
cut = float(sys.argv[7]) if len(sys.argv) > 7 else 6.0

t = nib.load(tpl_wm); wm = t.get_fdata() > 0.5
bd = wm & ~ndimage.binary_erosion(wm)
vox = np.argwhere(bd)
ras = (t.affine @ np.c_[vox, np.ones(len(vox))].T).T[:, :3]
v = np.load(npz)["verts"].astype(float)
d, _ = cKDTree(v).query(ras, k=1)

cort = d <= cut
out = {
    "subject_id": subj_id,
    "subject_age": float(subj_age),
    "template_age": int(tpl_age),
    "template_sex": tpl_sex,
    "d_age": int(tpl_age) - round(float(subj_age)),
    "n_boundary": int(len(d)),
    "full_median_mm": float(np.median(d)),     # PRIMARY trend statistic
    "full_mean_mm": float(d.mean()),
    "cort_mean_mm": float(d[cort].mean()),
    "cort_median_mm": float(np.median(d[cort])),
    "cort_pct_within_2mm": float(100 * (d[cort] <= 2).mean()),
    "cort_pct_within_1mm": float(100 * (d[cort] <= 1).mean()),
    "cut_mm": cut,
}
print(json.dumps(out))
