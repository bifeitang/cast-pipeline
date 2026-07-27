"""Qualitative pipeline ablation: original vs intermediate vs final (methods Fig. 13).

RECONSTRUCTED GENERATOR (2026-07-27). `compare_pipelines.png` was a slide-style graphic
(hand-set dark-red text on a transparent background) with no generator in the repo and,
unlike the other figures, no plotted numbers to reverse-engineer from.

Provenance was instead pinned against Supplementary Table `tab:pipeline-metrics`, whose
"mean WM intensity (scale only)" row gives 17.13 / 15.62 / 8.32 for the original,
intermediate and final pipelines. Measuring a WM proxy (mean of the top 20% of in-brain
voxels) on every candidate volume in the tree gives:

  original      17.13   old_age9f_template.nii.gz        17.41   ratio 1.016
  intermediate  15.62   age9male_old_pipeline.nii.gz     15.81   ratio 1.012
  final          8.32   pipeline2.nii.gz                  8.53   ratio 1.025

The three ratios agree to within 1.3% of each other, which is the signature of a constant
multiplicative bias in the crude proxy rather than three coincidences; no other volume in
the tree lands near any of the three targets. Note that the RELEASED age-nine templates
are NOT the "final" column here (they measure 7.59 female / 6.92 male): the ablation was a
separate build, which is worth knowing before anyone tries to reuse these numbers.

The file naming is actively misleading -- `age9male_old_pipeline.nii.gz` is the
INTERMEDIATE pipeline, not the original. The intensity measurement is the authority.

Ages: the ablation is at age nine. The age-11-female rebuild does not enter this figure.
"""
import sys
import numpy as np, nibabel as nib
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, "/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save
from figs_brain import planes_mm, canonical, window, brain_extent_mm
set_style()

ROOT = "/path/to/cast-project"
PANELS = [
    ("Original pipeline",
     f"{ROOT}/07_Results_and_Analysis/mriqc_result/subject_folder/old/old_age9f_template.nii.gz", 17.13),
    ("Intermediate pipeline\n(preprocessing improvements only)",
     f"{ROOT}/07_Results_and_Analysis/mriqc_result/subject_folder/age9m/age9male_old_pipeline.nii.gz", 15.62),
    ("Final pipeline\n(preprocessing + registration)",
     f"{ROOT}/07_Results_and_Analysis/mriqc_result/subject_folder/pipeline2.nii.gz", 8.32),
]


def wm_proxy(vol):
    nz = vol[vol > 0.01 * vol.max()]
    return nz[nz >= np.percentile(nz, 80)].mean()


fig, axes = plt.subplots(1, 3, figsize=(9.6, 4.4))
report = []
for ax, (label, path, expected) in zip(axes, PANELS):
    im = nib.load(path)
    raw_codes = nib.aff2axcodes(im.affine)
    # Reorient to canonical RAS before slicing. Two of these three volumes are LIA-
    # ordered and one is LAS, so index-based slicing picks different anatomical planes
    # and flips the superior-inferior direction; and they mix 1.0 and 0.8 mm voxels, so
    # voxel-space rendering would draw the 0.8 mm volume ~25% larger for no anatomical
    # reason. planes_mm handles both and crops each panel to the same 180 mm box.
    vol = canonical(im).get_fdata()
    sl, ext = planes_mm(im)["axial"]
    lo, hi = window(vol)
    ax.imshow(sl, cmap="gray", origin="lower", extent=ext, aspect="equal",
              vmin=lo, vmax=hi, interpolation="nearest")
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_title(label, fontsize=8.5)
    zooms = im.header.get_zooms()[:3]
    report.append((label.split("\n")[0], path.split("/")[-1], im.shape, zooms[0],
                   raw_codes, wm_proxy(vol), expected,
                   np.round(brain_extent_mm(vol, canonical(im).header.get_zooms()[:3]), 1)))

# one scale bar, leftmost panel, since all three are now on a true millimetre scale
axes[0].plot([-82, -32], [-80, -80], color="white", lw=2.0, solid_capstyle="butt")
axes[0].text(-57, -75, "50 mm", color="white", ha="center", va="bottom", fontsize=6.5)

fig.suptitle("Pipeline ablation at age nine: successive preprocessing and registration refinements",
             fontsize=9.5, fontweight="bold")
fig.text(0.5, 0.055,
         "Intensity scale differs by construction between columns (mean WM 17.1 / 15.6 / 8.3), so "
         "the panels are windowed\nindividually and no intensity-based metric is comparable across "
         "them; see Supplementary Table 4.",
         ha="center", fontsize=6.5, color="0.35")
fig.tight_layout(rect=[0, 0.09, 1, 0.94])
save(fig, "figures_final/compare_pipelines")

print("=== pipeline ablation panels ===")
print(f"{'panel':<24}{'file':<32}{'shape':<18}{'mm':>5}{'axes':>7}{'WM':>8}{'table':>8}{'ratio':>7}")
for label, fn, shape, mm, codes, meas, exp, ext in report:
    print(f"{label:<24}{fn:<32}{str(shape):<18}{mm:>5.1f}{''.join(codes):>7}"
          f"{meas:>8.2f}{exp:>8.2f}{meas/exp:>7.3f}")
print()
print("brain extent in mm (canonical R-L, P-A, I-S) -- these are now drawn to true scale:")
for label, fn, shape, mm, codes, meas, exp, ext in report:
    print(f"  {label:<24}{ext}")
