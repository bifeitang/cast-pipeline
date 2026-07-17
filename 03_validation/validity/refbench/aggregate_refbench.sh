#!/bin/bash
# aggregate_refbench.sh  -- run AFTER the gw-refbench array completes.
# Builds one head-to-head JSONL with three matched-SyN rows per subject:
#   CAST  (from the existing $DB/Validity/sweep/<EID>/meas_matched_syn.json)
#   NKI   (from $DB/Validity/refbench/<EID>/meas_nki_syn.json)
#   Fonov (from $DB/Validity/refbench/<EID>/meas_fonov_syn.json)
# Primary comparison statistic = full_median_mm (same as the CAST sweep).
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
MAN=$DB/validity_heatmap_scripts/refbench_manifest.txt
OUT=$DB/Validity/refbench/headtohead_measures.jsonl
: > "$OUT"
while read -r EID AGE SEX NKI FON; do
  [ -z "$EID" ] && continue
  cast=$DB/Validity/sweep/$EID/meas_matched_syn.json
  [ -s "$cast" ] && python3 -c "import sys,json;d=json.load(open('$cast'));d.update({'reference':'CAST','kind':'matched_syn'});print(json.dumps(d))" >> "$OUT" 2>/dev/null
  [ -s "$DB/Validity/refbench/$EID/meas_nki_syn.json" ]   && cat "$DB/Validity/refbench/$EID/meas_nki_syn.json"   >> "$OUT"
  [ -s "$DB/Validity/refbench/$EID/meas_fonov_syn.json" ] && cat "$DB/Validity/refbench/$EID/meas_fonov_syn.json" >> "$OUT"
done < "$MAN"
echo "[agg] rows: $(wc -l < "$OUT") -> $OUT"
# per-reference summary of the primary statistic
python3 - "$OUT" <<'PY'
import sys,json,statistics as st
from collections import defaultdict
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
g=defaultdict(list)
for r in rows: g[r.get('reference','?')].append(r['full_median_mm'])
print("reference  n     median_of_full_median_mm   mean")
for k in ('CAST','NKI','Fonov'):
    v=g.get(k,[])
    if v: print(f"{k:9s} {len(v):4d}   {st.median(v):.4f}                  {st.mean(v):.4f}")
PY
