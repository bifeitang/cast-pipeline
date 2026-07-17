#!/bin/bash
# aggregate_refbench_renorm.sh -- run AFTER the gw-renorm7m array completes.
# Builds the paired age7_male table:
#     CAST_0.8     vs NKI_0.8     <- the original (grid-matched) interface gap
#     CAST_renorm  vs NKI_0.8     <- gap remaining after WM-contrast restoration
#     CAST_renorm  vs CAST_0.8    <- the improvement attributable to contrast
# on full_median_mm (PRIMARY) and cort_median_mm (secondary), over the SAME 35
# held-out subjects, and prints the RECOVERED FRACTION of the gap:
#     recovered = (gap_before - gap_after) / gap_before
# computed both on paired medians and as the median of per-subject recovery.
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
OLD=$DB/Validity/refbench_0p8                 # meas_cast0p8.json / meas_nki0p8.json
NEW=$DB/Validity/refbench_renorm_age7m        # meas_castRN.json
MAN=$DB/validity_heatmap_scripts/refbench_renorm_age7m_manifest.txt
OUTJ=$NEW/headtohead_renorm_measures.jsonl
: > "$OUTJ"

while read -r EID AGE SEX; do
  [ -z "$EID" ] && continue
  [ -s "$OLD/$EID/meas_cast0p8.json" ] && cat "$OLD/$EID/meas_cast0p8.json" >> "$OUTJ"
  [ -s "$OLD/$EID/meas_nki0p8.json"  ] && cat "$OLD/$EID/meas_nki0p8.json"  >> "$OUTJ"
  [ -s "$NEW/$EID/meas_castRN.json"  ] && cat "$NEW/$EID/meas_castRN.json"  >> "$OUTJ"
done < "$MAN"
echo "[agg] rows: $(wc -l < "$OUTJ") -> $OUTJ"

python3 - "$OUTJ" "$MAN" <<'PY'
import sys, json, statistics as st
rows_p, man_p = sys.argv[1], sys.argv[2]
subs = [ln.split()[0] for ln in open(man_p) if ln.split()]
cast08, nki08, castRN = {}, {}, {}
for ln in open(rows_p):
    ln=ln.strip()
    if not ln: continue
    d=json.loads(ln); sid=d.get("subject_id"); ref=d.get("reference")
    if   ref=="CAST_0.8":    cast08[sid]=d
    elif ref=="NKI_0.8":     nki08[sid]=d
    elif ref=="CAST_renorm": castRN[sid]=d

def paired(A,B,key):
    xs,ys=[],[]
    for s in subs:
        if s in A and s in B:
            xs.append(A[s][key]); ys.append(B[s][key])
    return xs,ys

def summ(name,A,B,key):
    xs,ys=paired(A,B,key)
    if not xs: print(f"  {name:30s} n=0"); return None
    dx=[a-b for a,b in zip(xs,ys)]
    print(f"  {name:30s} n={len(xs):2d}  A_med={st.median(xs):.4f}  B_med={st.median(ys):.4f}  "
          f"paired_delta_med(A-B)={st.median(dx):+.4f}  mean={st.mean(dx):+.4f}")
    return st.median(dx)

for key,label in (("full_median_mm","[full_median_mm]  PRIMARY"),
                  ("cort_median_mm","[cort_median_mm]  secondary")):
    print(f"\n{label}  (CAST higher than NKI = worse)")
    gap_before = summ("CAST_0.8    vs NKI_0.8", cast08, nki08, key)
    gap_after  = summ("CAST_renorm vs NKI_0.8", castRN, nki08, key)
    impr       = summ("CAST_renorm vs CAST_0.8", castRN, cast08, key)
    if gap_before is not None and gap_after is not None and abs(gap_before)>1e-9:
        rec = (gap_before - gap_after)/gap_before
        print(f"  --> RECOVERED FRACTION of gap (paired medians): {rec*100:.1f}%  "
              f"(gap {gap_before:+.4f} -> {gap_after:+.4f})")
    # per-subject recovery fraction (only subjects with all three + positive gap)
    rs=[]
    for s in subs:
        if s in cast08 and s in nki08 and s in castRN:
            gb=cast08[s][key]-nki08[s][key]
            ga=castRN[s][key]-nki08[s][key]
            if abs(gb)>1e-6: rs.append((gb-ga)/gb)
    if rs:
        print(f"  --> per-subject recovery: median={st.median(rs)*100:.1f}%  "
              f"mean={st.mean(rs)*100:.1f}%  n={len(rs)}")

print(f"\ncoverage: CAST_renorm={len(castRN)}  CAST_0.8={len(cast08)}  NKI_0.8={len(nki08)}  (of {len(subs)})")
PY
echo "[agg] done -> $OUTJ"
