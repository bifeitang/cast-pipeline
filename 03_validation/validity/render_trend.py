#!/usr/bin/env python3
"""Gray-white interface error vs template mismatch (surface metric).
Parametric: render_trend.py [results.jsonl] [out.png] [REG_LABEL].
Titles are data-driven (report the actual cohort-mean spread) -- no spin."""
import sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = "/path/to/cast-project/07_Results_and_Analysis/validity_heatmap_pilot"
jsonl = sys.argv[1] if len(sys.argv) > 1 else f"{D}/trend_results.jsonl"
out = sys.argv[2] if len(sys.argv) > 2 else f"{D}/age6_female_validity_TREND.png"
REG = sys.argv[3] if len(sys.argv) > 3 else "AFFINE"

rows = [json.loads(l) for l in open(jsonl) if l.strip()]
subs = sorted({r["subject_id"] for r in rows})
colors = dict(zip(subs, ["C0", "C1", "C2"]))
sage_of = {s: next(r["subject_age"] for r in rows if r["subject_id"] == s) for s in subs}

def series(sid, sex, key):
    pts = sorted([(r["template_age"], r[key]) for r in rows
                  if r["subject_id"] == sid and r["template_sex"] == sex])
    return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])

fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 4.8))

# Panel A: AGE sweep (female templates)
fem_ages = sorted({r["template_age"] for r in rows if r["template_sex"] == "female"})
for sid in subs:
    ages, vals = series(sid, "female", "full_median_mm")
    axA.plot(ages, vals, "-o", color=colors[sid], alpha=0.6, ms=4,
             label=f"{sid[:10]} (age {sage_of[sid]:.1f})")
    axA.axvline(sage_of[sid], color=colors[sid], ls=":", lw=0.8, alpha=0.5)
cm = [np.mean([r["full_median_mm"] for r in rows
               if r["template_sex"] == "female" and r["template_age"] == a]) for a in fem_ages]
axA.plot(fem_ages, cm, "-", color="k", lw=2.4, label="cohort mean")
spread = max(cm) - min(cm)
min_age = fem_ages[int(np.argmin(cm))]
axA.set_xlabel("template age (years)"); axA.set_ylabel("median gray–white distance (mm)")
axA.set_title(f"Age sweep ({REG}): cohort-mean spread {spread:.2f} mm"
              + (f", min at age {min_age}" if spread > 0.15 else "  (~flat)"), fontsize=10)
axA.axvspan(6, 7, color="green", alpha=0.06)
axA.legend(fontsize=7, loc="best"); axA.grid(alpha=0.2)

# Panel B: SEX contrast at age 6 (paired)
x = np.arange(len(subs))
femv = [next(r["full_median_mm"] for r in rows if r["subject_id"] == s
             and r["template_sex"] == "female" and r["template_age"] == 6) for s in subs]
malev = [next(r["full_median_mm"] for r in rows if r["subject_id"] == s
              and r["template_sex"] == "male" and r["template_age"] == 6) for s in subs]
axB.bar(x - 0.18, femv, 0.36, label="age6 FEMALE (matched sex)", color="C0")
axB.bar(x + 0.18, malev, 0.36, label="age6 MALE (sex mismatch)", color="C3")
for i in range(len(subs)):
    axB.annotate(f"{malev[i]-femv[i]:+.2f}", (x[i] + 0.18, malev[i]), ha="center",
                 va="bottom", fontsize=8, color="C3")
axB.set_xticks(x)
axB.set_xticklabels([f"{s[:8]}\n({sage_of[s]:.1f}y)" for s in subs], fontsize=8)
axB.set_ylabel("median gray–white distance (mm)")
axB.set_title(f"Sex mismatch at age 6 ({REG})", fontsize=10)
axB.legend(fontsize=8); axB.grid(alpha=0.2, axis="y")
axB.set_ylim(0, max(malev) * 1.25)

fig.suptitle(f"Gray–white interface error vs template mismatch (surface, {REG}) — "
             f"age-6 girls (6.1–7.0 y), n=3 pilot", fontsize=10.5)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(out, dpi=150)
print("wrote", out)
print(f"\n[{REG}] cohort-mean by template age (female):")
for a, v in zip(fem_ages, cm):
    print(f"  age {a:>2}: {v:.3f} mm")
print(f"  spread {spread:.3f} mm; sex penalty (male-female age6): "
      f"{', '.join(f'{m-f:+.2f}' for m, f in zip(malev, femv))}")
