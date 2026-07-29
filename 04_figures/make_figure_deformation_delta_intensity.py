#!/usr/bin/env python3
"""Sex-matched advantage Delta at the age-nine templates, on the intensity rerun.

Replaces make_figure_deformation_delta.py, which reads
DeformationAnalysis/test_set_on_template_metrics_with_sex.csv -- a mask-era table whose
moving images are *_processed_centered.nii.gz, i.e. BINARY BRAIN MASKS registered onto
gray-scale templates (04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28.md).
Neither handoff listed this figure as a consumer of the bad data; it is one. Its published
"73% of males / 30% of females" split was measured on registrations whose interior carried
no metric gradient at all.

Delta_i = D(opposite-sex age-9 template) - D(same-sex age-9 template), on the ICV-normalised
mean displacement (norm_mean_disp = mean_disp_mm / L_mm). Positive Delta = the sex-matched
template is cheaper.

ICV ONLY. The mask-era run carried two normalisation schemes, icv and diag; the rerun
carries one (norm_type=template_icv, arithmetically identical to the old icv -- both are
mean_disp_mm / L_mm). The published panel (b) plotted icv and diag side by side and its
caption compares their magnitudes. That comparison cannot be regenerated, and pairing a
mask-era diag panel with an intensity-era icv panel would mix two generations inside one
figure, so only the icv series is produced here and the caption must drop the diag claim.

OUTPUTS  figures_final/gender_lollipop.{pdf,png}   waterfall by sex
         figures_final/age_effect.{pdf,png}        age-wise Delta by sex
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs_style import set_style, save, MALE, FEMALE
set_style()

CSV = os.path.join(HERE, "DeformationAnalysis",
                   "test_set_on_template_metrics_INTENSITY.csv")
N_BOOT = 5000
BOOT = np.random.default_rng(11)      # seeded: the CI band must be reproducible

df = pd.read_csv(CSV)
a9 = df[(df.arm == "cast") & (df.template_age == 9)].copy()
if len(a9) != 638:
    print(f"WARNING: expected 638 age-nine registrations, got {len(a9)}")

# One row per subject per template sex -> wide, then signed difference by subject sex.
w = a9.pivot_table(index=["subject_id", "Sex_Text", "age_dir"],
                   columns="template_sex", values="norm_mean_disp").reset_index()
missing = w[["male", "female"]].isna().any(axis=1).sum()
if missing:
    sys.exit(f"FATAL: {missing} subjects lack one of the two age-nine templates")
w["delta"] = np.where(w.Sex_Text == "male", w.female - w.male, w.male - w.female)
w = w.rename(columns={"age_dir": "age"})
print(f"subjects with a usable Delta: {len(w)}  "
      f"(male {(w.Sex_Text == 'male').sum()}, female {(w.Sex_Text == 'female').sum()})\n")

# ---------------------------------------------------------------- waterfall -----------
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6))
for ax, (sex, col) in zip(axes, [("male", MALE), ("female", FEMALE)]):
    s = w[w.Sex_Text == sex].sort_values("delta", ascending=False)
    y = s.delta.values
    x = np.arange(len(y))
    pos = y > 0
    ax.vlines(x[pos], 0, y[pos], color=col, lw=0.9, alpha=0.85)
    ax.vlines(x[~pos], 0, y[~pos], color="0.72", lw=0.9)
    ax.plot(x[pos], y[pos], "o", ms=2.2, color=col)
    ax.plot(x[~pos], y[~pos], "o", ms=2.2, color="0.72")
    ax.axhline(0, color="0.35", ls="--", lw=1)
    ax.set_title(f"{sex}  |  matched better in {100 * pos.mean():.0f}%  |  "
                 f"median $\\Delta$={np.median(y):+.4f}", fontsize=8.5)
    ax.set_xlabel(f"held-out subjects, sorted by $\\Delta$  (n={len(y)})")
    ax.set_ylabel("$\\Delta$ normalized mean displacement\n(mismatched $-$ matched)",
                  fontsize=7.5)
fig.suptitle("Sex-matched advantage at the age-nine template, CSF-normalised intensity "
             "images: positive $\\Delta$ = matched template cheaper (ICV normalisation)",
             fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, os.path.join(HERE, "figures_final", "gender_lollipop"))

print("=== waterfall (icv) ===")
for sex in ("male", "female"):
    s = w[w.Sex_Text == sex]
    print(f"  {sex:<7} n={len(s):>4}  median={s.delta.median():+.5f}  "
          f"mean={s.delta.mean():+.5f}  matched-better={100 * (s.delta > 0).mean():.1f}%")

# ---------------------------------------------------------------- age-wise ------------
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=True)
for ax, (sex, col) in zip(axes, [("male", MALE), ("female", FEMALE)]):
    s = w[w.Sex_Text == sex]
    ages = sorted(s.age.unique())
    mu, lo, hi, ns = [], [], [], []
    for a in ages:
        v = s[s.age == a].delta.values
        bs = BOOT.choice(v, (N_BOOT, len(v)), replace=True).mean(axis=1)
        mu.append(v.mean()); lo.append(np.percentile(bs, 2.5))
        hi.append(np.percentile(bs, 97.5)); ns.append(len(v))
    ax.fill_between(ages, lo, hi, color=col, alpha=0.20, lw=0)
    ax.plot(ages, mu, "-o", color=col, ms=4.5, lw=1.4)
    for a, m, n in zip(ages, mu, ns):
        ax.annotate(f"n={n}", (a, m), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=5.6, color="0.35")
    ax.axhline(0, color="0.35", ls="--", lw=1)
    ax.set_title(f"{sex}  |  ICV normalisation", fontsize=8.5)
    ax.set_xlabel("subject age (years)")
axes[0].set_ylabel("$\\Delta$ (mismatched $-$ matched)", fontsize=7.5)
fig.suptitle("Age-wise sex-matched advantage: small throughout and not systematic in age",
             fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, os.path.join(HERE, "figures_final", "age_effect"))

print("\n=== age-wise Delta (icv) ===")
print(f"{'sex':<8}{'age':>4}{'n':>5}{'mean':>12}{'median':>12}{'matched%':>10}")
for sex in ("male", "female"):
    s = w[w.Sex_Text == sex]
    for a in sorted(s.age.unique()):
        v = s[s.age == a].delta.values
        print(f"{sex:<8}{a:>4}{len(v):>5}{v.mean():>+12.6f}{np.median(v):>+12.6f}"
              f"{100 * (v > 0).mean():>9.1f}%")
mx = {sex: max(sorted(w[w.Sex_Text == sex].age.unique()),
               key=lambda a: w[(w.Sex_Text == sex) & (w.age == a)].delta.mean())
      for sex in ("male", "female")}
print(f"\npeak mean Delta: male at age {mx['male']}, female at age {mx['female']} "
      f"-- template age is 9")
print("\nmask-era published: male 73% matched-better (n=204, median +0.003); "
      "female 30% (n=115, median -0.002)")
