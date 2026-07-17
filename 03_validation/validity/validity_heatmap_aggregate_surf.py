#!/usr/bin/env python3
"""validity_heatmap_aggregate_surf.py  --  Option B (gold-standard, sub-voxel)

Gray-white interface error heat map (Ress R2, plan section 4.1), measured against
each held-out subject's FreeSurfer ?h.white SURFACE (continuous) instead of a 1 mm
FAST WM mask (voxel-quantized).

For the fixed template, the gray-white boundary is the inner surface of the
template WM mask (FAST). For each template-boundary voxel center (physical mm),
compute the distance to the nearest vertex of the subject's white surface AFTER it
has been warped into template space (warp_surface_to_template.py). Sign from the
warped surface normal: + = boundary point lies OUTSIDE subject WM (subject WM is
smaller there), - = inside -- same convention as the FAST pipeline.

Distances are continuous (no 1 mm lattice floor). Nearest-vertex rather than
nearest-point-on-triangle; FreeSurfer white meshes are dense (~0.8 mm edges) so the
residual is well under a voxel.

FreeSurfer ?h.white models ONLY the cerebral cortical gray-white interface. The
template FAST WM boundary also contains cerebellum, brainstem and periventricular
WM, which sit 10-40 mm from any cortical surface and form a clearly separate mode
in the distance histogram. We therefore restrict the reported boundary to the
cortical interface: a boundary voxel is "cortical" if its MEDIAN distance across
the cohort is <= CORTICAL_CUT_MM (default 6 mm, at the bimodal valley). Headline
stats are over the cortical set; the full-boundary stats are also reported. The
result is insensitive to the cut (median moves <0.1 mm over a 5-15 mm sweep).

Usage:
  validity_heatmap_aggregate_surf.py <level> <template_wm_mask> <out_prefix> \
      <subj1.npz> [<subj2.npz> ...]
Env: CORTICAL_CUT_MM (default 6.0)
"""
import os
import sys
import json
import numpy as np
import nibabel as nib
from scipy import ndimage
from scipy.spatial import cKDTree

CORTICAL_CUT_MM = float(os.environ.get("CORTICAL_CUT_MM", "6.0"))

level = sys.argv[1]
tpl_wm_path = sys.argv[2]
out_prefix = sys.argv[3]
npz_paths = sys.argv[4:]
if not npz_paths:
    sys.exit("ERROR: need at least one subject surface .npz")

tpl_img = nib.load(tpl_wm_path)
spacing = tuple(float(z) for z in tpl_img.header.get_zooms()[:3])
tpl_wm = tpl_img.get_fdata() > 0.5

# Template gray-white boundary = inner surface voxels of the WM mask.
tpl_bd = tpl_wm & ~ndimage.binary_erosion(tpl_wm)
bd_vox = np.argwhere(tpl_bd)                      # (n_bd, 3) voxel indices
n_bd = len(bd_vox)
if n_bd == 0:
    sys.exit("ERROR: empty template WM boundary")
# Boundary voxel centers in physical RAS (mm).
bd_ras = (tpl_img.affine @ np.c_[bd_vox, np.ones(n_bd)].T).T[:, :3]

per_subj_err = []   # signed mm error at each template boundary voxel
selfcheck = []
for p in npz_paths:
    d = np.load(p)
    verts = d["verts"].astype(np.float64)
    normals = d["normals"].astype(np.float64)
    tree = cKDTree(verts)
    dist, idx = tree.query(bd_ras, k=1)          # nearest-vertex distance (mm)
    sgn = np.sign(np.einsum("ij,ij->i", bd_ras - verts[idx], normals[idx]))
    sgn[sgn == 0] = 1.0
    per_subj_err.append(dist * sgn)
    selfcheck.append((p.split("/")[-2] if "/" in p else p,
                      float(np.median(dist)), float(np.percentile(dist, 95))))

errs = np.asarray(per_subj_err)                  # (n_subj, n_bd)
abs_err = np.abs(errs)
mean_abs = abs_err.mean(axis=0)                   # per boundary voxel
sd_abs = abs_err.std(axis=0)

# Cortical restriction: keep boundary voxels whose MEDIAN distance across the
# cohort is within the cut (excludes cerebellum / brainstem / periventricular WM
# that ?h.white does not model). Cohort-median, not per-subject, so the reported
# voxel set is identical for every subject.
median_abs = np.median(abs_err, axis=0)
cortical = median_abs <= CORTICAL_CUT_MM
n_cort = int(cortical.sum())

# Heat-map volumes on the template grid (cortical voxels only; rest left 0).
bd_idx = (bd_vox[cortical, 0], bd_vox[cortical, 1], bd_vox[cortical, 2])
heat = np.zeros(tpl_wm.shape, np.float32); heat[bd_idx] = mean_abs[cortical]
nib.save(nib.Nifti1Image(heat, tpl_img.affine, tpl_img.header),
         f"{out_prefix}_meanabs_heatmap.nii.gz")
sdmap = np.zeros(tpl_wm.shape, np.float32); sdmap[bd_idx] = sd_abs[cortical]
nib.save(nib.Nifti1Image(sdmap, tpl_img.affine, tpl_img.header),
         f"{out_prefix}_sd_heatmap.nii.gz")
# Signed-bias map: per-voxel MEAN of the signed error (+ = template boundary outside
# subject WM, i.e. template WM larger there; - = template WM smaller). Diverging, centered 0.
mean_signed = errs.mean(axis=0)
sgnmap = np.zeros(tpl_wm.shape, np.float32); sgnmap[bd_idx] = mean_signed[cortical]
nib.save(nib.Nifti1Image(sgnmap, tpl_img.affine, tpl_img.header),
         f"{out_prefix}_signedbias_heatmap.nii.gz")


def stats(mask):
    flat = abs_err[:, mask].ravel()
    sgn = errs[:, mask].ravel()
    return {
        "n_boundary_voxels": int(mask.sum()),
        "mean_abs_err_mm": float(flat.mean()),
        "median_abs_err_mm": float(np.median(flat)),
        "p95_abs_err_mm": float(np.percentile(flat, 95)),
        "pct_within_1mm": float((flat <= 1.0).mean() * 100.0),
        "pct_within_2mm": float((flat <= 2.0).mean() * 100.0),
        "mean_signed_err_mm": float(sgn.mean()),
    }


all_mask = np.ones(n_bd, bool)
summary = {
    "level": level,
    "method": "freesurfer_white_surface_nearest_vertex",
    "n_subjects": len(npz_paths),
    "voxel_spacing_mm": spacing,
    "cortical_cut_mm": CORTICAL_CUT_MM,
    "n_boundary_voxels_total": n_bd,
    "n_boundary_voxels_cortical": n_cort,
    "pct_boundary_cortical": float(100.0 * n_cort / n_bd),
    # Headline = cortical interface (where ?h.white is defined).
    "cortical": stats(cortical),
    # Full FAST WM boundary incl. cerebellum/brainstem (for transparency).
    "full_boundary": stats(all_mask),
    "per_subject_median_dist_mm": {s: m for s, m, _ in selfcheck},
    "per_subject_p95_dist_mm": {s: q for s, _, q in selfcheck},
    "subjects": [s for s, _, _ in selfcheck],
}
# Flat aliases (headline = cortical) so existing renderers keep working.
summary.update({k: summary["cortical"][k] for k in summary["cortical"]})
with open(f"{out_prefix}_summary.json", "w") as fh:
    json.dump(summary, fh, indent=2)
print(json.dumps(summary, indent=2))
