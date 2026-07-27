"""Signed gray-white interface bias, two example strata (methods manuscript Fig. 7).

RECONSTRUCTED GENERATOR (2026-07-27). The published `signed_bias_heatmap.png` was
hand-made and had no generator anywhere in the repo -- the same gap the descriptor's
Figs 2/3/4 had. Provenance was established from the plotted values: the row labels
read n=35 and n=23, which match `n_subjects` in the age7_male and age9_female entries
of sweep_aggregate/heatmaps/*_summary.json exactly, and the overlay is
`*_signedbias_heatmap.nii.gz` from the same directory (identical affine to the
matched template, so no resampling is involved).

What it shows: the per-voxel MEAN SIGNED offset between the held-out subjects' white
surface and the matched template's gray-white boundary. Red = template WM larger than
the subject's, blue = smaller. This complements the magnitude map in Fig. 6: a small
unsigned error could still hide a systematic directional bias, and this shows it does
not -- the map is sub-voxel along the ribbon with no large one-signed regions.

*** THE PUBLISHED FIGURE DID NOT SHOW THIS. *** It was titled "signed", carried a
diverging red/blue bar labelled "template WM smaller | larger", and was captioned as
the signed offset -- but it plotted `*_meanabs_heatmap.nii.gz`, the UNSIGNED magnitude.
Measured on the published PNG's age-7-male coronal panel, 98.3% of coloured pixels are
red and 1.7% blue; rendering the two candidate overlays through this same code gives
100.0% red for meanabs and 63.6% BLUE for signedbias. A strictly non-negative map
cannot be anything but red under a zero-centred diverging colormap, which is why the
published panel looked uniformly red. So Fig. 7 duplicated Fig. 6's magnitude instead
of complementing it, and its caption's central claim -- "low residual structural bias,
not merely small unsigned error" -- had no support in the graphic. This script plots
the signed map, which is what that claim needs.

The caption's "cohort mean signed offset -0.04 to -0.20 mm" does not reproduce from any
generation of this data. The measured cortical means for the two plotted strata are
-0.08 (age-7 male) and -0.26 (age-9 female); across all 16 strata the range is +0.03 to
-0.26 mm. See the printout at the end of this script.

Inputs (both refreshed on carya 2026-07-26 14:41-14:47, pulled 2026-07-27):
  sweep_aggregate/heatmaps/{stratum}_signedbias_heatmap.nii.gz
  sweep_aggregate/heatmaps/{stratum}_summary.json          (n and the cohort mean)
  ../08_Working_Temp/InspectionTemp/UpdatedTemplates/{stratum}_template.nii.gz  (underlay)

Rendering: volumes are reoriented to canonical RAS, sliced at the TEMPLATE brain's
centroid (the overlay is a thin boundary shell and centres poorly on itself), and each
panel is cropped to a fixed 180 mm box about that centroid and drawn on a true
millimetre extent. Brains are therefore centred, cut to the same box, and comparable in
size between the two rows. See figs_brain.py.
"""
import json, sys, os
import numpy as np, nibabel as nib
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
sys.path.insert(0, "/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, DIV_CMAP
from figs_brain import planes_mm, canonical, brain_centroid_vox, window
set_style()

ROOT = "/path/to/cast-project"
HEAT = f"{ROOT}/07_Results_and_Analysis/sweep_aggregate/heatmaps"
TPL  = f"{ROOT}/08_Working_Temp/InspectionTemp/UpdatedTemplates"

# The two strata the published figure shows. Kept explicit rather than derived, because
# "two example strata" is an editorial choice, not a property of the data.
STRATA = [("age7_male", "age 7 male"), ("age9_female", "age 9 female")]
VLIM = 1.0                      # mm; matches the published colour range
CLIP_ORIENT = ("sagittal", "coronal", "axial")


def load(stratum):
    """Return the overlay image, the template image, and the summary JSON."""
    ov = nib.load(f"{HEAT}/{stratum}_signedbias_heatmap.nii.gz")
    tp = nib.load(f"{TPL}/{stratum}_template.nii.gz")
    if not np.allclose(ov.affine, tp.affine, atol=1e-4):
        raise SystemExit(f"{stratum}: overlay and template are not in the same space; "
                         "resampling would be required and this script does not do it.")
    summ = json.load(open(f"{HEAT}/{stratum}_summary.json"))
    return ov, tp, summ


fig, axes = plt.subplots(len(STRATA), 3, figsize=(9.0, 5.8))
norm = TwoSlopeNorm(vmin=-VLIM, vcenter=0.0, vmax=VLIM)
im_handle = None
report = []

for r, (stratum, label) in enumerate(STRATA):
    ov_img, tp_img, summ = load(stratum)
    tp = canonical(tp_img).get_fdata()
    # Slice both the overlay and the underlay at the TEMPLATE brain's centroid, in the
    # canonical frame, and crop each panel to a fixed 180 mm box around it. The overlay
    # is a thin boundary shell, so its own centroid is a poor centring reference.
    cen = brain_centroid_vox(tp)
    ov_p = planes_mm(ov_img, centroid_vox=cen)
    tp_p = planes_mm(tp_img, centroid_vox=cen)
    n = summ["n_subjects"]
    report.append((stratum, n, summ["cortical"]["mean_signed_err_mm"],
                   ov_img.get_fdata()[ov_img.get_fdata() != 0].mean(),
                   tuple(int(round(v)) for v in cen)))

    lo, hi = window(tp)
    for c, plane in enumerate(CLIP_ORIENT):
        ax = axes[r, c]
        under, ext = tp_p[plane]
        over, _ = ov_p[plane]
        ax.imshow(under, cmap="gray", origin="lower", extent=ext, aspect="equal",
                  vmin=lo, vmax=hi, interpolation="nearest")
        im_handle = ax.imshow(np.ma.masked_where(over == 0, over), cmap=DIV_CMAP,
                              norm=norm, origin="lower", extent=ext, aspect="equal",
                              interpolation="nearest")
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values(): sp.set_visible(False)
        if r == 0: ax.set_title(plane, fontsize=8.5)
    axes[r, 0].set_ylabel(f"{label} (n={n})", fontsize=8.5, fontweight="bold")

# one scale bar, bottom-left panel, since every panel is now in true mm
sb = axes[-1, 0]
sb.plot([-80, -30], [-78, -78], color="white", lw=2.0, solid_capstyle="butt")
sb.text(-55, -73, "50 mm", color="white", ha="center", va="bottom", fontsize=6)

cb = fig.colorbar(im_handle, ax=axes, fraction=0.020, pad=0.02)
cb.set_label("signed gray-white bias (mm)\n" r"$\leftarrow$ template WM smaller  |  larger $\rightarrow$",
             fontsize=7)
cb.ax.tick_params(labelsize=6)
fig.suptitle("Signed gray-white interface bias of held-out subjects on the matched BRAIN CAST template",
             fontsize=9.5, fontweight="bold")
save(fig, "figures_final/signed_bias_heatmap")

print("=== signed gray-white bias (two example strata) ===")
print(f"{'stratum':<14}{'n':>4}{'cortical mean':>15}{'whole-map mean':>16}   slice (i,j,k)")
for stratum, n, cm, wm, idx in report:
    print(f"{stratum:<14}{n:>4}{cm:>+15.4f}{wm:>+16.4f}   {idx}")
print("\nColour range clipped to +/-%.1f mm; the maps' full range is wider (~+/-6 mm) at a"
      "\nhandful of boundary voxels, which is why the published figure clips too." % VLIM)
