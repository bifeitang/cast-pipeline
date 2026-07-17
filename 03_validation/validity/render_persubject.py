#!/usr/bin/env python3
"""Per-subject gray-white interface distance heat maps (Ress R2, §4.1) + the
mean and variability (SD) aggregate. AFFINE level = representativeness (each
child's true gyral shape is preserved; this is what Ress asked for). SyN is a
separate registration-floor question, not this figure.

Pilot n=3: every subject is shown individually so individual variance is
discernible; at full scale the Mean + SD maps are the deliverable."""
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
LEVEL = "affine"   # representativeness

tpl = nib.load(f"{D}/age6_female_template.nii.gz").get_fdata()
tw = nib.load(f"{D}/template_wm.nii.gz")
wm = tw.get_fdata() > 0.5
bd = wm & ~ndimage.binary_erosion(wm)
vox = np.argwhere(bd)
ras = (tw.affine @ np.c_[vox, np.ones(len(vox))].T).T[:, :3]
shape = wm.shape

paths = sorted(glob.glob(f"{D}/surf_npz/*_{LEVEL}.npz"))
eids = [p.split("/")[-1].replace(f"_{LEVEL}.npz", "") for p in paths]
dist = []
for p in paths:
    v = np.load(p)["verts"].astype(float)
    d, _ = cKDTree(v).query(ras, k=1)
    dist.append(d)
dist = np.asarray(dist)                       # (n_subj, n_bd), unsigned mm
cort = np.median(dist, 0) <= CUT              # cohort cortical mask

def vol(values):
    out = np.zeros(shape, np.float32)
    out[vox[cort, 0], vox[cort, 1], vox[cort, 2]] = values[cort]
    return out

per_subj_vol = [vol(dist[i]) for i in range(len(eids))]
mean_vol = vol(dist.mean(0))
sd_vol = vol(dist.std(0))

# per-subject summary numbers (cortical)
print(f"=== AFFINE per-subject cortical distance (mm) ===")
for i, e in enumerate(eids):
    dd = dist[i][cort]
    print(f"  {e}: median {np.median(dd):.2f}  mean {dd.mean():.2f}  "
          f"%<2mm {100*(dd<=2).mean():.0f}  p95 {np.percentile(dd,95):.2f}")
dm = dist[:, cort]
print(f"  COHORT mean {dm.mean():.2f}  median {np.median(dm):.2f}  %<2mm {100*(dm<=2).mean():.0f}")
print(f"  between-subject SD per voxel: median {np.median(dist.std(0)[cort]):.2f} mm, "
      f"p95 {np.percentile(dist.std(0)[cort],95):.2f} mm")

# slice at cortical centroid
cx, cy, cz = [int(np.median(vox[cort, k])) for k in range(3)]
planes = [("Axial", lambda V: V[:, :, cz]),
          ("Coronal", lambda V: V[:, cy, :]),
          ("Sagittal", lambda V: V[cx, :, :])]

rows = [(e, per_subj_vol[i]) for i, e in enumerate(eids)]
rows += [("Mean (n=3)", mean_vol), ("Variability  SD", sd_vol)]
nrow = len(rows)
VMAX, SDMAX = 4.0, 2.0

fig, axes = plt.subplots(nrow, 3, figsize=(10.5, 2.45 * nrow))
for r, (label, V) in enumerate(rows):
    is_sd = label.startswith("Variability")
    norm = Normalize(0, SDMAX if is_sd else VMAX)
    cmap = "viridis" if is_sd else "hot"
    for c, (pname, sl) in enumerate(planes):
        ax = axes[r, c]
        ax.imshow(sl(tpl).T, cmap="gray", origin="lower",
                  vmin=np.percentile(tpl[tpl > 0], 1), vmax=np.percentile(tpl[tpl > 0], 99))
        ov = sl(V)
        m = np.ma.masked_where(ov <= 0, ov)
        im = ax.imshow(m.T, cmap=cmap, norm=norm, origin="lower", alpha=0.95)
        ax.axis("off")
        if c == 0:
            ax.text(-0.04, 0.5, label, transform=ax.transAxes, rotation=90,
                    va="center", ha="right", fontsize=10,
                    fontweight="bold" if r >= len(eids) else "normal")
        if r == 0:
            ax.set_title(pname, fontsize=10)
    # row colorbar
    cax = fig.add_axes([0.91, 1 - (r + 0.85) / nrow, 0.012, 0.6 / nrow])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("SD (mm)" if is_sd else "|dist| (mm)", fontsize=7)
    cb.ax.tick_params(labelsize=6)

fig.suptitle("Gray–white interface distance, template → each held-out subject (AFFINE = representativeness)\n"
             "age6_female pilot, n=3 — per-subject (top), then cohort Mean and between-subject Variability (SD)",
             fontsize=10.5)
fig.subplots_adjust(left=0.06, right=0.9, top=0.93, bottom=0.01, wspace=0.02, hspace=0.06)
out = f"{D}/age6_female_validity_persubject_affine.png"
fig.savefig(out, dpi=150)
print("wrote", out)
