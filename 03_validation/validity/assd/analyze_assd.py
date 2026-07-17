#!/usr/bin/env python3
"""analyze_assd.py -- aggregate the symmetric-ASSD re-measure with bootstrap CIs.

Answers the load-bearing question: does the directional CAST-vs-NKI ranking change
under the fair symmetric (ASSD) metric? Reports, paired per subject:
  - directional cort (the published metric)  vs  symmetric ASSD
  - forward vs reverse component asymmetry
  - %-within-1mm in BOTH directions
  - signed bias (inside/outside)
with 10k-bootstrap 95% CIs, pooled and per template-age stratum.

Usage: analyze_assd.py <assd_measures.jsonl> <refA> <refB> [out.json]
       e.g.  analyze_assd.py assd_0p8_measures.jsonl CAST_0.8 NKI_0.8
"""
import sys, json, numpy as np
from collections import defaultdict
np.random.seed(20260615)

path, refA, refB = sys.argv[1], sys.argv[2], sys.argv[3]
outp = sys.argv[4] if len(sys.argv) > 4 else None
recs = [json.loads(l) for l in open(path)]
by = defaultdict(dict)
for r in recs:
    by[r['subject_id']][r['reference']] = r
subs = sorted(s for s, d in by.items() if refA in d and refB in d)


def boot_med(x, n=10000):
    x = np.asarray(x); idx = np.random.randint(0, len(x), (n, len(x)))
    bs = np.median(x[idx], axis=1)
    return float(np.median(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def report(subs, label):
    def col(ref, f): return np.array([by[s][ref][f] for s in subs])
    print(f"\n===== {label}  ({refA} vs {refB}, n={len(subs)} paired) =====")
    out = {'label': label, 'n': len(subs), 'metrics': {}}
    fields = [
        ('cort_median_mm', 'DIRECTIONAL cort median (published metric)', 'lower'),
        ('assd_mm', 'SYMMETRIC ASSD (mean)', 'lower'),
        ('assd_median_mm', 'SYMMETRIC ASSD (median)', 'lower'),
        ('fwd_mean_cort_mm', 'forward only (boundary->vertex)', 'lower'),
        ('rev_mean_mm', 'reverse only (vertex->boundary)', 'lower'),
        ('cort_pct_within_1mm', '%within1mm forward', 'higher'),
        ('rev_pct_within_1mm', '%within1mm reverse', 'higher'),
    ]
    for f, desc, better in fields:
        a, b = col(refA, f), col(refB, f)
        diff = a - b
        md, lo, hi = boot_med(diff)
        if better == 'lower':
            Awin = int(np.sum(a < b))
        else:
            Awin = int(np.sum(a > b))
        print(f"  {desc}:")
        print(f"     {refA}={np.median(a):.4f}  {refB}={np.median(b):.4f}  "
              f"paired Δ({refA}-{refB})={md:+.4f} [95%CI {lo:+.4f},{hi:+.4f}]  "
              f"{refA} better in {Awin}/{len(subs)}")
        out['metrics'][f] = dict(desc=desc, better=better,
                                 A_median=float(np.median(a)), B_median=float(np.median(b)),
                                 paired_diff=md, ci=[lo, hi], A_better=Awin, n=len(subs))
    # signed bias for each ref
    for ref in (refA, refB):
        if 'mean_signed_cort_mm' in by[subs[0]][ref]:
            sb = col(ref, 'mean_signed_cort_mm')
            print(f"  signed bias {ref}: median={np.median(sb):+.4f} mm "
                  f"(+ = template boundary OUTSIDE subject WM)")
            out['metrics'].setdefault('signed', {})[ref] = float(np.median(sb))
    return out


full = report(subs, 'POOLED')
strata = defaultdict(list)
for s in subs:
    strata[by[s][refA]['template_age']].append(s)
per = {}
for age in sorted(strata):
    if len(strata[age]) >= 5:
        per[age] = report(strata[age], f'age{age} (n={len(strata[age])})')

if outp:
    json.dump({'pooled': full, 'per_stratum': per}, open(outp, 'w'), indent=2)
    print(f"\n[saved] {outp}")

# headline verdict
dirA = full['metrics']['cort_median_mm']
asd = full['metrics']['assd_mm']
print("\n===== VERDICT =====")
print(f"Directional cort: {refA}-{refB} = {dirA['paired_diff']:+.4f} ({refA} better in {dirA['A_better']}/{full['n']})")
print(f"Symmetric ASSD:   {refA}-{refB} = {asd['paired_diff']:+.4f} ({refA} better in {asd['A_better']}/{full['n']})")
flip = (dirA['paired_diff'] > 0) != (asd['paired_diff'] > 0)
print("Ranking under symmetric metric: " + ("REVERSES" if flip else "does NOT reverse — same direction"))
