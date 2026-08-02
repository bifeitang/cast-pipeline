#!/usr/bin/env python3
"""Fig. 2 -- iterative groupwise diffeomorphic template construction.

Replaces `template_construction.png`. That figure embedded a four-panel
`Moving / Warp / Moved / Fixed` inset reproduced from another publication, with no
attribution in the caption -- which cannot be redistributed under the CC BY-NC-ND
licence the preprint carries. Panel b draws the same idea ourselves, from the schedule
actually used, so nothing third-party remains.

Uni-color house style shared with Figs 1 and 4: one accent (`figs_schematic.ACCENT`),
a pale accent-tinted workflow panel, white outlined boxes, dashed accent connectors,
tool names in the accent.

Provenance:
  loop structure and update rule ... manuscript Sec. "Template construction";
                                     ANTs antsMultivariateTemplateConstruction2.sh
  every flag and number in panel b . cast-pipeline/02_template_construction/README.md,
                                     "As-run invocation (identical across all 28
                                     published strata)"
  input thumbnail .................. a real preprocessed, CSF-normalised subject volume
                                     (the output of Fig. 1)
  output thumbnails ................ the released age-9 male template and its released
                                     GM / WM / CSF probability maps, from the deposit
  the four warped grids ............ ILLUSTRATIVE, and labelled so: they show what a
                                     coarse-to-fine schedule does, not measured data

Run:  python3 make_figure_F2_template_construction.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_schematic as S                                        # noqa: E402
from figs_style import set_style                                  # noqa: E402

ROOT = "/path/to/cast-project"
DEP = f"{ROOT}/06_Data/BRAINCAST_data_deposit/templates"
SUBJ = (f"{ROOT}/07_Results_and_Analysis/mriqc_result/subject_folder/"
        f"SUBJECT_ID_newpipeline/anat/T1_crop_sanlm_n4_csfNorm.nii.gz")
TPL = f"{DEP}/tpl-BRAINCAST_age-09_sex-M_T1w.nii.gz"
TPM = {t: f"{DEP}/tpl-BRAINCAST_age-09_sex-M_label-{t}_probseg.nii.gz"
       for t in ("GM", "WM", "CSF")}
OUT = f"{os.path.dirname(os.path.abspath(__file__))}/F2_template_construction"

W, H = 180.0, 108.0
GX, GW, GY, GH = 31.0, 100.0, 48.0, 46.0     # panel a workflow panel
BX, BW = 33.0, 96.0

LEVELS = [("8×", "4 vox", "120", 4, 1.0, 0.115),
          ("4×", "2 vox", "90", 6, 1.7, 0.085),
          ("2×", "1 vox", "60", 10, 2.6, 0.055),
          ("1×", "0 vox", "20", 16, 3.8, 0.032)]

# each option sits on one line with its meaning beside it, not stacked beneath it
CHIPS = [("-t SyN[0.1]", "diffeomorphic"),
         ("-m CC[2]", "cross-correlation"),
         ("-g 0.10", "gradient step"),
         ("-n 0", "no per-iteration N4"),
         ("-l 0", "no histogram match"),
         ("-r 1", "rigid pre-alignment")]


def show(fig, path, x, y, w, h, cmap="gray", frame=False, pct=99.5):
    """One real brain panel, canonical orientation and true physical scale."""
    import nibabel as nib
    from figs_brain import planes_mm
    img = nib.load(path)
    sl, ext = planes_mm(img)["axial"]
    vol = img.get_fdata()
    hi = float(np.percentile(vol[vol > 0], pct)) if (vol > 0).any() else 1.0
    ax = S.inset(fig, x, y, w, h, W, H)
    ax.imshow(sl, cmap=cmap, origin="lower", extent=ext, aspect="equal",
              vmin=0, vmax=hi, interpolation="bilinear", zorder=5)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(frame)
    return ax


def warped_grid(ax, x, y, s, n, k, amp):
    """A unit grid displaced by a smooth analytic field -- illustrative only."""
    t = np.linspace(0, 1, 121)
    g = np.linspace(0, 1, n + 1)

    def warp(u, v):
        return (u + amp * np.sin(k * np.pi * u) * np.cos(k * np.pi * v),
                v + amp * np.cos(k * np.pi * u) * np.sin(k * np.pi * v))

    for c in g:
        u, v = warp(np.full_like(t, c), t)
        ax.plot(x + u * s, y + v * s, color=S.ACCENT, lw=0.35, zorder=5)
        u, v = warp(t, np.full_like(t, c))
        ax.plot(x + u * s, y + v * s, color=S.ACCENT, lw=0.35, zorder=5)
    S.rbox(ax, x - 0.6, y - 0.6, s + 1.2, s + 1.2, fc="none", ec=S.RULE, r=0.6, z=6)


def main():
    set_style()
    fig, ax = S.canvas(W, H)

    # ============================================================== panel a
    S.panel_label(ax, 2.0, 107.0, "a")
    S.txt(ax, 8.0, 103.6, "One age × sex stratum → one unbiased template",
          fs=7.0, weight="bold")
    S.rbox(ax, GX, GY, GW, GH, fc=S.GROUND, ec="none", r=2.4, z=1)

    # ---- input
    S.txt(ax, 15.0, 89.0, "Preprocessed T1w", fs=6.4, ha="center", weight="bold")
    S.txt(ax, 15.0, 85.2, "n = 24–78 per stratum", fs=5.6, ha="center", color=S.MUTE)
    for k, d in enumerate((2.6, 1.3, 0.0)):
        S.rbox(ax, 4.4 + d, 62.0 - d, 20.0, 20.0, fc="black", ec=S.RULE, lw=0.4,
               r=0.6, z=2 + k)
    show(fig, SUBJ, 4.7, 62.3, 19.4, 19.4)
    S.txt(ax, 15.0, 57.0, "output of Fig. 1", fs=5.6, ha="center", color=S.MUTE)
    S.flow(ax, 26.0, 71.5, GX - 1.2, 71.5)

    # ---- seed
    S.dbox(ax, BX + 19.0, 84.0, 58.0, 9.6, "Seed  $T^{(0)}$",
           "one in-stratum scan (-z), rigid (-r 1)")
    S.flow(ax, BX + 48.0, 83.4, BX + 48.0, 78.6)

    # ---- the three loop steps
    step_w = (BW - 2 * 4.0) / 3
    steps = [("Register", "SyN · cross-correlation",
              ["every $I_k$ → current $T$", "one warp $φ_k$ each"]),
             ("Warp", "$I_k ∘ φ_k^{-1}$",
              ["resample each scan", "into template space"]),
             ("Average", "voxelwise mean",
              ["over N warped images", "→ updated $T^{(i)}$"])]
    for i, (title, tool, lines) in enumerate(steps):
        x = BX + i * (step_w + 4.0)
        S.dbox(ax, x, 56.0, step_w, 22.0, title, tool)
        for j, s in enumerate(lines):
            S.txt(ax, x + step_w / 2, 63.0 - j * 3.6, s, fs=5.6, ha="center",
                  color=S.MUTE)
        if i:
            S.flow(ax, x - 4.0 + 0.5, 67.0, x - 0.6, 67.0)

    # ---- the iteration
    arc = 50.6
    ax.plot([BX + BW - step_w / 2, BX + BW - step_w / 2, BX + step_w / 2],
            [55.4, arc, arc], color=S.ACCENT, lw=0.8, ls=(0, (2.6, 1.6)),
            solid_capstyle="round", zorder=6)
    S.flow(ax, BX + step_w / 2, arc, BX + step_w / 2, 55.4)
    S.txt(ax, BX + BW / 2, arc + 1.4, "repeat ×12   (-i 12)", fs=6.0, ha="center",
          color=S.ACCENT, weight="bold")

    # ---- outputs
    S.flow(ax, GX + GW + 1.0, 80.0, 136.0, 80.0)
    S.rbox(ax, 137.0, 71.0, 18.4, 18.4, fc="black", ec=S.RULE, lw=0.4, r=0.6, z=2)
    show(fig, TPL, 137.3, 71.3, 17.8, 17.8)
    S.txt(ax, 157.4, 82.0, "Age × sex", fs=6.2, weight="bold")
    S.txt(ax, 157.4, 78.0, "template", fs=6.2, weight="bold")
    S.txt(ax, 157.4, 74.0, "age 9, male shown", fs=5.5, color=S.MUTE)

    S.flow(ax, GX + GW + 1.0, 60.0, 136.0, 60.0)
    S.txt(ax, 137.0, 66.4, "Tissue probability maps", fs=6.2, weight="bold")
    for i, t in enumerate(("GM", "WM", "CSF")):
        x = 137.0 + i * 13.6
        S.rbox(ax, x, 51.0, 12.6, 12.6, fc="black", ec=S.RULE, lw=0.4, r=0.5, z=2)
        show(fig, TPM[t], x + 0.3, 51.3, 12.0, 12.0, pct=100)
        S.txt(ax, x + 6.3, 48.0, t, fs=5.6, ha="center", color=S.MUTE)

    # ============================================================== panel b
    S.panel_label(ax, 2.0, 42.0, "b")
    S.txt(ax, 8.0, 38.6, "As-run configuration, identical for all 28 strata",
          fs=7.0, weight="bold")

    S.txt(ax, 6.0, 33.0, "Coarse-to-fine schedule", fs=6.4, weight="bold")
    S.txt(ax, 6.0, 29.4, "-f 8x4x2x1   -s 4x2x1x0vox   -q 120x90x60x20",
          fs=5.8, color=S.MUTE, family="monospace")
    S.txt(ax, 84.0, 33.0, "schematic, not measured data", fs=5.4, color=S.MUTE,
          ha="right", style="italic")
    for i, (shrink, smooth, iters, n, k, amp) in enumerate(LEVELS):
        gx = 7.0 + i * 19.0
        warped_grid(ax, gx, 13.0, 13.5, n, k, amp)
        S.txt(ax, gx + 6.75, 9.4, f"{shrink} · {smooth}", fs=5.7, ha="center")
        S.txt(ax, gx + 6.75, 6.2, f"{iters} iterations", fs=5.5, ha="center",
              color=S.MUTE)
        if i:
            S.flow(ax, gx - 4.4, 19.8, gx - 1.4, 19.8, head=2.0)

    S.txt(ax, 88.0, 33.0, "Update rule", fs=6.4, weight="bold")
    S.txt(ax, 88.0, 26.8,
          r"$T^{(i)}(x)\;\;=\;\;\frac{1}{N}\,\sum_{k=1}^{N}\;"
          r"I_k\!\left(\phi_k^{-1}(x)\right)$",
          fs=8.5)
    S.txt(ax, 88.0, 19.4, "Options", fs=5.8, weight="bold", color=S.MUTE)
    for j, (flag, note) in enumerate(CHIPS):
        cx = 88.0 + (j // 3) * 46.0
        cy = 14.4 - (j % 3) * 5.5
        S.code(ax, cx, cy, flag, fs=6.0)
        S.txt(ax, cx + 22.0, cy, note, fs=5.4, color=S.MUTE, va="center")

    S.save(fig, OUT)


if __name__ == "__main__":
    main()
