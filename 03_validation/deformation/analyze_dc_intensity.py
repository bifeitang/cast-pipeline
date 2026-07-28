#!/usr/bin/env python3
"""Read the intensity rerun's metrics.txt files and answer the three open questions.

Written 2026-07-28 while the 5,104 jobs were still queued, so that whoever picks this up --
including a fresh session with no memory of the investigation -- can get the answer by
running one command instead of reconstructing the analysis.

Background: 04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28.md
Short version: every deformation-cost registration in the paper was run on BINARY BRAIN
MASKS against greyscale templates. CC has zero local variance inside a binary mask, so the
optimiser was matching an outline with SyN regularisation driving the interior --
under-constrained, not merely harder. Pilot (n=8) showed displacement 8.400 -> 2.362 mm and
between-subject SD 3.409 -> 0.127.

THE THREE QUESTIONS
  Q1  Does F2's age effect survive?  Published: median 3.08 mm at |dage|<0.5 y rising to
      3.63 mm at |dage|>=2 y, called "real but gentle" and "not statistically robust".
      Against the old SD of 3.4 that 0.55 mm was buried. Against ~0.13 it would be large.
  Q2  CAST vs NKI. Published "~3.8 vs 3.6 mm" -- a 0.2 mm gap against SD 3.4, i.e.
      uninterpretable. Now both arms use identical inputs and settings.
  Q3  Does the metric discriminate at all? The paper de-emphasises deformation cost because
      it is "SyN-saturated". That was concluded FROM THE MASK DATA. If the metric was
      insensitive because it was ill-posed rather than saturated, that reasoning needs
      rewriting. This is the one that changes the paper's argument, not just its numbers.

USAGE (pull the metrics down first, or run with --remote to rsync them):
    python analyze_dc_intensity.py [--remote]

Partial results are fine and expected -- it reports coverage so you can judge whether there
is enough to trust. Do not read Q1 before every template age has a decent subject count.
"""
import csv, os, subprocess, sys, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "dc_intensity")
CAST_REMOTE = "carya:/project/contreras-vidal/Yang/DC_INTENSITY_2026-07-27/"
NKI_REMOTE = "carya:/project/contreras-vidal/Yang/DC_NKI_INTENSITY_2026-07-28/"
AGE_CSV = os.path.join(HERE, "DeformationAnalysis",
                       "test_set_on_template_metrics_with_subject_age.csv")


def pull():
    for sub, remote in (("cast", CAST_REMOTE), ("nki", NKI_REMOTE)):
        dst = os.path.join(LOCAL, sub)
        os.makedirs(dst, exist_ok=True)
        subprocess.run(["rsync", "-am", "--include=*/", "--include=metrics.txt",
                        "--exclude=*", remote, dst + "/"], check=False)


def load(sub):
    """metrics.txt -> list of dicts. Path is <root>/<tpl_id>/<subject_age>/<eid>/metrics.txt"""
    out = []
    for p in glob.glob(os.path.join(LOCAL, sub, "**", "metrics.txt"), recursive=True):
        parts = p.split(os.sep)
        try:
            tpl_id, subj_age, eid = parts[-4], int(parts[-3]), parts[-2]
        except (IndexError, ValueError):
            continue
        with open(p) as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        if not rows:
            continue
        r = rows[0]
        try:
            rec = dict(tpl_id=tpl_id, subj_age=subj_age, eid=eid,
                       disp=float(r["mean_disp_mm"]),
                       logJ=float(r["mean_logJ"]),
                       comp=r.get("disp_component", "?"))
        except (KeyError, ValueError):
            continue
        # template age from the directory name: age9_female or NKI_age9
        digits = "".join(c for c in tpl_id.replace("NKI_", "") if c.isdigit())
        rec["tpl_age"] = int(digits) if digits else None
        rec["d_age"] = rec["tpl_age"] - rec["subj_age"] if rec["tpl_age"] else None
        out.append(rec)
    return out


def coverage(rows, label):
    print(f"\n=== {label}: {len(rows)} registrations ===")
    if not rows:
        return False
    bad = [r for r in rows if r["comp"] != "syn"]
    if bad:
        print(f"  !! {len(bad)} rows are not disp_component=syn -- mixed convention, STOP")
    byt = {}
    for r in rows:
        byt.setdefault(r["tpl_age"], []).append(r)
    print("  template age:  " + "  ".join(f"{a}:{len(v)}" for a, v in sorted(byt.items())))
    thin = [a for a, v in byt.items() if len(v) < 30]
    if thin:
        print(f"  thin coverage at template ages {sorted(thin)} -- treat Q1 as provisional")
    return not bad


def q1_age_effect(rows):
    print("\n" + "=" * 72)
    print("Q1  AGE EFFECT   (published: 3.08 mm at |dage|<0.5 -> 3.63 mm at |dage|>=2)")
    print("=" * 72)
    d = np.array([r["d_age"] for r in rows], dtype=float)
    v = np.array([r["disp"] for r in rows], dtype=float)
    near, far = v[np.abs(d) < 0.5], v[np.abs(d) >= 2]
    print(f"  between-subject SD, all registrations : {v.std():.4f} mm   (mask era: 3.409)")
    if len(near) and len(far):
        from scipy import stats
        u, p = stats.mannwhitneyu(near, far)
        eff = np.median(far) - np.median(near)
        print(f"  |dage| < 0.5 : median {np.median(near):.3f} mm  (n={len(near)})")
        print(f"  |dage| >= 2  : median {np.median(far):.3f} mm  (n={len(far)})")
        print(f"  effect       : {eff:+.3f} mm   Mann-Whitney p = {p:.2e}")
        print(f"  effect / SD  : {eff / v.std():.2f}   <- mask era was 0.55/3.41 = 0.16")
        print(f"  VERDICT      : {'age effect RESOLVED' if p < 0.05 else 'no detectable age effect'}")
    for a in sorted({r["tpl_age"] for r in rows}):
        s = np.array([r["disp"] for r in rows if r["tpl_age"] == a])
        print(f"    template age {a:>2}: median {np.median(s):.3f} mm  SD {s.std():.3f}  n={len(s)}")


def q2_cast_vs_nki(cast, nki):
    print("\n" + "=" * 72)
    print("Q2  CAST vs NKI   (published: ~3.8 vs 3.6 mm)")
    print("=" * 72)
    if not nki:
        print("  no NKI results yet")
        return
    c = np.array([r["disp"] for r in cast]); n = np.array([r["disp"] for r in nki])
    print(f"  CAST : median {np.median(c):.3f} mm  SD {c.std():.3f}  n={len(c)}")
    print(f"  NKI  : median {np.median(n):.3f} mm  SD {n.std():.3f}  n={len(n)}")
    diff = np.median(c) - np.median(n)
    print(f"  diff : {diff:+.3f} mm  =  {abs(diff) / max(c.std(), 1e-9):.2f} SD")
    # paired where the same subject has both
    cm = {}
    for r in cast: cm.setdefault(r["eid"], []).append(r["disp"])
    nm = {}
    for r in nki: nm.setdefault(r["eid"], []).append(r["disp"])
    both = sorted(set(cm) & set(nm))
    if both:
        from scipy import stats
        pc = np.array([np.mean(cm[e]) for e in both])
        pn = np.array([np.mean(nm[e]) for e in both])
        t, p = stats.wilcoxon(pc, pn)
        print(f"  paired on {len(both)} subjects: CAST-NKI {np.mean(pc - pn):+.4f} mm, "
              f"Wilcoxon p = {p:.2e}")


def q3_discriminates(rows):
    print("\n" + "=" * 72)
    print("Q3  DOES THE METRIC DISCRIMINATE?  (the 'SyN-saturated' argument)")
    print("=" * 72)
    d = np.array([abs(r["d_age"]) for r in rows], dtype=float)
    v = np.array([r["disp"] for r in rows], dtype=float)
    if len(set(d)) > 1:
        from scipy import stats
        r_, p_ = stats.pearsonr(d, v)
        print(f"  |dage| vs displacement : r = {r_:+.3f}, p = {p_:.2e}, n = {len(v)}")
        slope = np.polyfit(d, v, 1)[0]
        print(f"  slope                  : {slope:+.4f} mm per year of mismatch")
        print(f"  signal-to-noise        : slope*4y / SD = {abs(slope) * 4 / v.std():.2f}")
        print()
        if p_ < 0.05:
            print("  The metric DOES track age mismatch. The paper's stated reason for")
            print("  de-emphasising deformation cost -- that SyN saturates it -- was drawn")
            print("  from the mask data and needs rewriting. Structural fidelity remains the")
            print("  primary evidence; this becomes an ADDITIONAL argument for age specificity.")
        else:
            print("  The metric still does not track age mismatch on well-posed registrations,")
            print("  so the SyN-saturation argument survives and is now properly supported.")


def main():
    if "--remote" in sys.argv:
        print("pulling metrics from carya ...")
        pull()
    cast, nki = load("cast"), load("nki")
    ok = coverage(cast, "CAST")
    coverage(nki, "NKI")
    if not cast:
        print("\nnothing to analyse yet")
        return 1
    if not ok:
        print("\nrefusing to analyse a mixed-convention set")
        return 1
    q1_age_effect(cast)
    q2_cast_vs_nki(cast, nki)
    q3_discriminates(cast)
    print("\nCompare against the mask-era numbers in "
          "04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
