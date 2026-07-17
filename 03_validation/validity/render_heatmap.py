#!/usr/bin/env python3
"""Render validity gray-white error heat map over the template, SyN vs affine."""
import json
import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

D = "/path/to/cast-project/07_Results_and_Analysis/validity_heatmap_pilot"

tpl = nib.load(f"{D}/age6_female_template.nii.gz").get_fdata()
syn = nib.load(f"{D}/age6_female_syn_meanabs_heatmap.nii.gz").get_fdata()
aff = nib.load(f"{D}/age6_female_affine_meanabs_heatmap.nii.gz").get_fdata()
syn_sum = json.load(open(f"{D}/age6_female_syn_summary.json"))
aff_sum = json.load(open(f"{D}/age6_female_affine_summary.json"))

# Choose slices at the centroid of the SyN boundary (where the error lives).
xs, ys, zs = np.where(syn > 0)
cx, cy, cz = int(np.median(xs)), int(np.median(ys)), int(np.median(zs))

VMAX = 4.0  # mm, shared color scale
norm = Normalize(vmin=0, vmax=VMAX)
cmap = plt.cm.hot

def panel(ax, bg2d, ov2d, title):
    ax.imshow(bg2d.T, cmap="gray", origin="lower",
              vmin=np.percentile(tpl[tpl > 0], 1), vmax=np.percentile(tpl[tpl > 0], 99))
    m = np.ma.masked_where(ov2d <= 0, ov2d)
    im = ax.imshow(m.T, cmap=cmap, norm=norm, origin="lower", alpha=0.95)
    ax.set_title(title, fontsize=9)
    ax.axis("off")
    return im

fig, axes = plt.subplots(2, 3, figsize=(11, 7.6))
planes = [
    ("Axial",    lambda V: V[:, :, cz]),
    ("Coronal",  lambda V: V[:, cy, :]),
    ("Sagittal", lambda V: V[cx, :, :]),
]
for col, (pname, sl) in enumerate(planes):
    im = panel(axes[0, col], sl(tpl), sl(syn), f"SyN — {pname}")
    panel(axes[1, col], sl(tpl), sl(aff), f"Affine — {pname}")

cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
fig.colorbar(im, cax=cax, label="mean |gray-white error|  (mm)")

sup = (f"Gray-white interface validity heat map — age6_female template "
       f"(pilot, n=3)\n"
       f"SyN: mean {syn_sum['mean_abs_err_mm']:.2f} mm | "
       f"{syn_sum['pct_within_2mm']:.0f}% surface <2mm  |  "
       f"Affine: mean {aff_sum['mean_abs_err_mm']:.2f} mm | "
       f"{aff_sum['pct_within_2mm']:.0f}% <2mm")
fig.suptitle(sup, fontsize=10)
fig.subplots_adjust(left=0.02, right=0.9, top=0.9, bottom=0.03, wspace=0.02, hspace=0.08)
out = f"{D}/age6_female_validity_heatmap_pilot.png"
fig.savefig(out, dpi=150)
print("wrote", out)

# Histogram of per-voxel mean error, SyN vs affine.
fig2, ax = plt.subplots(figsize=(6, 4))
ax.hist(syn[syn > 0], bins=60, range=(0, 5), alpha=0.6, label="SyN", color="C0")
ax.hist(aff[aff > 0], bins=60, range=(0, 5), alpha=0.6, label="Affine", color="C3")
ax.axvline(2.0, ls="--", c="k", lw=1, label="2 mm")
ax.set_xlabel("mean |gray-white error| per boundary voxel (mm)")
ax.set_ylabel("# boundary voxels")
ax.set_title("Validity error distribution (age6_female, n=3)")
ax.legend()
fig2.tight_layout()
out2 = f"{D}/age6_female_validity_hist_pilot.png"
fig2.savefig(out2, dpi=150)
print("wrote", out2)
