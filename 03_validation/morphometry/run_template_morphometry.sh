set -uo pipefail
. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null
T=/mnt/Templates/UpdatedTemplates
SCR=/mnt/validity_heatmap_scripts
OUT=/mnt/tissue_volume_results/template_morphometry
mkdir -p $OUT
: > $OUT/template_morphometry.jsonl
for a in 5 6 7 8 9 10 11 12 13 14 15 17 18; do
  for s in female male; do
    tpl=$T/age${a}_${s}_template.nii.gz
    [ -f "$tpl" ] || { echo "[skip missing] age${a}_${s}"; continue; }
    python3 $SCR/template_morphometry.py "$tpl" "$OUT" "age${a}_${s}" >> $OUT/template_morphometry.jsonl 2>>$OUT/err.log \
      && echo "[done] age${a}_${s}" || echo "[FAIL] age${a}_${s}"
  done
done
echo "=== morphometry rows: $(wc -l < $OUT/template_morphometry.jsonl) ==="
