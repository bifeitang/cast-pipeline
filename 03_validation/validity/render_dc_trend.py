#!/usr/bin/env python3
"""Reproduce Dong et al. (2020) Fig.3-left from OUR deformation-cost CSV:
deformation cost vs age difference (subject - template), with binned median +
smooth fit. Tests whether OUR data shows their rising trend. (Spoiler: flat.)"""
import csv, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = "/path/to/cast-project/07_Results_and_Analysis"
rows = [r for r in csv.DictReader(open(f"{D}/DeformationAnalysis/test_set_dc_metrics_merged.csv"))
        if float(r["normalized_warp_value"]) < 2]        # drop 2 broken rows
ad = np.array([float(r["subject_age"]) - float(r["template_age"]) for r in rows])
raw = np.array([float(r["mean_disp_mm"]) for r in rows])
norm = np.array([float(r["normalized_warp_value"]) for r in rows])
sex = np.array([r["template_sex"] for r in rows])

def panel(ax, y, ylab, title):
    ax.scatter(ad, y, s=5, c="steelblue", alpha=0.22, edgecolors="none")
    # binned median +/- IQR
    edges = np.arange(-9, 17, 2)
    cx, med, q1, q3 = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (ad >= lo) & (ad < hi)
        if s.sum() > 5:
            cx.append((lo+hi)/2); med.append(np.median(y[s]))
            q1.append(np.percentile(y[s],25)); q3.append(np.percentile(y[s],75))
    cx=np.array(cx)
    ax.fill_between(cx, q1, q3, color="navy", alpha=0.12, label="IQR")
    ax.plot(cx, med, "-o", color="navy", lw=2.2, ms=5, label="binned median")
    # quadratic fit (Dong used GAMLSS; quadratic captures any U-shape)
    c = np.polyfit(ad, y, 2); xs = np.linspace(ad.min(), ad.max(), 100)
    ax.plot(xs, np.polyval(c, xs), "--", color="C3", lw=2, label="quadratic fit")
    r = np.corrcoef(np.abs(ad), y)[0,1]
    ax.axvline(0, color="green", ls=":", lw=1)
    ax.set_xlabel("age difference: subject − template (years)")
    ax.set_ylabel(ylab); ax.set_title(f"{title}\ncorr(|age-diff|, cost) = {r:+.3f}  (≈ 0 → no trend)", fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.2)

fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5))
panel(a1, raw,  "mean displacement (mm)", "Raw SyN deformation cost")
panel(a2, norm, "normalized warp (disp / template ICV)", "Normalized (as in our CSV)")
fig.suptitle("Our deformation cost vs age difference (n=3,926, ages 5–22 → templates 6–14)\n"
             "Dong 2020 Fig.3 shows a rising trend here — ours is FLAT (post-affine SyN residual, size-normalized)",
             fontsize=11)
fig.tight_layout(rect=[0,0,1,0.93])
out = f"{D}/deformation_cost_trend/our_dc_vs_agediff.png"
import os; os.makedirs(f"{D}/deformation_cost_trend", exist_ok=True)
fig.savefig(out, dpi=150); print("wrote", out)
