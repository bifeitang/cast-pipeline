#!/usr/bin/env python3
"""make_assd_figure.py -- honest head-to-head figure: directional asymmetry -> symmetric tie.

Panel A: per-subject paired difference CAST-NKI (mm) for Forward (published, biased),
         Reverse, and Symmetric ASSD. Zero line; the one-sided metric favors NKI, the
         reverse favors CAST, the fair symmetric average is a tie.
Panel B: symmetric-ASSD paired difference per age stratum with bootstrap 95% CIs.

Usage: make_assd_figure.py <assd_measures.jsonl> <assd_results.json> <out.png>
"""
import sys, json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict

meas, resj, outp = sys.argv[1], sys.argv[2], sys.argv[3]
recs = [json.loads(l) for l in open(meas)]
by = defaultdict(dict)
for r in recs:
    by[r['subject_id']][r['reference']] = r
subs = sorted(s for s, d in by.items() if 'CAST_0.8' in d and 'NKI_0.8' in d)
res = json.load(open(resj))


def diff(field):
    return np.array([by[s]['CAST_0.8'][field] - by[s]['NKI_0.8'][field] for s in subs])


fwd = diff('fwd_mean_cort_mm')
rev = diff('rev_mean_mm')
asd = diff('assd_mm')

fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={'width_ratios': [1, 1.15]})

# ---- Panel A: per-subject paired differences ----
data = [fwd, rev, asd]
labels = ['Forward\n(template→subject,\npublished)', 'Reverse\n(subject→template)', 'Symmetric\nASSD (fair)']
pos = [0, 1, 2]
for i, (x, d) in enumerate(zip(pos, data)):
    jit = np.random.RandomState(i).normal(0, 0.05, len(d))
    col = np.where(d > 0, '#d1495b', '#2e86ab')  # red=NKI better, blue=CAST better
    axA.scatter(np.full(len(d), x) + jit, d, s=7, c=col, alpha=0.45, lw=0)
    md = np.median(d)
    axA.plot([x - 0.28, x + 0.28], [md, md], color='k', lw=2.2, zorder=5)
    axA.annotate(f"{md:+.3f}", (x, md), textcoords="offset points", xytext=(0, 8 if md >= 0 else -14),
                 ha='center', fontsize=9, fontweight='bold')
axA.axhline(0, color='gray', lw=1, ls='--')
axA.set_xticks(pos); axA.set_xticklabels(labels, fontsize=8.5)
axA.set_ylabel('paired difference CAST − NKI (mm)\n← CAST better   |   NKI better →', fontsize=9)
axA.set_title('A  Direction-of-measurement decides the "winner"', fontsize=10, loc='left', fontweight='bold')
axA.text(0.5, 0.97, 'grid-matched 0.8 mm, n=144 held-out subjects', transform=axA.transAxes,
         ha='center', va='top', fontsize=8, color='#555')

# ---- Panel B: per-stratum symmetric ASSD diff with CIs ----
ages, diffs, los, his = [], [], [], []
for age, m in res['per_stratum'].items():
    g = m['metrics']['assd_mm']
    ages.append(int(age)); diffs.append(g['paired_diff']); los.append(g['ci'][0]); his.append(g['ci'][1])
order = np.argsort(ages)
ages = np.array(ages)[order]; diffs = np.array(diffs)[order]
los = np.array(los)[order]; his = np.array(his)[order]
err = np.vstack([diffs - los, his - diffs])
pooled = res['pooled']['metrics']['assd_mm']
axB.errorbar(ages, diffs, yerr=err, fmt='o', color='#2e86ab', capsize=3, ms=6, lw=1.5, label='per age stratum')
axB.axhspan(pooled['ci'][0], pooled['ci'][1], color='#2e86ab', alpha=0.12,
            label=f"pooled {pooled['paired_diff']:+.4f} mm [95% CI]")
axB.axhline(pooled['paired_diff'], color='#2e86ab', lw=1, ls='-')
axB.axhline(0, color='gray', lw=1, ls='--')
axB.set_xlabel('template age (years)', fontsize=9)
axB.set_ylabel('symmetric ASSD: CAST − NKI (mm)', fontsize=9)
axB.set_title('B  Symmetric ASSD is a tie at every age', fontsize=10, loc='left', fontweight='bold')
axB.legend(fontsize=8, loc='upper right')
axB.set_ylim(-0.07, 0.05)

fig.tight_layout()
fig.savefig(outp, dpi=160, bbox_inches='tight')
fig.savefig(outp.replace('.png', '.pdf'), bbox_inches='tight')
print(f"[saved] {outp} (+pdf)")
