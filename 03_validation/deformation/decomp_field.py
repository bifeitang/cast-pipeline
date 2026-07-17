import sys, numpy as np, nibabel as nib
field_path, mask_path, label = sys.argv[1:4]
f = np.squeeze(nib.load(field_path).get_fdata())   # (X,Y,Z,3) ANTs disp field, mm world
mask = nib.load(mask_path).get_fdata() > 0.5
u = f[mask]
mag = np.linalg.norm(u, axis=1)
ubar = u.mean(axis=0)
demean = np.linalg.norm(u - ubar, axis=1)
print(f"{label:8s} mean|u|={mag.mean():7.3f}  median|u|={np.median(mag):7.3f}  p95={np.percentile(mag,95):7.3f}  "
      f"||translation_ubar||={np.linalg.norm(ubar):7.3f}  demeaned_mean={demean.mean():7.3f}")
