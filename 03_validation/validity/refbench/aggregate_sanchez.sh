#!/bin/bash
# aggregate_sanchez.sh -- run AFTER the gw-sanchez array completes.
# WORKSTREAM B: fold the Sanchez third-reference ASSD rows into the existing
# 1.0 mm 3-way symmetric-ASSD measure file and run the paired analysis so the
# CAST-vs-Sanchez comparison drops into Table 3 alongside CAST/NKI/Fonov.
#
# Inputs:
#   $DB/Validity/refbench/assd_1p0_measures.jsonl        (CAST/NKI/Fonov rows, n=209)
#   $DB/Validity/refbench/<EID>/meas_sanchez_assd.json   (Sanchez rows, n<=189, ages 5-10)
# Output:
#   $DB/Validity/refbench/assd_1p0_sanchez_measures.jsonl  (4-reference combined)
#   stdout: analyze_assd.py paired reports for CAST-vs-Sanchez, Sanchez-vs-NKI,
#           Sanchez-vs-Fonov (both directional cort + symmetric ASSD, bootstrap CI,
#           per-age strata).
set -uo pipefail
DB="${DB:-/project/contreras-vidal/Yang/PediatricMriDB}"
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/sanchez_manifest.txt
BASE=$DB/Validity/refbench/assd_1p0_measures.jsonl     # CAST/NKI/Fonov 3-way
OUT=$DB/Validity/refbench/assd_1p0_sanchez_measures.jsonl
AN=$SCR/assd/analyze_assd.py

if [[ ! -s "$BASE" ]]; then echo "[ERR] missing 3-way base $BASE"; exit 1; fi

# 1) start from the existing 3-way file, then append every Sanchez measure
cp -f "$BASE" "$OUT"
ns=0
while read -r EID SAGE TAGE SEX TAG; do
  [ -z "$EID" ] && continue
  f=$DB/Validity/refbench/$EID/meas_sanchez_assd.json
  if [[ -s "$f" ]]; then cat "$f" >> "$OUT"; ns=$((ns+1)); else echo "[MISS sanchez] $EID" >&2; fi
done < "$MAN"
echo "[agg] appended $ns Sanchez rows -> $OUT"
echo "[agg] total rows: $(wc -l < "$OUT")"

# 2) per-reference quick summary of the primary statistics
python3 - "$OUT" <<'PY'
import sys,json,statistics as st
from collections import defaultdict
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
g=defaultdict(lambda: defaultdict(list))
for r in rows:
    ref=r.get('reference','?')
    g[ref]['assd'].append(r['assd_mm'])
    g[ref]['cort'].append(r['cort_median_mm'])
print("\n=== per-reference (median over subjects) ===")
print(f"{'reference':10s} {'n':>4s}  {'assd_mm(med)':>13s} {'cort_median_mm(med)':>20s}")
for k in ('CAST','NKI','Fonov','Sanchez'):
    if k in g:
        a=g[k]['assd']; c=g[k]['cort']
        print(f"{k:10s} {len(a):4d}  {st.median(a):13.4f} {st.median(c):20.4f}")
PY

# 3) paired analyses (analyze_assd.py is generic in refA/refB)
for pair in "CAST Sanchez" "Sanchez NKI" "Sanchez Fonov" "NKI Sanchez" "Fonov Sanchez"; do
  set -- $pair
  echo ""
  echo "############################################################"
  echo "# PAIRED:  $1  vs  $2"
  echo "############################################################"
  python3 "$AN" "$OUT" "$1" "$2" || echo "[WARN] analyze failed for $1 vs $2"
done
