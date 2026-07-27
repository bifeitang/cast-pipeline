"""Methods Sec. 2.7: Jacobian regularity of the template-construction warps.

Every subject-to-template warp used to BUILD the 28 CAST templates (n=1,272 across
14 ages x 2 sexes), not a held-out subset. Shows (a) the small, uniform, sex-independent
global contraction, (b) the within-warp spread of local volume change, and (c) that the
deformation never approaches the folding boundary -- 0 of 1,272 warps contained a single
non-diffeomorphic voxel.

Data: DeformationAnalysis/jacobian_construction_2026-07-22/per_warp_results.tsv,
pulled from carya /project/contreras-vidal/Yang/JACOBIAN_2026-07-22/out/*/results.tsv
(job cast-jac 7757880). Columns: stratum, subject, n_vox, mean_logJ, std_logJ, pct_nondiffeo.

Note: the age-9 male stratum is built from its 92 `_rc` warps (the stratum has 129 forward
warps, 37 of which are superseded); its between-warp spread is therefore much tighter than
the other strata. This is a property of the warp set, not of the registration.
"""
import csv, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, "/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE, OKABE
set_style()

SRC = "DeformationAnalysis/jacobian_construction_2026-07-22/per_warp_results.tsv"
rows = list(csv.DictReader(open(SRC), delimiter="\t"))
for r in rows:
    r["age"] = int(r["stratum"].split("_")[0].replace("age", ""))
    r["sex"] = r["stratum"].split("_")[1]
    for k in ("n_vox", "mean_logJ", "std_logJ", "pct_nondiffeo"):
        r[k] = float(r[k])
print(f"construction warps: {len(rows)} across {len({r['stratum'] for r in rows})} strata")

AGES = sorted({r["age"] for r in rows})
pooled_mean = np.mean([r["mean_logJ"] for r in rows])
pooled_sd = np.mean([r["std_logJ"] for r in rows])
n_bad = sum(1 for r in rows if r["pct_nondiffeo"] > 0)

fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4))

# (a) per-stratum mean log J: small, uniform, sex-independent contraction
ax = axes[0]
for sex, col, dx in (("male", MALE, -0.12), ("female", FEMALE, +0.12)):
    xs, ys, es = [], [], []
    for a in AGES:
        v = np.array([r["mean_logJ"] for r in rows if r["age"] == a and r["sex"] == sex])
        if not len(v):
            continue
        xs.append(a + dx); ys.append(v.mean()); es.append(v.std())
    ax.errorbar(xs, ys, yerr=es, fmt="o", ms=3.2, lw=0, elinewidth=0.9,
                capsize=1.8, color=col, label=sex.capitalize())
ax.axhline(0, color="0.45", ls=":", lw=1)
ax.axhline(pooled_mean, color=OKABE["vermillion"], ls="--", lw=1)
ax.text(0.98, 0.06, f"pooled mean {pooled_mean:+.3f}", transform=ax.transAxes,
        ha="right", fontsize=6, color=OKABE["vermillion"])
ax.text(0.98, 0.93, "$J=1$ (volume preserving)", transform=ax.transAxes,
        ha="right", fontsize=6, color="0.45")
ax.set_xlabel("Template age (years)"); ax.set_ylabel("mean $\\log J$ per warp")
ax.set_xticks(AGES[::2])
ax.set_title("Mild global compression,\nuniform and sex-independent", fontsize=8.5)
ax.legend(fontsize=6.5, loc="lower left"); panel_letter(ax, "a")

# (b) within-warp SD of log J: local deformation magnitude
ax = axes[1]
for sex, col, dx in (("male", MALE, -0.12), ("female", FEMALE, +0.12)):
    xs, ys, es = [], [], []
    for a in AGES:
        v = np.array([r["std_logJ"] for r in rows if r["age"] == a and r["sex"] == sex])
        if not len(v):
            continue
        xs.append(a + dx); ys.append(v.mean()); es.append(v.std())
    ax.errorbar(xs, ys, yerr=es, fmt="o", ms=3.2, lw=0, elinewidth=0.9,
                capsize=1.8, color=col, label=sex.capitalize())
ax.axhline(pooled_sd, color=OKABE["vermillion"], ls="--", lw=1)
ax.text(0.98, 0.06, f"pooled {pooled_sd:.3f}", transform=ax.transAxes,
        ha="right", fontsize=6, color=OKABE["vermillion"])
ax.set_xlabel("Template age (years)"); ax.set_ylabel("within-warp SD of $\\log J$")
ax.set_xticks(AGES[::2])
ax.set_title("Local volume-change magnitude\nstable across the library", fontsize=8.5)
ax.legend(fontsize=6.5, loc="lower left"); panel_letter(ax, "b")

# (c) pooled voxelwise J density: voxel-weighted mixture of per-warp lognormals
ax = axes[2]
xs = np.linspace(1e-3, 2.5, 600)
mu = np.array([r["mean_logJ"] for r in rows])
sd = np.clip(np.array([r["std_logJ"] for r in rows]), 1e-3, None)
w = np.array([r["n_vox"] for r in rows]); w = w / w.sum()
dens = np.zeros_like(xs)
for m_, s_, w_ in zip(mu, sd, w):
    dens += w_ * (1.0 / (xs * s_ * np.sqrt(2 * np.pi))) * np.exp(-(np.log(xs) - m_) ** 2 / (2 * s_ ** 2))
trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
dens /= trapz(dens, xs)
ax.fill_between(xs, dens, color=OKABE["blue"], alpha=0.35, lw=0)
ax.plot(xs, dens, color=OKABE["blue"], lw=1.3)
ax.axvline(1.0, color="0.5", ls=":", lw=1)
ax.axvline(0.0, color=OKABE["vermillion"], lw=1.8)
ax.text(0.03, 0.92, "folding boundary\n$J\\leq0$", transform=ax.transAxes,
        color=OKABE["vermillion"], fontsize=6, va="top")
ax.text(1.03, 0.04, "$J=1$", transform=ax.get_xaxis_transform(), fontsize=6, color="0.4")
ax.text(0.97, 0.55, f"{n_bad} of {len(rows):,} warps\ncontain any $J\\leq0$",
        transform=ax.transAxes, ha="right", fontsize=6.5, color="0.25")
ax.set_xlim(0, 2.5); ax.set_xlabel("Jacobian determinant $J$"); ax.set_ylabel("voxel density")
ax.set_title("Deformation stays far from\nthe folding boundary", fontsize=8.5)
panel_letter(ax, "c")

fig.suptitle(f"Jacobian regularity of all {len(rows):,} template-construction warps "
             "(28 age $\\times$ sex strata)", fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, "figures_final/F_jacobian_construction")

print("\n=== construction-warp Jacobian summary ===")
print(f"  n warps            {len(rows):,}")
print(f"  mean log J         {pooled_mean:+.5f}")
print(f"  within-warp SD     {pooled_sd:.4f}  (range {min(r['std_logJ'] for r in rows):.4f}-{max(r['std_logJ'] for r in rows):.4f})")
print(f"  warps with J<=0    {n_bad}")
print("\n  per-stratum mean log J:")
for a in AGES:
    parts = []
    for sex in ("male", "female"):
        v = [r["mean_logJ"] for r in rows if r["age"] == a and r["sex"] == sex]
        if v:
            parts.append(f"{sex[0].upper()} {np.mean(v):+.4f} (n={len(v)})")
    print(f"    age {a:>2}  " + "   ".join(parts))
