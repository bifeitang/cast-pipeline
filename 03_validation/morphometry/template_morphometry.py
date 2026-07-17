import sys, json, subprocess, os
import numpy as np, nibabel as nib
from scipy import ndimage

tpl, outdir, name = sys.argv[1:4]
os.makedirs(outdir, exist_ok=True)
img = nib.load(tpl); data = img.get_fdata().astype(np.float32)
zooms = np.array(img.header.get_zooms()[:3], float); voxvol_ml = float(np.prod(zooms))/1000.0

# --- brain mask: use file if present, else derive (handles background-shell templates) ---
maskpath = tpl.replace("_template.nii.gz","_brain_mask.nii.gz")
if os.path.exists(maskpath):
    bm = nib.load(maskpath).get_fdata() > 0.5
else:
    nz = data[data>0]; thr = max(np.percentile(nz,55)*0.5, nz.max()*0.18)  # between background & GM
    bm = data > thr
    bm = ndimage.binary_closing(bm, iterations=2)
    bm = ndimage.binary_fill_holes(bm)
    lbl,n = ndimage.label(bm)
    if n>0:
        sizes=np.bincount(lbl.ravel()); sizes[0]=0; bm = lbl==sizes.argmax()
    bm = ndimage.binary_dilation(bm, iterations=3)  # recapture CSF rim
masked = data*bm
mpath = os.path.join(outdir, name+"_braintmp.nii.gz")
nib.save(nib.Nifti1Image(masked.astype(np.float32), img.affine, img.header), mpath)

base = os.path.join(outdir, name+"_fast")
subprocess.run(["fast","-t","1","-n","3","-g","-o",base, mpath],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pve0=nib.load(base+"_pve_0.nii.gz").get_fdata(); pve1=nib.load(base+"_pve_1.nii.gz").get_fdata(); pve2=nib.load(base+"_pve_2.nii.gz").get_fdata()
csf_ml=float(pve0.sum()*voxvol_ml); gm_ml=float(pve1.sum()*voxvol_ml); wm_ml=float(pve2.sum()*voxvol_ml); icv_ml=csf_ml+gm_ml+wm_ml
brain=(pve0+pve1+pve2)>0.5
wm=pve2>0.9; gm=pve1>0.9
mWM=float(data[wm].mean()) if wm.any() else float('nan'); mGM=float(data[gm].mean()) if gm.any() else float('nan')
bgvals=data[(data>0)&(data<np.percentile(data[data>0],2))]; noise=float(bgvals.std()) if bgvals.size>50 else float(data[gm].std())
contrast=(mWM-mGM)/(noise+1e-6)
gx,gy,gz=np.gradient(data, zooms[0],zooms[1],zooms[2]); gmag=np.sqrt(gx**2+gy**2+gz**2)
tenengrad=float((gmag[brain]**2).mean())
wmbin=pve2>0.5; boundary=wmbin & ~ndimage.binary_erosion(wmbin)
edge=float(gmag[boundary].mean()) if boundary.any() else float('nan')
def fd_boxcount(maskbin, zooms):
    pts=np.argwhere(maskbin).astype(float)*zooms
    if len(pts)<50: return float('nan')
    pts-=pts.min(0); sizes=np.array([1.6,3.2,6.4,12.8],float); counts=[]
    for s in sizes: counts.append(len(set(map(tuple,(pts//s).astype(int)))))
    return float(-np.polyfit(np.log(sizes),np.log(np.array(counts,float)),1)[0])
fd=fd_boxcount(boundary,zooms)
out=dict(name=name, vox_mm=round(float(zooms[0]),2), gm_ml=round(gm_ml,1), wm_ml=round(wm_ml,1), csf_ml=round(csf_ml,1),
         icv_ml=round(icv_ml,1), gmwm_contrast=round(contrast,3), tenengrad=round(tenengrad,4),
         edge_strength=round(edge,4), fd=round(fd,3), meanWM=round(mWM,3), meanGM=round(mGM,3),
         had_mask=os.path.exists(maskpath))
for suf in ["_pve_0","_pve_1","_pve_2","_seg","_mixeltype","_pveseg"]:
    f=base+suf+".nii.gz";  os.path.exists(f) and os.remove(f)
os.path.exists(mpath) and os.remove(mpath)
print(json.dumps(out))
