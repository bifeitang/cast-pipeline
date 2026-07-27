"""BRAIN CAST vs NKI: the "winner" is an artifact of measurement direction (methods Fig. 9).

RECONSTRUCTED GENERATOR (2026-07-27). `assd_headtohead.png` was hand-made with no
generator in the repo. Provenance was pinned by reproducing every annotation exactly
from `refbench_0p8/assd_0p8_measures.jsonl` (carya, 2026-06-15; 288 rows = 144 subjects
x 2 references):

  published annotation      reproduced
  n = 144 held-out subjects 144 paired subjects           exact
  Forward  +0.029           median +0.0286                exact
  Reverse  -0.035           median -0.0348                exact
  Symmetric ASSD -0.005     median -0.0046                exact
  pooled -0.0046 mm         median of the symmetric diff  exact
  panel b, ages 5-10        -0.0138 / -0.0339 / +0.0012 /
                            -0.0019 / -0.0028 / -0.0377   exact

Table 3 in the manuscript comes from the same file and also reproduces to the digit
(BRAIN CAST 0.836/0.705, NKI 0.783/0.677, paired +0.0492 full / +0.0239 cortical,
reverse 128/144, ASSD -0.0046 mean-based / +0.0112 median-based).

Note the two different per-subject summaries in play, which are easy to confuse:
  cort_mean_mm / fwd_mean_cort_mm  mean distance over cortical boundary voxels  -> the FIGURE (+0.029)
  cort_median_mm                   median distance over the same voxels         -> the TABLE  (+0.024)
Both are one-directional template->subject; they are not inconsistent, they are
different summaries of the same distances. The figure uses the mean-based one.

Ages 5-10 only, so the age-11-female rebuild does not enter this figure at all.
"""
import json, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, "/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, CAST, NKI
set_style()

SRC = "refbench/assd_0p8_measures.jsonl"
REF_A, REF_B = "CAST_0.8", "NKI_0.8"
N_BOOT = 5000
rng = np.random.default_rng(0)

rows = [json.loads(l) for l in open(SRC) if l.strip()]
by = {}
for r in rows:
    by.setdefault(r["subject_id"], {})[r["reference"]] = r
P = [v for v in by.values() if REF_A in v and REF_B in v]
if not P:
    raise SystemExit(f"no paired subjects in {SRC}")


def diff(field):
    return np.array([v[REF_A][field] - v[REF_B][field] for v in P])


# The three formulations of the same interface distance. 'Forward' is the one that was
# published first and that makes NKI look better; the symmetric ASSD is the fair one.
FORMS = [
    ("Forward\n(template$\\to$subject,\npublished)", "fwd_mean_cort_mm"),
    ("Reverse\n(subject$\\to$template)",              "rev_mean_mm"),
    ("Symmetric\nASSD (fair)",                        "assd_mm"),
]

fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))

# ---- (a) per-subject paired differences, three formulations -------------------------
ax = axes[0]
for i, (label, field) in enumerate(FORMS):
    d = diff(field)
    jit = rng.uniform(-0.16, 0.16, len(d))
    # colour by which reference each subject favours, so the split is readable directly
    ax.scatter((i + jit)[d < 0], d[d < 0], s=9, color=CAST, alpha=0.55, edgecolors="none")
    ax.scatter((i + jit)[d >= 0], d[d >= 0], s=9, color=NKI, alpha=0.55, edgecolors="none")
    med = np.median(d)
    ax.plot([i - 0.30, i + 0.30], [med, med], color="black", lw=2.4, solid_capstyle="butt", zorder=5)
    ax.text(i, med + (0.006 if med >= 0 else -0.006), f"{med:+.3f}", ha="center",
            va="bottom" if med >= 0 else "top", fontsize=8, fontweight="bold", zorder=6)
ax.axhline(0, color="0.4", ls="--", lw=1)
ax.set_xticks(range(len(FORMS)))
ax.set_xticklabels([f[0] for f in FORMS], fontsize=7)
ax.set_xlim(-0.55, len(FORMS) - 0.45)
ax.set_ylabel("paired difference BRAIN CAST $-$ NKI (mm)\n"
              r"$\leftarrow$ BRAIN CAST better  |  NKI better $\rightarrow$", fontsize=7.5)
ax.set_title("Direction of measurement decides the “winner”", fontsize=8.5)
ax.text(0.5, 0.985, f"grid-matched 0.8 mm, n={len(P)} held-out subjects",
        transform=ax.transAxes, ha="center", va="top", fontsize=6.5, color="0.4")
panel_letter(ax, "a")

# ---- (b) symmetric ASSD by template age, bootstrap CIs -------------------------------
ax = axes[1]
sym = diff("assd_mm")
ages = np.array([v[REF_A]["template_age"] for v in P])


def boot_ci(x, n=N_BOOT):
    bs = np.median(rng.choice(x, (n, len(x)), replace=True), axis=1)
    return np.percentile(bs, 2.5), np.percentile(bs, 97.5)


pooled = np.median(sym)
plo, phi = boot_ci(sym)
ax.axhspan(plo, phi, color=CAST, alpha=0.13,
           label=f"pooled {pooled:+.4f} mm [95% CI]")
ax.axhline(pooled, color=CAST, lw=1.2)
xs, ys, los, his = [], [], [], []
for a in sorted(set(ages)):
    x = sym[ages == a]
    lo, hi = boot_ci(x)
    xs.append(a); ys.append(np.median(x)); los.append(lo); his.append(hi)
ys = np.array(ys)
ax.errorbar(xs, ys, yerr=[ys - np.array(los), np.array(his) - ys], fmt="o", color=CAST,
            ms=6, capsize=3, lw=1.3, label="per age stratum")
ax.axhline(0, color="0.4", ls="--", lw=1)
ax.set_xlabel("template age (years)")
ax.set_ylabel("symmetric ASSD: BRAIN CAST $-$ NKI (mm)", fontsize=7.5)
ax.set_title("Symmetric ASSD is a tie at every age", fontsize=8.5)
ax.legend(fontsize=6, loc="upper right")
panel_letter(ax, "b")

fig.tight_layout()
save(fig, "figures_final/assd_headtohead")

print(f"=== BRAIN CAST vs NKI head-to-head, grid-matched 0.8 mm, n={len(P)} paired ===")
print(f"{'formulation':<34}{'median':>10}{'mean':>10}{'CAST better':>14}")
for label, field in FORMS:
    d = diff(field)
    flat = label.replace("\n", " ")
    print(f"  {flat:<32}{np.median(d):>+10.4f}{d.mean():>+10.4f}{f'{int((d<0).sum())}/{len(d)}':>14}")
print(f"\npooled symmetric ASSD median {pooled:+.4f} mm, 95% CI [{plo:+.4f}, {phi:+.4f}]")
print(f"{'age':>5}{'n':>5}{'median':>10}{'CI low':>10}{'CI high':>10}")
for a, y, lo, hi in zip(xs, ys, los, his):
    print(f"{a:>5}{int((ages==a).sum()):>5}{y:>+10.4f}{lo:>+10.4f}{hi:>+10.4f}")
print("\nTable 3 cross-check (median across subjects):")
for ref, name in [(REF_A, "BRAIN CAST"), (REF_B, "NKI")]:
    print(f"  {name:<11} full {np.median([v[ref]['full_median_mm'] for v in P]):.3f}"
          f"   cortical {np.median([v[ref]['cort_median_mm'] for v in P]):.3f}")
print(f"  paired delta  full {np.median(diff('full_median_mm')):+.4f}"
      f"   cortical {np.median(diff('cort_median_mm')):+.4f}")
print(f"  ASSD  mean-based {np.median(diff('assd_mm')):+.4f}"
      f"   median-based {np.median(diff('assd_median_mm')):+.4f}")
