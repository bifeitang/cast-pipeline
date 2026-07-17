#!/usr/bin/env python3
"""Render the Option B (FreeSurfer surface, sub-voxel) gray-white validity heat
map over the template, SyN vs affine, plus the distance-distribution figure that
(a) justifies the cortical restriction (bimodal) and (b) shows the sub-voxel win
over the FAST pilot."""
import json
import glob
import numpy as np
import nibabel as nib
from scipy import ndimage
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

D = "/path/to/cast-project/07_Results_and_Analysis/validity_heatmap_pilot"
CUT = 6.0

tpl = nib.load(f"{D}/age6_female_template.nii.gz").get_fdata()
syn = nib.load(f"{D}/age6_female_syn_surf_meanabs_heatmap.nii.gz").get_fdata()
aff = nib.load(f"{D}/age6_female_affine_surf_meanabs_heatmap.nii.gz").get_fdata()
syn_sum = json.load(open(f"{D}/age6_female_syn_surf_summary.json"))["cortical"]
aff_sum = json.load(open(f"{D}/age6_female_affine_surf_summary.json"))["cortical"]
pct_cort = json.load(open(f"{D}/age6_female_syn_surf_summary.json"))["pct_boundary_cortical"]

# ---- Figure 1: cortical surface heat map, SyN vs affine, 3 planes ----------
xs, ys, zs = np.where(syn > 0)
cx, cy, cz = int(np.median(xs)), int(np.median(ys)), int(np.median(zs))
VMAX = 4.0
norm = Normalize(vmin=0, vmax=VMAX)

def panel(ax, bg2d, ov2d, title):
    ax.imshow(bg2d.T, cmap="gray", origin="lower",
              vmin=np.percentile(tpl[tpl > 0], 1), vmax=np.percentile(tpl[tpl > 0], 99))
    m = np.ma.masked_where(ov2d <= 0, ov2d)
    im = ax.imshow(m.T, cmap="hot", norm=norm, origin="lower", alpha=0.95)
    ax.set_title(title, fontsize=9); ax.axis("off")
    return im

fig, axes = plt.subplots(2, 3, figsize=(11, 7.6))
planes = [("Axial", lambda V: V[:, :, cz]),
          ("Coronal", lambda V: V[:, cy, :]),
          ("Sagittal", lambda V: V[cx, :, :])]
for col, (pname, sl) in enumerate(planes):
    im = panel(axes[0, col], sl(tpl), sl(syn), f"SyN — {pname}")
    panel(axes[1, col], sl(tpl), sl(aff), f"Affine — {pname}")
cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
fig.colorbar(im, cax=cax, label="mean |gray-white error|  (mm)")
sup = (f"Gray-white interface validity — age6_female template "
       f"(Option B: FreeSurfer ?h.white surface, sub-voxel, n=3)\n"
       f"Cortical interface ({pct_cort:.0f}% of boundary).  "
       f"SyN: mean {syn_sum['mean_abs_err_mm']:.2f} mm, median {syn_sum['median_abs_err_mm']:.2f} mm, "
       f"{syn_sum['pct_within_2mm']:.0f}% <2mm  |  "
       f"Affine: mean {aff_sum['mean_abs_err_mm']:.2f} mm, {aff_sum['pct_within_2mm']:.0f}% <2mm")
fig.suptitle(sup, fontsize=9.5)
fig.subplots_adjust(left=0.02, right=0.9, top=0.9, bottom=0.03, wspace=0.02, hspace=0.08)
fig.savefig(f"{D}/age6_female_validity_heatmap_surf.png", dpi=150)
print("wrote heatmap_surf.png")

# ---- recompute full per-voxel SyN distances locally (for the histogram) -----
tw = nib.load(f"{D}/template_wm.nii.gz")
wm = tw.get_fdata() > 0.5
bd = wm & ~ndimage.binary_erosion(wm)
vox = np.argwhere(bd)
ras = (tw.affine @ np.c_[vox, np.ones(len(vox))].T).T[:, :3]
dists = []
for p in sorted(glob.glob(f"{D}/surf_npz/*_syn.npz")):
    v = np.load(p)["verts"].astype(float)
    d, _ = cKDTree(v).query(ras, k=1)
    dists.append(d)
dists = np.asarray(dists)                  # (n_subj, n_bd)
full_mean = dists.mean(0)                   # per-voxel mean across subjects
cort_mask = np.median(dists, 0) <= CUT
cort_mean = full_mean[cort_mask]

# FAST (Option A) per-voxel SyN mean for the quantization comparison.
fast_syn = nib.load(f"{D}/age6_female_syn_meanabs_heatmap.nii.gz").get_fdata()
fast_vals = fast_syn[fast_syn > 0]

# ---- Figure 2: (a) bimodal justification  (b) sub-voxel win ----------------
fig2, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.2))

axA.hist(full_mean, bins=120, range=(0, 30), color="C7", alpha=0.85)
axA.axvspan(0, CUT, color="C0", alpha=0.12)
axA.axvline(CUT, ls="--", c="C0", lw=1.4, label=f"cortical cut = {CUT:.0f} mm")
axA.set_yscale("log")
axA.set_xlabel("per-voxel mean distance to subject surface (mm)")
axA.set_ylabel("# template boundary voxels (log)")
axA.set_title(f"Boundary is bimodal: cortical mode vs\ncerebellum/brainstem/periventricular tail "
              f"({100*cort_mask.mean():.0f}% cortical)")
axA.legend(fontsize=8)

axB.hist(fast_vals, bins=60, range=(0, 5), alpha=0.55, color="C3",
         label=f"Option A — FAST mask (quantized)\nmedian {np.median(fast_vals):.2f} mm")
axB.hist(cort_mean, bins=60, range=(0, 5), alpha=0.55, color="C0",
         label=f"Option B — ?h.white surface (sub-voxel)\nmedian {np.median(cort_mean):.2f} mm")
axB.axvline(2.0, ls="--", c="k", lw=1)
for x in (1.0, np.sqrt(2), np.sqrt(3)):     # FAST lattice spikes
    axB.axvline(x, ls=":", c="C3", lw=0.6, alpha=0.6)
axB.set_xlabel("mean |gray-white error| per boundary voxel (mm)")
axB.set_ylabel("# boundary voxels")
axB.set_title("Sub-voxel win (SyN, cortical):\nsurface removes the 1 mm lattice floor")
axB.legend(fontsize=8)
fig2.suptitle("Option B validity — distance distribution (age6_female, n=3)", fontsize=10)
fig2.tight_layout(rect=[0, 0, 1, 0.95])
fig2.savefig(f"{D}/age6_female_validity_hist_surf.png", dpi=150)
print("wrote hist_surf.png")
