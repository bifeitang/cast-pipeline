#!/usr/bin/env python3
"""extract_slices.py -- pull matched montage slices from a rigidly-aligned template + tissues.

All templates are rigidly aligned to ONE common reference grid, so a fixed voxel index is the
same physical location across ages/sexes (matched anatomy), and rigid alignment preserves true
brain size (no scaling) -> the mm-space montage shows real growth. Saves a compact .npz of 2D
slices + tissue volumes (rigid-invariant) for age 16 and the trajectory plot.

Usage: extract_slices.py <brain> <csf_pve> <gm_pve> <wm_pve> <out.npz> <age> <sex>
"""
import sys, numpy as np, nibabel as nib

brain_p, csf_p, gm_p, wm_p, outp, age, sex = sys.argv[1:8]
load = lambda p: nib.load(p).get_fdata().astype(np.float32)
br, csf, gm, wm = load(brain_p), load(csf_p), load(gm_p), load(wm_p)
vox = tuple(float(z) for z in nib.load(brain_p).header.get_zooms()[:3])
nx, ny, nz = br.shape

out = {'age': int(age), 'sex': sex, 'vox': np.array(vox, np.float32), 'shape': np.array(br.shape)}
# sagittal / coronal mid (common grid => matched location)
out['brain_sag'] = br[nx // 2, :, :]
out['brain_cor'] = br[:, ny // 2, :]
# axial at several physical levels (fraction of grid) so the best can be picked at render time
for fr in (0.40, 0.45, 0.50, 0.55, 0.60):
    z = int(nz * fr)
    out[f'brain_ax_{int(fr*100)}'] = br[:, :, z]
    out[f'gm_ax_{int(fr*100)}'] = gm[:, :, z]
    out[f'wm_ax_{int(fr*100)}'] = wm[:, :, z]
    out[f'csf_ax_{int(fr*100)}'] = csf[:, :, z]
# rigid-invariant tissue volumes (mL) from the partial-volume estimates
vv = float(np.prod(vox)) / 1000.0
out['gm_ml'] = float(gm.sum() * vv)
out['wm_ml'] = float(wm.sum() * vv)
out['csf_ml'] = float(csf.sum() * vv)
out['icv_ml'] = out['gm_ml'] + out['wm_ml'] + out['csf_ml']
np.savez_compressed(outp, **out)
print(f"[slices] age{age}_{sex} vox={vox} ICV={out['icv_ml']:.0f} GM={out['gm_ml']:.0f} "
      f"WM={out['wm_ml']:.0f} CSF={out['csf_ml']:.0f}")
