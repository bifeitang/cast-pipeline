#!/usr/bin/env python3
"""weber_mech.py -- WM-GM Weber-contrast locus test (subject vs averaged template).

Step 2 of the CAST contrast-deficit mechanism investigation (HANDOFF 2026-06-14, sec 4).

Decisive question: CAST's CSF-anchored normalization is a PURE GLOBAL SCALAR
    I_norm(x) = I(x) / mean_ventricular_CSF
which is mathematically INVARIANT to Weber contrast (WM-GM)/GM (the scalar cancels).
So changing the global-scalar anchor (CSF -> WM, etc.) cannot change any individual
subject's WM-GM contrast. If the AVERAGED CAST template nonetheless has lower
WM-GM contrast than NKI, the deficit must arise at the AVERAGING stage (mis-registration
/ anatomical-variability blur), NOT at normalization -> full-library re-normalization
would be a misdiagnosis.

This script measures WM-GM Weber contrast on a CONSISTENT, mask-free definition across
three item kinds so they are directly comparable:
  (a) individual CSF-normalized CONSTRUCTION subjects (the inputs that were averaged),
  (b) the averaged CAST 0.8 mm template,
  (c) the matched NKI template.
Subjects have no tissue masks, so tissue levels are recovered by a 3-class Otsu
threshold (CSF / GM / WM) computed from the brain-masked intensity histogram --
identical procedure for all items. For items that DO have masks (templates), a
mask-based Weber and the team's "WM(all) vs GM-ring" operative Weber are ALSO reported
so the mask-free estimator can be cross-validated against the published numbers
(CAST age7_male ~0.277, NKI ~0.393 under the operative def).

Weber = (median(I_WM) - median(I_GM)) / median(I_GM), higher = more contrast.

Manifest (pipe-delimited, one item per line; use NONE for absent paths):
  kind|label|age|sex|img|brain|wm|gm
Usage:
  weber_mech.py <manifest> <out_jsonl>
Writes one JSON object per line to <out_jsonl> and echoes a compact line to stdout.
"""
import sys, json
import numpy as np
import nibabel as nib
from scipy import ndimage


def otsu3(x, nbins=256):
    """Two thresholds (t1<t2) splitting x into CSF/GM/WM by max between-class variance.
    Pure-numpy 3-class Otsu over a robust [p1,p99] histogram. Returns (t1,t2)."""
    lo, hi = np.percentile(x, [1.0, 99.0])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return float(np.median(x)), float(np.median(x))
    edges = np.linspace(lo, hi, nbins + 1)
    hist, _ = np.histogram(x, bins=edges)
    p = hist.astype(np.float64)
    s = p.sum()
    if s <= 0:
        return float(lo), float(hi)
    p /= s
    centers = 0.5 * (edges[:-1] + edges[1:])
    P = np.cumsum(p)                 # P[i] = mass up to and incl bin i
    M = np.cumsum(p * centers)       # first moment
    muT = M[-1]
    n = len(p)
    best, t1, t2 = -1.0, centers[0], centers[-1]
    for i in range(1, n - 1):
        w0 = P[i]
        if w0 <= 1e-9:
            continue
        m0 = M[i]
        mu0 = m0 / w0
        for j in range(i + 1, n):
            w1 = P[j] - P[i]
            w2 = 1.0 - P[j]
            if w1 <= 1e-9 or w2 <= 1e-9:
                continue
            mu1 = (M[j] - M[i]) / w1
            mu2 = (muT - M[j]) / w2
            var = w0 * (mu0 - muT) ** 2 + w1 * (mu1 - muT) ** 2 + w2 * (mu2 - muT) ** 2
            if var > best:
                best, t1, t2 = var, centers[i], centers[j]
    return float(t1), float(t2)


def load(path):
    return nib.load(path).get_fdata().astype(np.float64)


def measure(kind, label, age, sex, img_p, brain_p, wm_p, gm_p):
    I = load(img_p)
    if brain_p != "NONE":
        region = load(brain_p) > 0.5
    else:
        region = np.isfinite(I) & (I > 0)
    x = I[region]
    x = x[np.isfinite(x) & (x > 0)]
    out = {
        "kind": kind, "label": label, "age": age, "sex": sex,
        "img": img_p, "n_brain_vox": int(x.size), "shape": list(I.shape),
    }
    if x.size < 1000:
        out["error"] = "too few brain voxels"
        return out

    # --- mask-free 3-class Otsu Weber (the cross-item-comparable definition) ---
    t1, t2 = otsu3(x)
    csf = x[x < t1]
    gm = x[(x >= t1) & (x < t2)]
    wm = x[x >= t2]
    gm_med = float(np.median(gm)) if gm.size else float("nan")
    wm_med = float(np.median(wm)) if wm.size else float("nan")
    csf_med = float(np.median(csf)) if csf.size else float("nan")
    out.update({
        "otsu_t1": t1, "otsu_t2": t2,
        "csf_med_otsu": csf_med, "gm_med_otsu": gm_med, "wm_med_otsu": wm_med,
        "n_gm_otsu": int(gm.size), "n_wm_otsu": int(wm.size),
        "weber_otsu": (wm_med - gm_med) / gm_med if gm_med else float("nan"),
    })

    # --- mask-based cross-checks (templates only) ---
    if wm_p != "NONE":
        wmask = load(wm_p) > 0.5
        wm_m = float(np.median(I[wmask & (I > 0)]))
        # team operative def: WM(all) vs GM ring (2-vox dilation of WM minus WM)
        ring = ndimage.binary_dilation(wmask, iterations=2) & ~wmask
        gm_ring = I[ring & (I > 0)]
        if gm_ring.size:
            gmr = float(np.median(gm_ring))
            out["weber_ring_operative"] = (wm_m - gmr) / gmr
            out["wm_med_mask"] = wm_m
            out["gm_ring_med"] = gmr
        if gm_p != "NONE":
            gmask = load(gm_p) > 0.5
            gm_m = float(np.median(I[gmask & (I > 0)]))
            out["weber_wmgm_mask"] = (wm_m - gm_m) / gm_m
            out["gm_med_mask"] = gm_m
    return out


def main():
    manifest, out_jsonl = sys.argv[1], sys.argv[2]
    with open(manifest) as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
    with open(out_jsonl, "w") as fo:
        for ln in lines:
            parts = ln.split("|")
            if len(parts) != 8:
                print("[skip malformed]", ln, file=sys.stderr)
                continue
            kind, label, age, sex, img_p, brain_p, wm_p, gm_p = parts
            try:
                rec = measure(kind, label, age, sex, img_p, brain_p, wm_p, gm_p)
            except Exception as e:  # noqa
                rec = {"kind": kind, "label": label, "error": repr(e), "img": img_p}
            fo.write(json.dumps(rec) + "\n")
            fo.flush()
            wb = rec.get("weber_otsu", float("nan"))
            print(f"{kind:14s} {label:34s} weber_otsu={wb:.4f}"
                  + (f" ring={rec['weber_ring_operative']:.4f}" if "weber_ring_operative" in rec else ""),
                  flush=True)


if __name__ == "__main__":
    main()
