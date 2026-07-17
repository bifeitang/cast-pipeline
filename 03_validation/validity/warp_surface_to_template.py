#!/usr/bin/env python3
"""warp_surface_to_template.py  (runs INSIDE the apptainer container)

Option B (gold-standard, sub-voxel): take a held-out subject's FreeSurfer
gray-white surface (lh.white + rh.white) and bring it into the matched
template's space, so the template gray-white boundary error can be measured
against a CONTINUOUS surface instead of a 1 mm voxel mask.

Transform chain for surface VERTICES (points), composed in one
antsApplyTransformsToPoints call:

  FS surface-RAS --(Norig . inv(Torig), numpy)--> FS scanner-RAS
                 --([fs2mov_0GenericAffine.mat,1])--> csfNorm_rc moving space
                 --([reg_0GenericAffine.mat,1] [, reg_1InverseWarp])--> template

The fs->moving rigid is REQUIRED: header frames are only approximately shared
(one pilot subject was off by ~40 mm in z), so we register the FS anatomy to the
csfNorm_rc moving image explicitly rather than trusting the sform.

ANTs points use LPS; FreeSurfer/nibabel scanner coords are RAS -> negate x,y on
the way in and out.

Outputs an .npz with template-space vertices (RAS, mm) + faces + recomputed
outward vertex normals (for the inside/outside sign of the boundary error).

Usage:
  warp_surface_to_template.py <orig.mgz> <lh.white> <rh.white> \
      <fs2mov_affine.mat> <reg_affine.mat> <out.npz> [reg_invwarp.nii.gz]

If reg_invwarp is omitted -> AFFINE level (linear only). If given -> SyN level.
"""
import sys
import os
import csv
import subprocess
import numpy as np
import nibabel as nib
from nibabel.freesurfer.io import read_geometry

orig_p, lh_p, rh_p, fs2mov_p, regaff_p, out_npz = sys.argv[1:7]
reg_invwarp = sys.argv[7] if len(sys.argv) > 7 else None

# --- FS surface-RAS -> FS scanner-RAS ---------------------------------------
orig = nib.load(orig_p)
tkr2scan = orig.affine @ np.linalg.inv(orig.header.get_vox2ras_tkr())

vlh, flh = read_geometry(lh_p)
vrh, frh = read_geometry(rh_p)
verts = np.vstack([vlh, vrh]).astype(np.float64)
faces = np.vstack([flh, frh + len(vlh)]).astype(np.int64)
scan = (tkr2scan @ np.c_[verts, np.ones(len(verts))].T).T[:, :3]

# --- write LPS CSV for ANTs --------------------------------------------------
lps = scan.copy()
lps[:, 0] *= -1
lps[:, 1] *= -1
base = os.path.splitext(out_npz)[0]
in_csv, out_csv = base + "_in.csv", base + "_out.csv"
with open(in_csv, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["x", "y", "z", "t"])
    for p in lps:
        w.writerow([f"{p[0]:.6f}", f"{p[1]:.6f}", f"{p[2]:.6f}", 0])

# --- compose transforms: fs->moving->template (point convention) ------------
cmd = ["antsApplyTransformsToPoints", "-d", "3", "-i", in_csv, "-o", out_csv,
       "-t", f"[{fs2mov_p},1]", "-t", f"[{regaff_p},1]"]
if reg_invwarp:
    cmd += ["-t", reg_invwarp]
subprocess.run(cmd, check=True)

# --- read back, LPS -> RAS ---------------------------------------------------
warped = []
with open(out_csv) as fh:
    r = csv.DictReader(fh)
    for row in r:
        warped.append([float(row["x"]), float(row["y"]), float(row["z"])])
warped = np.asarray(warped)
warped[:, 0] *= -1
warped[:, 1] *= -1

# --- recompute outward vertex normals from the WARPED mesh -------------------
# (face connectivity is preserved under the warp; normals must be recomputed in
#  template space because the nonlinear warp does not preserve them.)
v = warped
tri = v[faces]                                   # (F,3,3)
fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
vn = np.zeros_like(v)
for k in range(3):
    np.add.at(vn, faces[:, k], fn)
nrm = np.linalg.norm(vn, axis=1, keepdims=True)
vn = vn / np.clip(nrm, 1e-8, None)

np.savez_compressed(out_npz, verts=v.astype(np.float32),
                    normals=vn.astype(np.float32), n_lh=len(vlh))
os.remove(in_csv); os.remove(out_csv)
print(f"[warp] {out_npz}  verts={len(v):,}  level={'syn' if reg_invwarp else 'affine'}")
