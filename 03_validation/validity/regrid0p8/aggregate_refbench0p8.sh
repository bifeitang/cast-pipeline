#!/bin/bash
# aggregate_refbench0p8.sh -- run AFTER the gw-refbench0p8 array completes.
# Joins the 0.8 mm re-benchmark (CAST_0.8, NKI_0.8) with the published
# head-to-head rows (CAST=1.0/mixed, NKI=1.0, Fonov) to produce:
#   (a) a combined JSONL with all rows for the affected subjects, and
#   (b) a per-subject PAIRED before/after table:
#         CAST(published) vs NKI(1.0)            <- the original gap
#         CAST_0.8        vs NKI(1.0)            <- regridded CAST vs published NKI
#         CAST_0.8        vs NKI_0.8             <- pure grid-matched contrast
#       on both full_median_mm and cort_median_mm, with paired deltas + medians.
# Primary statistic = full_median_mm (same as the CAST sweep); cort_median_mm 2ndary.
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
H2H=$DB/Validity/refbench/headtohead_measures.jsonl          # published CAST(1.0)/NKI/Fonov
NEW=$DB/Validity/refbench_0p8                                 # per-subject meas_cast0p8/meas_nki0p8
MAN=$DB/validity_heatmap_scripts/refbench0p8_manifest.txt
OUTJ=$DB/Validity/refbench_0p8/headtohead_0p8_measures.jsonl
: > "$OUTJ"

# collect the new 0.8mm rows
while read -r EID AGE SEX NKI; do
  [ -z "$EID" ] && continue
  [ -s "$NEW/$EID/meas_cast0p8.json" ] && cat "$NEW/$EID/meas_cast0p8.json" >> "$OUTJ"
  [ -s "$NEW/$EID/meas_nki0p8.json" ]  && cat "$NEW/$EID/meas_nki0p8.json"  >> "$OUTJ"
done < "$MAN"
echo "[agg] new 0.8mm rows: $(wc -l < "$OUTJ") -> $OUTJ"

python3 - "$H2H" "$OUTJ" "$MAN" <<'PY'
import sys, json, statistics as st
h2h_p, new_p, man_p = sys.argv[1], sys.argv[2], sys.argv[3]

# affected subjects (from the 0.8 manifest)
affected = set()
for ln in open(man_p):
    ln = ln.split()
    if ln: affected.add(ln[0])

# per-subject metric stores
def blank(): return {}
cast1, nki1, cast08, nki08 = {}, {}, {}, {}

for ln in open(h2h_p):
    ln = ln.strip()
    if not ln: continue
    d = json.loads(ln)
    sid = d.get("subject_id")
    if sid not in affected: continue
    ref = d.get("reference")
    if ref == "CAST": cast1[sid] = d
    elif ref == "NKI": nki1[sid] = d

for ln in open(new_p):
    ln = ln.strip()
    if not ln: continue
    d = json.loads(ln)
    sid = d.get("subject_id")
    ref = d.get("reference")
    if ref == "CAST_0.8": cast08[sid] = d
    elif ref == "NKI_0.8": nki08[sid] = d

def paired(A, B, key):
    xs, ys = [], []
    for s in affected:
        if s in A and s in B:
            xs.append(A[s][key]); ys.append(B[s][key])
    return xs, ys

def summ(name, A, B, key):
    xs, ys = paired(A, B, key)
    if not xs:
        print(f"  {name:28s} n=0 (no paired subjects)"); return
    dx = [a-b for a,b in zip(xs,ys)]
    print(f"  {name:28s} n={len(xs):3d}  "
          f"A_med={st.median(xs):.4f}  B_med={st.median(ys):.4f}  "
          f"paired_delta_med(A-B)={st.median(dx):+.4f}  mean={st.mean(dx):+.4f}")

print("\n=== PAIRED before/after (affected subjects only) ===")
print("[full_median_mm]  (PRIMARY; lower=better)")
summ("CAST(published) vs NKI(1.0)", cast1,  nki1, "full_median_mm")
summ("CAST_0.8 vs NKI(1.0)",        cast08, nki1, "full_median_mm")
summ("CAST_0.8 vs NKI_0.8",         cast08, nki08,"full_median_mm")
print("[cort_median_mm]  (secondary)")
summ("CAST(published) vs NKI(1.0)", cast1,  nki1, "cort_median_mm")
summ("CAST_0.8 vs NKI(1.0)",        cast08, nki1, "cort_median_mm")
summ("CAST_0.8 vs NKI_0.8",         cast08, nki08,"cort_median_mm")

# also: CAST self before/after (resolution effect on CAST alone)
print("[CAST self: published(1.0/mixed) -> 0.8]  full_median_mm")
summ("CAST_0.8 vs CAST(published)", cast08, cast1, "full_median_mm")

print(f"\ncoverage: CAST_0.8={len(cast08)}  NKI_0.8={len(nki08)}  "
      f"CAST(pub)={len(cast1)}  NKI(1.0)={len(nki1)}  (of {len(affected)} affected)")
PY
echo "[agg] done -> $OUTJ"
