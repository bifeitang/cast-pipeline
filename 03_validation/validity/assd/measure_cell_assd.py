#!/usr/bin/env python3
"""measure_cell_assd.py -- symmetric + signed extension of measure_cell.py.

Non-invasive SUPERSET of ../measure_cell.py: it emits every original field byte-for-byte
(so it can be cross-checked against the validated directional metric) AND adds the symmetric
Average Symmetric Surface Distance (ASSD) plus a signed inside/outside summary.

Geometry (subject S already SyN-warped into template T's space):
  B_T = template gray-white boundary  = inner-surface voxels of the template WM mask
        (bd = WM & ~binary_erosion(WM)), in physical RAS mm.            [b_1..b_m]
  V_S = subject FreeSurfer ?h.white vertices (CORTEX ONLY) + outward normals.  [v_1..v_n]

Metrics:
  (M1) forward, directional, unsigned  d_i = min_j ||b_i - v_j||      (B_T -> V_S)
       -- the ORIGINAL metric; cortical subset C = {i: d_i <= cut}.
  (M4) reverse                          e_j = min_{i in C} ||v_j - b_i||  (V_S -> cortical B_T)
       ASSD = 1/2 ( mean_{i in C} d_i + mean_j e_j ).   Removes the one-sided penalty on the
       template with the larger cortical surface.  Subject ?h.white is cortex-only, so the
       reverse query uses the cortical boundary subset C (cerebellum/brainstem voxels, which
       form the far mode removed by the cut, never participate).
  (M5) signed forward  s_i = d_i * sign((b_i - v_{k(i)}) . nu_{k(i)})
       (+ => boundary lies OUTSIDE subject WM, i.e. subject WM smaller there; same convention
        as validity_heatmap_aggregate_surf.py).

Usage: measure_cell_assd.py <template_wm> <cell.npz> <subj_age> <tpl_age> <tpl_sex> <subj_id> [cut_mm] [reference]
Prints one JSON line.  Optional <reference> (e.g. CAST_0.8 / NKI_0.8) is echoed into the record.
"""
import sys, json
import numpy as np, nibabel as nib
from scipy import ndimage
from scipy.spatial import cKDTree

tpl_wm, npz, subj_age, tpl_age, tpl_sex, subj_id = sys.argv[1:7]
cut = float(sys.argv[7]) if len(sys.argv) > 7 else 6.0
reference = sys.argv[8] if len(sys.argv) > 8 else None

t = nib.load(tpl_wm); wm = t.get_fdata() > 0.5
bd = wm & ~ndimage.binary_erosion(wm)
vox = np.argwhere(bd)
ras = (t.affine @ np.c_[vox, np.ones(len(vox))].T).T[:, :3]

arr = np.load(npz)
v = arr["verts"].astype(float)

# --- (M1) forward: template boundary -> nearest subject vertex (ORIGINAL, unchanged) ---
d, idx = cKDTree(v).query(ras, k=1)
cort = d <= cut

# --- (M4) reverse: each subject vertex -> nearest CORTICAL template boundary voxel ---
ras_cort = ras[cort]
if len(ras_cort):
    e, _ = cKDTree(ras_cort).query(v, k=1)
else:
    e = np.full(len(v), np.nan)

fwd_mean = float(d[cort].mean())
rev_mean = float(e.mean())
assd_mm = 0.5 * (fwd_mean + rev_mean)

out = {
    "subject_id": subj_id,
    "subject_age": float(subj_age),
    "template_age": int(tpl_age),
    "template_sex": tpl_sex,
    "d_age": int(tpl_age) - round(float(subj_age)),
    "n_boundary": int(len(d)),
    # ---- ORIGINAL directional fields (identical formulas; the self-check anchor) ----
    "full_median_mm": float(np.median(d)),
    "full_mean_mm": float(d.mean()),
    "cort_mean_mm": float(d[cort].mean()),
    "cort_median_mm": float(np.median(d[cort])),
    "cort_pct_within_2mm": float(100 * (d[cort] <= 2).mean()),
    "cort_pct_within_1mm": float(100 * (d[cort] <= 1).mean()),
    "cut_mm": cut,
    # ---- NEW: directional components + symmetric ASSD (M1/M4) ----
    "fwd_mean_cort_mm": fwd_mean,                       # == cort_mean_mm by construction
    "fwd_median_cort_mm": float(np.median(d[cort])),
    "rev_mean_mm": rev_mean,
    "rev_median_mm": float(np.median(e)),
    "n_vertices": int(len(v)),
    "n_cort_boundary": int(cort.sum()),
    "assd_mm": assd_mm,                                 # PRIMARY symmetric statistic
    "assd_median_mm": 0.5 * (float(np.median(d[cort])) + float(np.median(e))),
    "rev_pct_within_1mm": float(100 * (e <= 1).mean()),
    "rev_pct_within_2mm": float(100 * (e <= 2).mean()),
}

# ---- NEW: signed inside/outside summary (M5) ----
if "normals" in arr.files:
    nrm = arr["normals"].astype(float)
    sgn = np.sign(np.einsum("ij,ij->i", ras - v[idx], nrm[idx]))
    sgn[sgn == 0] = 1.0
    signed = d * sgn
    out["mean_signed_cort_mm"] = float(signed[cort].mean())
    out["median_signed_cort_mm"] = float(np.median(signed[cort]))
    out["pct_boundary_outside_subjWM"] = float(100 * (signed[cort] > 0).mean())

if reference is not None:
    out["reference"] = reference

print(json.dumps(out))
