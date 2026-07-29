"""Supplementary: what the affine component contributes to the deformation cost.

REBUILT AND REFRAMED 2026-07-29 on a dedicated re-registration (DC_TRANSLATION_2026-07-29).

WHY THE PUBLISHED PANEL COULD NOT SIMPLY BE RENUMBERED
It was titled "translation artifact" and claimed the composite affine o SyN cost was
"inflated ~11x (median 35.3 vs 3.2 mm) by a near-rigid coordinate-origin offset that is
independent of age". Two of those three claims do not survive on correct inputs:

                       published        measured now
  clean SyN                3.2 mm           2.44 mm
  composite affine o SyN  35.3 mm           6.83 mm
  inflation                ~11x             2.80x
  offset               ~32 mm, "constant"   4.25 mm, CV 0.58, range 0.6-22.9 mm
  independent of age?      asserted         CONFIRMED (p=0.80, r=+0.01)

So the offset is real and age-independent -- that part stands -- but it is an order of
magnitude smaller than published and it is emphatically NOT constant. Its per-subject
spread (CV 0.58) is the whole story, and a panel built to display a constant cannot show it.

Two defects in the old figure explain the gap:
  1. Its moving images were *_processed_centered.nii.gz -- BINARY BRAIN MASKS registered
     onto gray-scale templates. On a mask the affine stage is as poorly constrained as the
     SyN stage, which inflates its translation without any file header being wrong.
  2. It JOINED TWO SEPARATELY-RUN TABLES on (subject, template), so a single point could
     pair two different registrations of one subject.

Both are fixed. cal_deformation_cost.sh now emits mean/median/p95_disp_total_mm from the
composed field that a -disp-component syn run already builds for the Jacobian, so each
point is ONE registration measured two ways.

WHAT THE PANEL NOW ARGUES -- a better case for SyN-only than the original made
The affine adds a median 4.25 mm that varies enormously between subjects (0.6-22.9 mm) and
correlates only r = 0.26 with the SyN cost it would be added to. It is therefore a large
subject-level nuisance term that is nearly orthogonal to the anatomical mismatch the metric
exists to measure. Reporting the composite would inject that term into every comparison;
reporting the SyN component alone does not. That holds regardless of where the affine's
variability comes from, which is why this argument is more robust than "there is a
constant offset to subtract".

USAGE
    python make_supplement_translation.py
Pull the metrics first:
    rsync -am --include='*/' --include=metrics.txt --exclude='*' \
      carya:/project/contreras-vidal/Yang/DC_TRANSLATION_2026-07-29/ dc_translation/
"""
import csv, glob, os, sys
import numpy as np
from scipy import stats
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from figs_style import set_style, save, panel_letter, CAST, OKABE
set_style()

SRC = os.path.join(HERE, "dc_translation")
# 640 sampled pairs (64 subjects x 10 templates, seeded) plus the 7 validation pairs that
# were run first and fell outside the sample. All are legitimate registrations of the same
# kind, so they are kept rather than discarded to hit a round number.
EXPECT = 647


def load():
    rows = []
    for p in glob.glob(os.path.join(SRC, "**", "metrics.txt"), recursive=True):
        parts = p.split(os.sep)
        tpl, sage, eid = parts[-4], int(parts[-3]), parts[-2]
        r = list(csv.DictReader(open(p), delimiter="\t"))[0]
        if "mean_disp_total_mm" not in r:
            sys.exit(f"FATAL: {p} predates the composite columns -- rerun with the "
                     f"2026-07-29 cal_deformation_cost.sh")
        if r.get("disp_component") != "syn":
            sys.exit(f"FATAL: {p} is not a SyN-only run, so its 'clean' axis would be the "
                     f"composite repeated back")
        rows.append(dict(tpl=tpl, tage=int("".join(c for c in tpl if c.isdigit())),
                         sage=sage, eid=eid, clean=float(r["mean_disp_mm"]),
                         total=float(r["mean_disp_total_mm"])))
    return rows


rows = load()
if not rows:
    sys.exit(f"FATAL: no metrics under {SRC} -- see the rsync line in this file's docstring")
if len(rows) != EXPECT:
    print(f"WARNING: {len(rows)} registrations, expected {EXPECT} -- partial run")

c = np.array([r["clean"] for r in rows])
t = np.array([r["total"] for r in rows])
off = t - c
cv = off.std() / off.mean()
r_ct = float(np.corrcoef(c, t)[0, 1])
lr_age = stats.linregress(np.array([r["sage"] for r in rows], float), off)

fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3))

# (a) the two costs against each other -- the weak correlation IS the argument
ax = axes[0]
ax.scatter(c, t, s=7, alpha=0.30, color=CAST, edgecolors="none")
ax.axhline(np.median(t), ls=":", color="0.5", lw=0.8)
ax.axvline(np.median(c), ls=":", color="0.5", lw=0.8)
ax.set_xlabel("SyN-only cost (mm)")
ax.set_ylabel("composite affine-then-SyN cost (mm)")
ax.set_title(f"The composite tracks the SyN cost weakly\n"
             f"median {np.median(t):.2f} vs {np.median(c):.2f} mm "
             f"({np.median(t) / np.median(c):.1f}×), r = {r_ct:+.2f}", fontsize=8.5)
panel_letter(ax, "a")

# (b) the affine's contribution -- broad, not a constant to subtract
ax = axes[1]
ax.hist(off, bins=40, color=OKABE["orange"], edgecolor="none", alpha=0.85)
ax.axvline(float(np.median(off)), color="0.25", ls="--", lw=1.2)
ax.text(float(np.median(off)), ax.get_ylim()[1] * 0.97, f" median {np.median(off):.2f} mm",
        fontsize=6.5, color="0.25", va="top")
ax.set_xlabel("affine contribution, composite − SyN-only (mm)")
ax.set_ylabel("registrations")
ax.set_title(f"and its excess is not a constant\n"
             f"{off.min():.1f}–{off.max():.1f} mm, CV {cv:.2f}, "
             f"flat in subject age (p = {lr_age.pvalue:.2f})", fontsize=8.5)
panel_letter(ax, "b")

fig.suptitle("The affine component is a large subject-specific term, nearly orthogonal to "
             "the anatomical mismatch", fontsize=9.5)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, os.path.join(HERE, "figures_final", "S_translation_artifact"))

print(f"registrations {len(rows)}   templates {len({r['tpl'] for r in rows})}   "
      f"subjects {len({r['eid'] for r in rows})}")
print(f"clean      median {np.median(c):.3f}  IQR {np.percentile(c, 25):.3f}-"
      f"{np.percentile(c, 75):.3f}")
print(f"composite  median {np.median(t):.3f}  IQR {np.percentile(t, 25):.3f}-"
      f"{np.percentile(t, 75):.3f}")
print(f"ratio      {np.median(t) / np.median(c):.2f}x        (published ~11x)")
print(f"offset     median {np.median(off):.3f}  mean {off.mean():.3f}  SD {off.std():.3f}  "
      f"CV {cv:.3f}")
print(f"           range {off.min():.2f}-{off.max():.2f} mm   (published ~32 mm, 'constant')")
print(f"corr(SyN, composite) r = {r_ct:+.3f}")
print(f"offset vs subject age: slope {lr_age.slope:+.4f} mm/yr  r={lr_age.rvalue:+.3f}  "
      f"p={lr_age.pvalue:.2f}   <- 'independent of age' SURVIVES")
print("\nper-template-age offset (a per-template constant would show near-zero CV):")
for a in sorted({r["tage"] for r in rows}):
    o = np.array([r["total"] - r["clean"] for r in rows if r["tage"] == a])
    print(f"  age {a:>2}  n={len(o):>3}  median {np.median(o):6.3f}  SD {o.std():5.3f}  "
          f"CV {o.std() / o.mean():.2f}")
