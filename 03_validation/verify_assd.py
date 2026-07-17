import json, numpy as np
from collections import defaultdict
from scipy import stats
BASE="/path/to/cast-project/08_Working_Temp/reverify_2026-06-15"
def load(p):
    by=defaultdict(dict)
    for l in open(p):
        if l.strip():
            r=json.loads(l); by[r['subject_id']][r['reference']]=r
    return by
def h2h(by,refA,refB,fields,label):
    subs=sorted(s for s,d in by.items() if refA in d and refB in d)
    print(f"\n===== {label}: {refA} vs {refB}, n={len(subs)} =====")
    rng=np.random.default_rng(2027)  # independent seed (analyze_assd used 20260615)
    for f,better in fields:
        a=np.array([by[s][refA][f] for s in subs]); b=np.array([by[s][refB][f] for s in subs])
        diff=a-b
        Awin=int((a<b).sum()) if better=='lower' else int((a>b).sum())
        bs=np.median(diff[rng.integers(0,len(diff),(10000,len(diff)))],axis=1)
        lo,hi=np.percentile(bs,[2.5,97.5])
        try: W,pw=stats.wilcoxon(a,b)
        except Exception: pw=float('nan')
        tag="(better=%s)"%better
        print(f"  {f:20s}{tag:14s} A={np.median(a):.4f} B={np.median(b):.4f} medD={np.median(diff):+.4f} "
              f"[CI {lo:+.4f},{hi:+.4f}] {refA}_better={Awin}/{len(subs)} Wilcoxon_p={pw:.1e}")
    return subs
by=load(f"{BASE}/assd_0p8_measures.jsonl")
F=[('cort_median_mm','lower'),('assd_mm','lower'),('assd_median_mm','lower'),
   ('fwd_mean_cort_mm','lower'),('rev_mean_mm','lower'),
   ('cort_pct_within_1mm','higher'),('rev_pct_within_1mm','higher')]
subs=h2h(by,'CAST_0.8','NKI_0.8',F,'0.8mm GRID-MATCHED (=Table 3)')
for ref in ('CAST_0.8','NKI_0.8'):
    sb=np.array([by[s][ref]['mean_signed_cort_mm'] for s in subs])
    print(f"  signed-bias {ref}: median={np.median(sb):+.4f} mm (+ = boundary OUTSIDE subj WM)")
# self-check vs handoff stored value
sid="NDARxxxxxxxx"
if sid in by and 'CAST_0.8' in by[sid]:
    print(f"  [self-check] {sid} CAST cort_median_mm={by[sid]['CAST_0.8']['cort_median_mm']:.8f} (handoff: 0.74229191)")
by10=load(f"{BASE}/assd_1p0_measures.jsonl")
F2=[('cort_median_mm','lower'),('assd_mm','lower'),('assd_median_mm','lower')]
h2h(by10,'CAST','NKI',F2,'1.0mm 3-way')
h2h(by10,'CAST','Fonov',F2,'1.0mm 3-way')
