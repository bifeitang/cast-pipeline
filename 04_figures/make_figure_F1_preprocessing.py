#!/usr/bin/env python3
"""Fig. 1 -- constraint-aware pediatric preprocessing, drawn with real subject imagery.

Replaces `preprocessing_pipeline.png`, a black-ground slide export. Uni-color house
style shared with Figs 2 and 4: one accent (`figs_schematic.ACCENT`), a pale
accent-tinted workflow panel, white outlined boxes, dashed accent connectors, tool names
in the accent, everything else black or grey. Spelling follows the manuscript, which is
US English throughout ("normalization", "recenter").

WHY THE NORMALIZATION PANEL SHOWS FIVE SUBJECTS, NOT ONE BEFORE/AFTER PAIR.
CSF anchoring divides a whole volume by one number, so within a subject it is a pure
change of units: a before/after image pair looks identical under any sane display window,
and showing one invites the reader to believe the step improved that subject's contrast,
which it did not and cannot. The step exists to make DIFFERENT subjects commensurable, so
the panel measures exactly that -- in-brain median intensity across five subjects, over
identical voxels (the raw volume masked by the normalized volume's own support, both on
the same grid, so no resampling is involved), before and after. Measured: 6.7x -> 1.19x.
Residual anterior-posterior brightness is bias field, which is N4's job at step 3, not
normalization's; nothing in this panel claims otherwise.

Every brain panel is the REAL intermediate volume from a run of the released pipeline:
  stages ............... anat/T1{,_crop_sanlm_n4,_..._brain,_..._brain_mask,
                         _..._buffermask,_..._csfNorm}.nii.gz  (one subject)
  normalization panel .. s1/sub-*_T1w.nii.gz  vs  intensity_improve/subj_*.nii.gz  (five)

Identifiable images: HBN distributes these scans already defaced, and every panel is
axial, which carries no facial profile. No subject identifier appears in the figure.

Run:  python3 make_figure_F1_preprocessing.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_schematic as S                                        # noqa: E402
from figs_schematic import fs_                                    # noqa: E402
from figs_style import set_style                                  # noqa: E402

ROOT = "/path/to/cast-project"
SUBJ = f"{ROOT}/07_Results_and_Analysis/mriqc_result/subject_folder"
ANAT = f"{SUBJ}/SUBJECT_ID_newpipeline/anat"
OUT = f"{os.path.dirname(os.path.abspath(__file__))}/F1_preprocessing"
NORM_IDS = ["SUBJECT_ID_1", "SUBJECT_ID_2", "SUBJECT_ID_3", "SUBJECT_ID_4",
            "SUBJECT_ID_5"]

W, H = 180.0, 104.0
GX, GW, GY, GH = 31.0, 102.0, 1.5, 95.0
BX, BW = 33.0, 98.0
ROW1, ROW2, ROW3, ROW4 = 84.0, 52.0, 16.0, 3.0
H1, H2, H3, H4 = 10.0, 30.0, 32.0, 11.0
SMALL_W = (BW - 2 * 3.0) / 3.0


# ------------------------------------------------------------------- imagery
def show(fig, path, x, y, w, h, ref=None, contour=None, frame=False):
    """One real brain panel at (x, y, w, h) mm, optionally with a mask outline."""
    import nibabel as nib
    from figs_brain import planes_mm
    img = nib.load(path)
    sl, ext = planes_mm(img, ref_img=ref)["axial"]
    vol = img.get_fdata()
    hi = float(np.percentile(vol[vol > 0], 99.5))
    ax = S.inset(fig, x, y, w, h, W, H)
    ax.imshow(sl, cmap="gray", origin="lower", extent=ext, aspect="equal",
              vmin=0, vmax=hi, interpolation="bilinear", zorder=5)
    if contour is not None:
        csl, cext = planes_mm(nib.load(contour), ref_img=ref)["axial"]
        ax.contour(csl, levels=[0.5], colors=[S.ACCENT], linewidths=0.7,
                   extent=cext, zorder=6)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(frame)
    return ax


# ------------------------------------------------- the normalization evidence
def normalization_curves():
    """In-brain intensity distributions of five subjects, before and after CSF
    anchoring, over IDENTICAL voxels: the raw volume masked by the normalized
    volume's own support. Both live on the same grid, so no resampling is involved."""
    import nibabel as nib
    before, after, med_b, med_a = [], [], [], []
    for sid in NORM_IDS:
        raw = nib.load(f"{SUBJ}/s1/sub-{sid}_T1w.nii.gz").get_fdata()[::2, ::2, ::2]
        nrm = nib.load(f"{SUBJ}/intensity_improve/subj_{sid}.nii.gz"
                       ).get_fdata()[::2, ::2, ::2]
        m = nrm > 0
        a, b = raw[m], nrm[m]
        med_b.append(float(np.median(a)))
        med_a.append(float(np.median(b)))
        for store, vals, rng in ((before, a, (0, 620)), (after, b, (0, 6))):
            cnt, e = np.histogram(vals, bins=140, range=rng)
            store.append((0.5 * (e[1:] + e[:-1]), cnt / cnt.max()))
    med_b, med_a = np.array(med_b), np.array(med_a)
    return before, after, med_b.max() / med_b.min(), med_a.max() / med_a.min()


def mini_hist(fig, x, y, w, h, curves, xlim, xticks, xlabel):
    ax = S.inset(fig, x, y, w, h, W, H)
    for cx, cy in curves:
        ax.plot(cx, cy, color=S.ACCENT, lw=0.7, alpha=0.85, zorder=3)
    ax.set_xlim(*xlim)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([])
    ax.set_xticks(xticks)
    ax.tick_params(labelsize=fs_(5.2), length=1.5, width=0.4, pad=1.0)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=fs_(5.4), labelpad=1.0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.4)


# ---------------------------------------------------------------------- draw
def main():
    set_style()
    import nibabel as nib
    fig, ax = S.canvas(W, H)
    ref = nib.load(f"{ANAT}/T1_crop_sanlm_n4_brain.nii.gz")

    S.txt(ax, 3.0, 100.4, "Constraint-aware pediatric preprocessing pipeline", fs=7.0,
          weight="bold")
    S.rbox(ax, GX, GY, GW, GH, fc=S.GROUND, ec="none", r=2.4, z=1)

    # ---------------------------------------------------------------- input
    S.txt(ax, 15.0, 66.0, "T1w images", fs=6.4, ha="center", weight="bold")
    S.txt(ax, 15.0, 62.2, "scan$_1$ – scan$_n$", fs=5.7, ha="center", color=S.MUTE)
    for k, d in enumerate((2.6, 1.3, 0.0)):
        S.rbox(ax, 4.4 + d, 38.0 - d, 20.0, 20.0, fc="black", ec=S.RULE, lw=0.4,
               r=0.6, z=2 + k)
    show(fig, f"{ANAT}/T1.nii.gz", 4.7, 38.3, 19.4, 19.4)
    S.txt(ax, 15.0, 33.0, "one scan per subject", fs=5.5, ha="center", color=S.MUTE)
    S.flow(ax, 26.0, 48.0, GX - 1.2, 48.0)

    # --------------------------------------------------------------- row 1
    for i, (title, tool) in enumerate(
            [("Reorient & FoV crop", "AFNI · FSL robustfov"),
             ("SANLM denoise", "reduced strength, v = 1"),
             ("N4 bias correction", "ANTs 2.5.0")]):
        x = BX + i * (SMALL_W + 3.0)
        S.dbox(ax, x, ROW1, SMALL_W, H1, title, tool)
        if i:
            S.flow(ax, x - 2.6, ROW1 + H1 / 2, x - 0.6, ROW1 + H1 / 2, head=2.0)
    S.flow(ax, BX + BW / 2, ROW1 - 0.6, BX + BW / 2, ROW2 + H2 + 0.6, head=2.0)

    # --------------------------------------------------------------- row 2
    big_w = (BW - 4.0) / 2
    S.dbox(ax, BX, ROW2, big_w, H2, "Brain extraction",
           "FreeSurfer autorecon-1 → DeepBET")
    S.txt(ax, BX + big_w / 2, ROW2 + H2 - 11.6, "mask, then autorecon-2 & -3",
          fs=5.5, ha="center", va="center", color=S.ACCENT)
    show(fig, f"{ANAT}/T1_crop_sanlm_n4.nii.gz", BX + 11.5, ROW2 + 3.0, 12.4, 12.4,
         ref=ref)
    show(fig, f"{ANAT}/T1_crop_sanlm_n4_brain.nii.gz", BX + 26.5, ROW2 + 3.0,
         12.4, 12.4, ref=ref, contour=f"{ANAT}/T1_crop_sanlm_n4_brain_mask.nii.gz")
    S.flow(ax, BX + 24.5, ROW2 + 9.2, BX + 26.0, ROW2 + 9.2, head=1.8)

    x2 = BX + big_w + 4.0
    S.dbox(ax, x2, ROW2, big_w, H2, "Background model", "2-voxel buffer shell")
    S.txt(ax, x2 + big_w / 2, ROW2 + H2 - 11.6, "outside = 1% of σ(air)",
          fs=5.5, ha="center", va="center", color=S.ACCENT)
    show(fig, f"{ANAT}/T1_crop_sanlm_n4_brain.nii.gz", x2 + (big_w - 12.4) / 2,
         ROW2 + 3.0, 12.4, 12.4, ref=ref,
         contour=f"{ANAT}/T1_crop_sanlm_n4_buffermask.nii.gz")
    S.flow(ax, BX + big_w + 1.0, ROW2 + H2 / 2, x2 - 0.6, ROW2 + H2 / 2, head=2.0)
    S.flow(ax, BX + BW / 2, ROW2 - 0.6, BX + BW / 2, ROW3 + H3 + 0.6, head=2.0)

    # --------------------------------------------------------------- row 3
    S.dbox(ax, BX, ROW3, BW, H3, "CSF-anchored intensity normalization", None)
    S.txt(ax, BX + BW / 2, ROW3 + H3 - 9.0,
          r"$I_{\mathrm{norm}}(x)\;=\;I(x)\,/\,\mu_{\mathrm{CSF}}$",
          fs=7.4, ha="center", va="center", color=S.ACCENT)
    before, after, sp_b, sp_a = normalization_curves()
    S.txt(ax, BX + BW / 2, ROW3 + H3 - 14.0,
          f"in-brain median across five subjects, identical voxels: "
          f"{sp_b:.1f}× spread → {sp_a:.2f}×",
          fs=5.6, ha="center", va="center", color=S.MUTE)
    S.txt(ax, BX + 24.0, ROW3 + H3 - 18.5, "before · scanner units", fs=5.8,
          ha="center", va="center", weight="bold")
    S.txt(ax, BX + 71.0, ROW3 + H3 - 18.5, "after · I / μ$_{\\mathrm{CSF}}$",
          fs=5.8, ha="center", va="center", weight="bold")
    mini_hist(fig, BX + 8.0, ROW3 + 4.5, 32.0, 8.5, before, (0, 620), [0, 300, 600],
              None)
    mini_hist(fig, BX + 55.0, ROW3 + 4.5, 32.0, 8.5, after, (0, 6), [0, 2, 4, 6],
              None)
    S.flow(ax, BX + 43.0, ROW3 + 8.8, BX + 52.0, ROW3 + 8.8, head=2.0)

    # --------------------------------------------------------------- row 4
    for i, (title, tool) in enumerate(
            [("MRIQC metrics", "Tenengrad, EFC, FWHM"),
             ("Expert screening", "failures excluded"),
             ("Recenter", "common origin")]):
        x = BX + i * (SMALL_W + 3.0)
        S.dbox(ax, x, ROW4, SMALL_W, H4, title, tool)
        if i:
            S.flow(ax, x - 2.6, ROW4 + H4 / 2, x - 0.6, ROW4 + H4 / 2, head=2.0)
    S.flow(ax, BX + 12.0, ROW3 - 0.6, BX + 12.0, ROW4 + H4 + 0.6, head=2.0)

    # -------------------------------------------------------------- outputs
    for path, label, y in (
            (f"{ANAT}/T1_crop_sanlm_n4_brain_mask.nii.gz", "Brain mask", 63.0),
            (f"{ANAT}/T1_crop_sanlm_n4_csfNorm.nii.gz",
             "Analysis-ready\nvolume → Fig. 2", 25.0)):
        S.rbox(ax, 137.0, y, 20.0, 20.0, fc="black", ec=S.RULE, lw=0.4, r=0.6, z=2)
        show(fig, path, 137.3, y + 0.3, 19.4, 19.4, ref=ref)
        S.txt(ax, 157.5, y + 10.0, label, fs=6.0, va="center", linespacing=1.4)
        S.flow(ax, GX + GW + 1.0, y + 10.0, 136.0, y + 10.0, head=2.0)

    S.save(fig, OUT)


if __name__ == "__main__":
    main()
