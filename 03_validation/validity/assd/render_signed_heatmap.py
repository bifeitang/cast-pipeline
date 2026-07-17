#!/usr/bin/env python3
"""render_signed_heatmap.py -- signed gray-white bias overlaid on the template.

Diverging map centered at 0: red = template boundary OUTSIDE the subjects' white surface
(template WM larger there), blue = interior (template WM smaller). Sparse boundary voxels are
dilated for visibility and overlaid on the grayscale template.

Usage: render_signed_heatmap.py <out.png> <label1> <tpl1> <heat1> [<label2> <tpl2> <heat2> ...]
"""
import sys, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
from scipy import ndimage

outp = sys.argv[1]
items = sys.argv[2:]
strata = [(items[i], items[i+1], items[i+2]) for i in range(0, len(items), 3)]
VLIM = 1.0  # mm

fig, axes = plt.subplots(len(strata), 3, figsize=(11, 3.4 * len(strata)))
if len(strata) == 1:
    axes = axes[None, :]
im = None
for r, (label, tplp, heatp) in enumerate(strata):
    tpl = nib.load(tplp).get_fdata()
    heat = nib.load(heatp).get_fdata()
    # dilate sparse boundary for visibility (in-plane only handled per slice)
    nz = heat != 0
    # choose 3 slices (sagittal, coronal, axial) at the centroid of the boundary mass
    cz = np.argwhere(nz).mean(0).astype(int)
    views = [('sagittal', 0), ('coronal', 1), ('axial', 2)]
    for c, (vname, ax_dim) in enumerate(views):
        ax = axes[r, c]
        sl = [slice(None)] * 3; sl[ax_dim] = cz[ax_dim]
        bg = tpl[tuple(sl)].T
        hv = heat[tuple(sl)].T
        hm = hv != 0
        # dilate the in-plane boundary for visibility
        hm_d = ndimage.binary_dilation(hm, iterations=1)
        hv_d = np.where(hm_d, ndimage.grey_dilation(np.where(hm, hv, 0), size=3), 0)
        ax.imshow(bg, cmap='gray', origin='lower', aspect='equal',
                  vmin=np.percentile(bg, 1), vmax=np.percentile(bg, 99))
        masked = np.ma.masked_where(~hm_d, hv_d)
        im = ax.imshow(masked, cmap='RdBu_r', origin='lower', aspect='equal', vmin=-VLIM, vmax=VLIM)
        ax.set_xticks([]); ax.set_yticks([])
        if c == 0:
            ax.set_ylabel(label, fontsize=11, fontweight='bold')
        if r == 0:
            ax.set_title(vname, fontsize=10)

fig.subplots_adjust(right=0.9, hspace=0.05, wspace=0.05)
cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
cb = fig.colorbar(im, cax=cax)
cb.set_label('signed gray–white bias (mm)\n← template WM smaller   |   larger →', fontsize=9)
fig.suptitle('Signed gray–white interface bias of held-out subjects on the matched CAST template',
             fontsize=11, fontweight='bold', y=0.99)
fig.savefig(outp, dpi=160, bbox_inches='tight')
fig.savefig(outp.replace('.png', '.pdf'), bbox_inches='tight')
print(f"[saved] {outp} (+pdf)")
