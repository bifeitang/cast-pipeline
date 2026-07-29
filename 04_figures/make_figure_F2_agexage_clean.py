"""F2: deformation-cost age trend on the CSF-normalised INTENSITY registrations.

REBUILT 2026-07-28. The published version of this figure was computed from registrations
that put a BINARY BRAIN MASK against a greyscale template -- an input-selection error, not
a design choice (04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28.md). CC has
zero local variance inside a binary mask, so the optimiser matched an outline while SyN
regularisation drove the interior; the resulting 3.08 -> 3.63 mm trend was optimiser drift
across an under-constrained problem. All 5,104 registrations were rerun on the correct
subj_<EID>_csfNorm_rc.nii.gz intensity images.

WHAT CHANGED, AND WHAT DID NOT
    displacement       3.08 -> 2.40 mm matched, 3.63 -> 2.43 mm mismatched
    slope              +0.10 -> +0.025 mm/yr
    between-subject SD 3.41 -> 0.43 mm
    the conclusion     unchanged: the age effect is real, detectable, and negligible.

REPORT EFFECT SIZE, NOT SIGNIFICANCE. At n = 3,190 a 0.028 mm difference reaches p = 0.006,
and 0.028 mm is 3.5% of a 0.8 mm voxel. Every panel title here therefore carries the effect
in voxel units next to the p-value; a p-value alone at this n says only that the sample is
large. An earlier version of the companion analysis script printed "age effect RESOLVED"
for exactly this quantity.

AGE CONVENTION -- float, not integer bins. |dage| is computed from the subject's continuous
age, which is what the paper's own "|dage| < 0.5 y" wording describes and what the published
figure did. analyze_dc_intensity.py instead bins subject age to its integer directory bin
and so reports 2.399/2.425 and +0.024 mm/yr. Both are defensible and neither changes any
conclusion, but they are NOT interchangeable: on the mask-era data the float convention
reproduces the published 3.08/3.63/+0.10 exactly and the integer one gives 3.02/3.50/+0.067.
Keep this file, the manuscript text, and verify_claims.py on the float convention together.
"""
import csv, os, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs_style import set_style, save, panel_letter, CAST, MALE, FEMALE, OKABE
set_style()

VOX = 0.8   # acquisition voxel, mm -- the yardstick for "does this matter?"
CSV = os.path.join(HERE, "DeformationAnalysis",
                   "test_set_on_template_metrics_INTENSITY.csv")

rows = []
with open(CSV) as f:
    for x in csv.DictReader(f):
        if x["display_dataset"] != "My Template":
            continue
        rows.append(dict(age=float(x["Age"]), tage=float(x["template_age"]),
                         d=float(x["template_age"]) - float(x["Age"]),
                         cost=float(x["mean_disp_mm"]), sex=x["Sex_Text"].strip().lower()))
n_subj = len({(r["age"], r["sex"]) for r in rows})
print(f"CAST intensity registrations: {len(rows)}")
if len(rows) != 3190:
    print(f"  WARNING: expected 3,190 -- got {len(rows)}")

d = np.array([r["d"] for r in rows]); cost = np.array([r["cost"] for r in rows])
absd = np.abs(d)
SD = cost.std()

fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.3))

# --- (a) signed dage: binned median +/- IQR ------------------------------------------
ax = axes[0]
bins = np.arange(-6.5, 7.5, 1)
cen, med, q1, q3 = [], [], [], []
for lo, hi in zip(bins[:-1], bins[1:]):
    m = (d >= lo) & (d < hi)
    if m.sum() >= 10:
        cen.append((lo + hi) / 2); med.append(np.median(cost[m]))
        q1.append(np.percentile(cost[m], 25)); q3.append(np.percentile(cost[m], 75))
cen = np.array(cen); med = np.array(med)
ax.fill_between(cen, q1, q3, color=CAST, alpha=0.18, lw=0)
ax.plot(cen, med, "-o", color=CAST, ms=4)
ax.axvline(0, color="0.5", ls=":", lw=0.9)
i0 = int(np.argmin(np.abs(cen)))
imin = int(np.argmin(med))
span = med.max() - med.min()
# The matched bin is NOT the minimum -- it is 0.025 mm above the bin at -3 y. The published
# version asserted "the matched-age template gave the lowest cost", which its own mask-era
# data also did not support (that minimum sat at +3 y). Mark both points rather than
# labelling only the one that flatters the hypothesis.
ax.annotate("matched", (0, med[i0]), textcoords="offset points", xytext=(4, 8),
            fontsize=7, color="0.3")
ax.plot([cen[imin]], [med[imin]], "o", ms=8, mfc="none", mec=OKABE["vermillion"], mew=1.2)
ax.annotate(f"minimum ({cen[imin]:+.0f} y)", (cen[imin], med[imin]),
            textcoords="offset points", xytext=(-2, -16), fontsize=6.5,
            color=OKABE["vermillion"], ha="center")
# A voxel-tall scale bar makes the flatness legible instead of hidden by autoscaling.
lo_y = min(q1)
ax.errorbar([cen.max() - 0.4], [lo_y + VOX / 2], yerr=VOX / 2, color="0.35",
            capsize=2.5, lw=1.0)
ax.text(cen.max() - 0.75, lo_y + VOX / 2, "one\nvoxel", fontsize=6, color="0.35",
        ha="right", va="center")
ax.set_xlabel("template age − subject age (years)")
ax.set_ylabel("deformation cost (mean displacement, mm)")
ax.set_title(f"Flat across ±6 y of mismatch:\nwhole span {span:.3f} mm "
             f"({span / VOX * 100:.0f}% of a voxel, median ± IQR)", fontsize=8.5)
panel_letter(ax, "a")

# --- (b) |dage| regression -------------------------------------------------------------
ax = axes[1]
lr = stats.linregress(absd, cost)
xs = np.linspace(0, absd.max(), 50)
rng = np.random.default_rng(0)   # reproducible jitter
ax.scatter(absd + rng.uniform(-0.12, 0.12, len(absd)), cost, s=4, color=CAST,
           alpha=0.10, edgecolors="none")
ax.plot(xs, lr.intercept + lr.slope * xs, "-", color="black", lw=1.6)
cen2, med2 = [], []
for k in range(0, 7):
    m = (absd >= k - 0.5) & (absd < k + 0.5)
    if m.sum() >= 10:
        cen2.append(k); med2.append(np.median(cost[m]))
ax.plot(cen2, med2, "D", color=OKABE["orange"], ms=5, label="binned median")
ax.set_xlabel("age mismatch |Δage| (years)")
ax.set_ylabel("deformation cost (mm)")
ax.set_title(f"Detectable, not material\nslope={lr.slope:+.3f} mm/yr "
             f"({abs(lr.slope) / VOX * 100:.0f}% of a voxel/yr), p={lr.pvalue:.1e}",
             fontsize=8.5)
ax.legend(loc="upper left")
panel_letter(ax, "b")

# --- (c) by sex ------------------------------------------------------------------------
ax = axes[2]
stat = {}
for sex, c in [("male", MALE), ("female", FEMALE)]:
    rs = [r for r in rows if r["sex"] == sex]
    dd = np.array([r["d"] for r in rs]); cc = np.array([r["cost"] for r in rs])
    cen3, med3 = [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (dd >= lo) & (dd < hi)
        if m.sum() >= 8:
            cen3.append((lo + hi) / 2); med3.append(np.median(cc[m]))
    ax.plot(cen3, med3, "-o", color=c, ms=3.5, label=sex)
    ad = np.abs(dd)
    mt, mm = cc[ad < 0.5], cc[ad >= 2]
    stat[sex] = dict(p_mw=stats.mannwhitneyu(mt, mm, alternative="less")[1],
                     slope=stats.linregress(ad, cc).slope,
                     p_slope=stats.linregress(ad, cc).pvalue,
                     eff=np.median(mm) - np.median(mt),
                     span=max(med3) - min(med3))
ax.axvline(0, color="0.5", ls=":", lw=0.9)
ax.set_xlabel("template age − subject age (years)")
ax.set_ylabel("deformation cost (mm)")
ax.set_title(f"Neither sex varies by a third of a voxel\n"
             f"span M {stat['male']['span'] / VOX * 100:.0f}%, "
             f"F {stat['female']['span'] / VOX * 100:.0f}% of a voxel "
             f"(outer bins n<20)", fontsize=8.5)
ax.legend(loc="upper center")
panel_letter(ax, "c")

fig.suptitle("Deformation cost on CSF-normalised intensity images: cost rises weakly with "
             "age mismatch, but the entire trend spans a sixth of a voxel", fontsize=9.5)
fig.tight_layout(rect=[0, 0, 1, 0.94])
save(fig, os.path.join(HERE, "figures_final", "F2_agexage_clean"))

near = np.array([r["cost"] for r in rows if abs(r["d"]) < 0.5])
far = np.array([r["cost"] for r in rows if abs(r["d"]) >= 2])
eff = np.median(far) - np.median(near)
print("\n=== deformation cost, intensity rerun (float-age convention) ===")
print(f"registrations            {len(rows)}")
print(f"between-subject SD       {SD:.4f} mm      (mask era 3.409)")
print(f"matched  |d|<0.5         {np.median(near):.4f} mm  n={len(near)}   (mask era 3.08)")
print(f"mismatch |d|>=2          {np.median(far):.4f} mm  n={len(far)}   (mask era 3.63)")
print(f"effect                   {eff:+.4f} mm = {abs(eff) / VOX * 100:.1f}% of a voxel "
      f"= {abs(eff) / SD:.2f} SD   (mask era +0.55 mm, 0.16 SD)")
print(f"                         Mann-Whitney p = {stats.mannwhitneyu(near, far)[1]:.3g}")
print(f"slope                    {lr.slope:+.4f} mm/yr  r={lr.rvalue:+.3f} "
      f"p={lr.pvalue:.3g}   (mask era +0.10, r=0.04, p=0.015)")
print(f"4 y of mismatch          {lr.slope * 4:.4f} mm = {abs(lr.slope) * 4 / SD:.2f} SD")
print(f"signed-curve minimum     {cen[imin]:+.0f} y, NOT the matched bin "
      f"({med[imin]:.4f} vs {med[i0]:.4f} mm) -- the published 'matched-age template gave "
      f"the lowest cost' held on neither generation")
print(f"signed-curve span        {span:.4f} mm = {span / VOX * 100:.0f}% of a voxel")
for sex in ("male", "female"):
    s = stat[sex]
    print(f"{sex:<8} matched-vs-mismatch {s['eff']:+.4f} mm p={s['p_mw']:.3g}; "
          f"slope {s['slope']:+.4f} p={s['p_slope']:.3g}; "
          f"span {s['span']:.4f} mm ({s['span'] / VOX * 100:.0f}% voxel)")
print("\nSignificance at n=3,190 is a function of n. Report the voxel fraction.")
