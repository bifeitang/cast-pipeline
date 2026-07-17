#!/usr/bin/env python3
"""validity_heatmap_aggregate.py

Gray-white interface error heat map (Ress R2, plan section 4.1).

For a fixed template, define the gray-white boundary as the surface of the
template WM mask. For each held-out subject (already registered + FAST-
segmented in template space), compute the signed surface distance from each
template-boundary voxel to that subject's WM surface, in mm. Aggregate across
subjects per boundary voxel -> mean |error| and SD heat maps on the template,
plus whole-boundary summary stats.

Signed distance convention: + = template boundary lies OUTSIDE the subject WM
(subject WM is smaller there); - = inside.

Usage:
  validity_heatmap_aggregate.py <level> <template_wm_mask> <out_prefix> <subj_wm_1> [<subj_wm_2> ...]
"""
import sys
import json
import numpy as np
import nibabel as nib
from scipy import ndimage


def main():
    level = sys.argv[1]
    tpl_wm_path = sys.argv[2]
    out_prefix = sys.argv[3]
    subj_wm_paths = sys.argv[4:]
    if not subj_wm_paths:
        sys.exit("ERROR: need at least one subject WM mask")

    tpl_img = nib.load(tpl_wm_path)
    spacing = tuple(float(z) for z in tpl_img.header.get_zooms()[:3])
    tpl_wm = tpl_img.get_fdata() > 0.5

    # Template gray-white boundary = inner surface voxels of the WM mask.
    tpl_bd = tpl_wm & ~ndimage.binary_erosion(tpl_wm)
    bd_idx = np.where(tpl_bd)
    n_bd = int(tpl_bd.sum())
    if n_bd == 0:
        sys.exit("ERROR: empty template WM boundary")

    per_subj_err = []  # signed mm error at each template boundary voxel
    for p in subj_wm_paths:
        m = nib.load(p).get_fdata() > 0.5
        # Signed distance to the subject WM surface (mm), via EDT with spacing.
        dt_out = ndimage.distance_transform_edt(~m, sampling=spacing)
        dt_in = ndimage.distance_transform_edt(m, sampling=spacing)
        sdf = dt_out - dt_in  # >0 outside subject WM, <0 inside
        per_subj_err.append(sdf[bd_idx])

    errs = np.asarray(per_subj_err)        # (n_subj, n_boundary)
    abs_err = np.abs(errs)
    mean_abs = abs_err.mean(axis=0)        # per boundary voxel
    sd_abs = abs_err.std(axis=0)

    # Heat-map volumes on the template grid.
    heat = np.zeros(tpl_wm.shape, np.float32)
    heat[bd_idx] = mean_abs
    nib.save(nib.Nifti1Image(heat, tpl_img.affine, tpl_img.header),
             f"{out_prefix}_meanabs_heatmap.nii.gz")
    sdmap = np.zeros(tpl_wm.shape, np.float32)
    sdmap[bd_idx] = sd_abs
    nib.save(nib.Nifti1Image(sdmap, tpl_img.affine, tpl_img.header),
             f"{out_prefix}_sd_heatmap.nii.gz")

    flat = abs_err.ravel()
    summary = {
        "level": level,
        "n_subjects": len(subj_wm_paths),
        "n_boundary_voxels": n_bd,
        "voxel_spacing_mm": spacing,
        "mean_abs_err_mm": float(flat.mean()),
        "median_abs_err_mm": float(np.median(flat)),
        "p95_abs_err_mm": float(np.percentile(flat, 95)),
        "pct_within_1mm": float((flat <= 1.0).mean() * 100.0),
        "pct_within_2mm": float((flat <= 2.0).mean() * 100.0),
        "mean_signed_err_mm": float(errs.mean()),
        "subjects": [p.split("/")[-2] if "/" in p else p for p in subj_wm_paths],
    }
    with open(f"{out_prefix}_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
