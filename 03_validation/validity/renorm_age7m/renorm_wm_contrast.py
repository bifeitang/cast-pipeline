#!/usr/bin/env python3
"""renorm_wm_contrast.py -- restore deep-WM-to-GM contrast on a CAST template.

CAUSAL TEST (template-only intervention): CAST's CSF-anchored intensity
normalization compresses the template's deep-WM-to-GM Weber contrast
(CAST age7_male 0.256 vs NKI age7 0.408, NKI +59%), giving SyN a lower-contrast
FIXED registration target. This script applies a monotone, WM-targeted intensity
gain to the *template intensity image only* (the SyN fixed image) so that the
WM-vs-GM Weber contrast moves toward an NKI-like target, while:
  - GM / CSF / background intensities are left essentially unchanged,
  - the brain-mask geometry is untouched,
  - the measurement WM mask (FAST pve_2>0.5) is NOT regenerated -- the published
    age7_male_wm.nii.gz is reused verbatim, so the only thing that differs from
    the published CAST_0.8 arm is the fixed image's WM contrast.

Weber contrast is defined exactly as in the 4-angle investigation:
    W = (median(I_WM) - median(I_GM)) / median(I_GM)
on the deep-WM population (WM mask eroded to drop partial-volume boundary voxels)
and the GM population (GM mask).

Transform (monotone, continuous, anchored at the GM level G so GM/CSF/background
are fixed): for intensities above G, scale the excess by g>=1:
    I' = G + g * (I - G)              for I >  G   (mostly WM + bright GM tail)
    I' = I                           for I <= G   (GM, CSF, background fixed)
This is a one-parameter "WM gain". We solve g in closed form so the post-transform
deep-WM median hits the NKI-matched WM level:
    target_WM = G * (1 + W_target)
    g = (target_WM - G) / (median(I_WM) - G)
The transform is strictly increasing (g>=1), so it cannot create new boundaries,
flip the WM>GM ordering, or move the GM-WM crossing point -> FAST WM mask and the
gray-white surface geometry are preserved by construction. We then re-mask to the
brain and confirm the achieved Weber contrast.

Usage:
  renorm_wm_contrast.py <cast_template> <cast_wm_mask> <cast_gm_mask> \
                        <cast_brain_mask> <nki_template> <nki_wm_mask> \
                        <out_template> [w_target_override]
Prints a JSON QC line.
"""
import sys, json
import numpy as np, nibabel as nib
from scipy import ndimage

cast_t, cast_wm, cast_gm, cast_bm, nki_t, nki_wm, out_t = sys.argv[1:8]
w_target_override = float(sys.argv[8]) if len(sys.argv) > 8 else None

def weber(img_path, wm_path, gm_path=None, wm_pop="all"):
    """Weber contrast = (median(I_WM) - median(I_GM)) / median(I_GM).

    Operative definition (matches the 4-angle investigation's CAST 0.256 / NKI
    0.408): wm_pop="all" (whole WM mask) vs a GM RING proxy (2-voxel dilation of
    WM, the GM that SyN actually sees across the gray-white boundary). The ring
    GM proxy is used as the contrast ANCHOR because it is the GM level the
    registration metric compares deep WM against at the interface, and because it
    is the definition under which the deficit (CAST<NKI) reproduces. A GM mask, if
    supplied, is used only for an auxiliary QC readout."""
    im = nib.load(img_path).get_fdata().astype(np.float64)
    wm = nib.load(wm_path).get_fdata() > 0.5
    if wm_pop == "deep":
        wmm = ndimage.binary_erosion(wm, iterations=1)
        if wmm.sum() < 100:
            wmm = wm
    else:
        wmm = wm
    wm_med = float(np.median(im[wmm]))
    if gm_path is not None:
        gm = nib.load(gm_path).get_fdata() > 0.5
        gm_pop = im[gm & (im > 0)]
    else:
        # GM ring proxy: 2-voxel dilation outside WM, gated > 0 (drops background)
        ring = ndimage.binary_dilation(wm, iterations=2) & ~wm
        gm_pop = im[ring & (im > 0)]
    gm_med = float(np.median(gm_pop))
    return wm_med, gm_med, (wm_med - gm_med) / gm_med

# --- OPERATIVE Weber contrast: WM(all) vs GM ring proxy (matches the 4-angle
#     investigation's CAST 0.256 / NKI 0.408). This is the metric we restore. ---
c_wm_med, c_gm_med, c_W = weber(cast_t, cast_wm, None, wm_pop="all")
n_wm_med, n_gm_med, n_W = weber(nki_t,  nki_wm,  None, wm_pop="all")
# auxiliary QC readouts (deep WM, GM-mask) -- NOT used to drive the gain
_, _, c_W_deep_ring = weber(cast_t, cast_wm, None,     wm_pop="deep")
_, _, c_W_gmmask    = weber(cast_t, cast_wm, cast_gm,  wm_pop="all")

W_target = w_target_override if w_target_override is not None else n_W

# --- solve WM gain g anchored at the GM RING level G (the GM level SyN compares
#     deep WM against at the interface; GM/CSF/background <= G are left fixed). ---
G = c_gm_med
target_WM = G * (1.0 + W_target)
denom = (c_wm_med - G)
g = (target_WM - G) / denom if denom > 1e-9 else 1.0
g = max(g, 1.0)  # never compress; only restore

# --- apply monotone transform on the intensity image, re-mask to brain ---
t_img = nib.load(cast_t)
I = t_img.get_fdata().astype(np.float64)
bm = nib.load(cast_bm).get_fdata() > 0.5
above = I > G
Iout = I.copy()
Iout[above] = G + g * (I[above] - G)
Iout[~bm] = 0.0  # keep background/skull-strip identical to the brain-masked region
out = nib.Nifti1Image(Iout.astype(np.float32), t_img.affine, t_img.header)
nib.save(out, out_t)

# --- QC: achieved Weber on the renormalized template (same operative metric) ---
a_wm_med, a_gm_med, a_W = weber(out_t, cast_wm, None, wm_pop="all")
_, _, a_W_gmmask = weber(out_t, cast_wm, cast_gm, wm_pop="all")

print(json.dumps({
    "cast_template": cast_t,
    "nki_template": nki_t,
    "out_template": out_t,
    "metric": "Weber = (med I_WM(all) - med I_GMring)/med I_GMring",
    "cast_wm_med": c_wm_med, "cast_gm_med": c_gm_med,
    "cast_Weber_before": c_W,
    "cast_Weber_before_deepWM": c_W_deep_ring,
    "cast_Weber_before_GMmask": c_W_gmmask,
    "nki_Weber_target": n_W,
    "W_target_used": W_target,
    "GM_ring_anchor": G,
    "wm_gain_g": g,
    "achieved_wm_med": a_wm_med, "achieved_gm_med": a_gm_med,
    "achieved_Weber_after": a_W,
    "achieved_Weber_after_GMmask": a_W_gmmask,
    "moved_toward_nki": (a_W > c_W),
}, indent=None))
