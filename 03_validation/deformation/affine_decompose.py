import glob, os, numpy as np, nibabel as nib
from scipy.io import loadmat

AGE = {"NDARxxxxxxxx":6.07, "NDARxxxxxxxx":6.99, "NDARxxxxxxxx":6.70}
FLIP = np.diag([-1.,-1.,1.])           # ITK LPS -> nibabel RAS
maskcache = {}
def mask_xyz(tpl):
    if tpl not in maskcache:
        m = nib.load(f"affine_decomp/masks/{tpl}_brain_mask.nii.gz")
        ijk = np.argwhere(m.get_fdata() > 0.5)
        maskcache[tpl] = nib.affines.apply_affine(m.affine, ijk)   # RAS world mm
    return maskcache[tpl]

rows=[]
for f in sorted(glob.glob("affine_decomp/mats/*.mat")):
    base = os.path.basename(f)[:-4]
    eid, tpl = base.split("__")
    d = loadmat(f)
    p = d["AffineTransform_double_3_3"].ravel()
    M = p[:9].reshape(3,3); t = p[9:12]; c = d["fixed"].ravel()
    M = FLIP@M@FLIP; t = FLIP@t; c = FLIP@c          # -> RAS
    x = mask_xyz(tpl)
    u = (M - np.eye(3)) @ (x - c).T + t[:,None]      # 3 x Nvox displacement (mm)
    u = u.T
    mag = np.linalg.norm(u, axis=1)
    ubar = u.mean(axis=0)
    demean = np.linalg.norm(u - ubar, axis=1)
    tage = int(tpl.replace("age","").split("_")[0]); tsex = tpl.split("_")[1]
    rows.append(dict(eid=eid, sage=AGE[eid], tage=tage, tsex=tsex,
                     total=mag.mean(), translation=np.linalg.norm(ubar), affresid=demean.mean()))

print(f"{'subject':12s} {'sage':>4} {'tpl':>10} | {'TOTAL':>7} {'transl':>7} {'aff_resid':>9}  (mm, masked mean |affine disp|)")
for r in sorted(rows, key=lambda r:(r['eid'], r['tsex'], r['tage'])):
    print(f"{r['eid']:12s} {r['sage']:4.1f} age{r['tage']}_{r['tsex']:<6} | {r['total']:7.2f} {r['translation']:7.2f} {r['affresid']:9.2f}")

import numpy as _np
tot=_np.array([r['total'] for r in rows]); tr=_np.array([r['translation'] for r in rows]); ar=_np.array([r['affresid'] for r in rows])
print(f"\nOVERALL (n={len(rows)}): mean TOTAL affine disp = {tot.mean():.2f} mm | translation = {tr.mean():.2f} mm "
      f"({100*tr.mean()/tot.mean():.0f}% of total) | affine-residual(scale/shear/rot) = {ar.mean():.2f} mm")
# does affine-residual (the size/shape part) trend with |age-diff|?
fem=[r for r in rows if r['tsex']=='female']
ad=_np.array([abs(r['tage']-r['sage']) for r in fem]); arf=_np.array([r['affresid'] for r in fem])
print(f"female-only: corr(|age-diff|, affine-residual) = {_np.corrcoef(ad,arf)[0,1]:+.3f}  "
      f"(if >0 and meaningful, the size/scale part DOES carry an age signal)")
