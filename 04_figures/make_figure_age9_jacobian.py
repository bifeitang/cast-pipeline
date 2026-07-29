"""Supplementary: warp regularity for held-out subjects registered to the age-nine templates.

REBUILT 2026-07-28 on the intensity rerun. The published version of this figure was computed
from registrations of a BINARY BRAIN MASK onto a greyscale template -- an input-selection
error (04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28.md). Its headline
"mean log J = -0.108, a global compression of roughly 10%" was a property of an ill-posed
optimisation, not of pediatric anatomy.

Population: the 319-subject held-out test set, each registered to BOTH age-nine templates
(male and female) = 638 registrations.

WHAT THE CORRECTED DATA SHOWS -- the story improves substantially
  1. Pooled mean log J is -0.011, not -0.108. There is no global 10% compression.
  2. The two age-nine templates are offset from each other by a constant +0.113 in mean
     log J at every subject age. That offset is not a warp property: the age-9 male template
     is 1558.3 ml ICV against the female's 1389.0 ml, a ratio whose log is +0.1150 -- within
     0.002 of the measured offset. The composed Jacobian is reading template size, exactly
     as it must. Do NOT report the pooled value as if it described one population; it is the
     mean of two curves separated by a known constant, and its crossing of zero near the
     template age is an artefact of that averaging, not a finding.
  3. Within each template, mean log J rises with subject age by about +0.08 across ages
     5-12: younger subjects are compressed onto a nine-year-old template and older ones
     expanded. That is what anatomy predicts, and the mask-era data could not show it --
     there the curve was flat at -0.108 because the optimiser was matching an outline.
  4. Within-warp SD of log J is 0.227-0.251, tighter than the mask era's 0.342-0.417, and
     nearly flat in subject age. Its minimum is at age 10.
  5. No non-diffeomorphic voxels anywhere.

JACOBIAN CONVENTION -- DO NOT CALL THIS LIKE-FOR-LIKE WITH SEC. 2.7
  These Jacobians come from the COMPOSED affine o SyN field. cal_deformation_cost.sh builds
  a separate composed field for the Jacobian whenever -disp-component syn is in force (its
  lines 579-587), so the displacement columns are SyN-only but the Jacobian columns are not.
  The affine carries scale and shear, so composed and SyN-only Jacobians are different
  quantities rather than rescalings. The rerun therefore fixed this figure's mask->intensity
  axis and NOT its composed->SyN-only axis: it still cannot be compared directly with the
  SyN-only construction warps (-0.032) or the tissue Jacobians (-0.03/-0.03/+0.05). The run
  kept only metrics.txt, so a SyN-only Jacobian cannot be recovered without re-registering.

Data: DeformationAnalysis/tables/age9_jacobian_summary_by_age_gender_INTENSITY.csv, written
by build_dc_intensity_tables.py from the 638 age-nine metrics.txt files.
"""
import csv, json, os, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs_style import set_style, save, panel_letter, MALE, FEMALE, OKABE
set_style()

# The male/female offset in mean log J should equal log(ICV_male / ICV_female) for the two
# age-nine templates, because the composed Jacobian carries the affine's scale. Derive it
# from the template morphometry rather than hard-coding, so the claim stays checkable.
_MORPH = {r["name"]: r for r in
          (json.loads(l) for l in open(os.path.join(HERE, "morphometry",
                                                    "template_morphometry.jsonl"))
           if l.strip())}
ICV_LOG = float(np.log(_MORPH["age9_male"]["icv_ml"] / _MORPH["age9_female"]["icv_ml"]))

SRC = os.path.join(HERE, "DeformationAnalysis", "tables",
                   "age9_jacobian_summary_by_age_gender_INTENSITY.csv")
rows = list(csv.DictReader(open(SRC)))
for r in rows:
    r["Age"] = int(r["Age"]); r["n"] = int(r["n"])
    for k in ("mean_mean_logJ", "ci_mean_logJ_low", "ci_mean_logJ_high",
              "mean_std_logJ", "ci_std_logJ_low", "ci_std_logJ_high",
              "mean_pct_non_diff", "rate_any_non_diff"):
        r[k] = float(r[k])

AGES = sorted({r["Age"] for r in rows})
n_tot = sum(r["n"] for r in rows)
W = [r["n"] for r in rows]
pooled_mean = np.average([r["mean_mean_logJ"] for r in rows], weights=W)
pooled_sd = np.average([r["mean_std_logJ"] for r in rows], weights=W)
print(f"registrations: {n_tot}  pooled mean logJ {pooled_mean:+.4f}  "
      f"pooled SD logJ {pooled_sd:.4f}")
if n_tot != 638:
    print(f"  WARNING: expected 638 registrations, got {n_tot}")

fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.3))


def series(ax, key, lo, hi):
    for sex, col, dx, lbl in (("male", MALE, -0.10, "Age-9 male template"),
                              ("female", FEMALE, +0.10, "Age-9 female template")):
        sub = sorted([r for r in rows if r["template_gender"] == sex],
                     key=lambda r: r["Age"])
        xs = np.array([r["Age"] for r in sub], dtype=float) + dx
        ys = np.array([r[key] for r in sub])
        err = np.vstack([ys - np.array([r[lo] for r in sub]),
                         np.array([r[hi] for r in sub]) - ys])
        ax.errorbar(xs, ys, yerr=err, fmt="o-", ms=3.2, lw=1.0, elinewidth=0.9,
                    capsize=1.8, color=col, label=lbl)


# (a) mean log J -- two parallel curves whose separation is the templates' ICV ratio
ax = axes[0]
series(ax, "mean_mean_logJ", "ci_mean_logJ_low", "ci_mean_logJ_high")
ax.axhline(0, color="0.45", ls=":", lw=1)
ax.axvline(9, color="0.75", ls=":", lw=1)
ax.text(9.05, ax.get_ylim()[0], " template age", fontsize=6, color="0.55", va="bottom")
ax.text(0.02, 0.955, "$J=1$ (volume preserving)", transform=ax.transAxes,
        ha="left", va="top", fontsize=6, color="0.45")
# The gap between the two series is template size, not warp behaviour. Say so on the figure.
gap = np.mean([r["mean_mean_logJ"] for r in rows if r["template_gender"] == "female"]) - \
      np.mean([r["mean_mean_logJ"] for r in rows if r["template_gender"] == "male"])
ax.annotate("", xy=(6, np.mean([r["mean_mean_logJ"] for r in rows
                                if r["template_gender"] == "female"])),
            xytext=(6, np.mean([r["mean_mean_logJ"] for r in rows
                                if r["template_gender"] == "male"])),
            arrowprops=dict(arrowstyle="<->", color="0.35", lw=0.8))
ax.text(6.2, -0.045, f"{gap:+.3f}\n= log(ICV$_M$/ICV$_F$)\n= {ICV_LOG:+.3f}", fontsize=5.8,
        color="0.35", va="center", ha="left")
ax.set_xlabel("Subject age (years)"); ax.set_ylabel("mean $\\log J$")
ax.set_xticks(AGES)
ax.set_title("Each template's curve rises with subject age;\nthe gap between them is their "
             "size ratio", fontsize=8.5)
ax.legend(fontsize=6.2, loc="lower right"); panel_letter(ax, "a")

# (b) within-warp SD -- narrow band, no degradation with mismatch
ax = axes[1]
series(ax, "mean_std_logJ", "ci_std_logJ_low", "ci_std_logJ_high")
allsd = [r["mean_std_logJ"] for r in rows]
lo_age = min(AGES, key=lambda a: np.mean([r["mean_std_logJ"] for r in rows
                                          if r["Age"] == a]))
ax.axvline(9, color="0.75", ls=":", lw=1)
ax.text(9, ax.get_ylim()[1], " template age", fontsize=6, color="0.55", va="top")
ax.set_xlabel("Subject age (years)"); ax.set_ylabel("within-warp SD of $\\log J$")
ax.set_xticks(AGES)
ax.set_title(f"No degradation with age mismatch\n(range {min(allsd):.3f}–{max(allsd):.3f}; "
             f"minimum at age {lo_age})", fontsize=8.5)
ax.legend(fontsize=6.2, loc="lower left"); panel_letter(ax, "b")

fig.suptitle("Warp regularity for held-out subjects registered to the age-nine templates "
             f"({n_tot} registrations, composed affine-then-SyN Jacobian)", fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.91])
save(fig, os.path.join(HERE, "figures_final", "F_age9_jacobian"))

print("\nsubject age   mean log J (M / F)      SD log J (M / F)")
for a in AGES:
    g = {r["template_gender"]: r for r in rows if r["Age"] == a}
    print(f"   {a:>2}         {g['male']['mean_mean_logJ']:+.4f} / "
          f"{g['female']['mean_mean_logJ']:+.4f}      "
          f"{g['male']['mean_std_logJ']:.4f} / {g['female']['mean_std_logJ']:.4f}")
for sex in ("male", "female"):
    s = sorted([r for r in rows if r["template_gender"] == sex], key=lambda r: r["Age"])
    print(f"{sex:>7} template: mean log J {s[0]['mean_mean_logJ']:+.4f} (age {s[0]['Age']}) "
          f"-> {s[-1]['mean_mean_logJ']:+.4f} (age {s[-1]['Age']}), "
          f"rise {s[-1]['mean_mean_logJ'] - s[0]['mean_mean_logJ']:+.4f}")
print(f"\nfemale - male offset {gap:+.4f}  vs  log(ICV_M/ICV_F) {ICV_LOG:+.4f}  "
      f"(agree to {abs(gap - ICV_LOG):.4f}) -- the gap is template size, not warp behaviour")
print(f"minimum within-warp SD at subject age {lo_age}")
print(f"non-diffeomorphic: max per-stratum mean = "
      f"{max(r['mean_pct_non_diff'] for r in rows):g}")
print("\nCOMPOSED affine o SyN Jacobian -- NOT comparable with the SyN-only -0.032 of the "
      "construction warps.")
