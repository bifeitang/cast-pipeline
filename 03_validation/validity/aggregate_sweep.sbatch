#!/usr/bin/env bash
#SBATCH --job-name=gw-agg
#SBATCH --output=gw-agg-%j.out
#SBATCH --error=gw-agg-%j.err
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=12G
#SBATCH --time=01:30:00
# STEP 2 aggregation: (1) recompute per-cell measures from the durable surface npz
# (matched SyN, matched affine, cross-sex affine), collate to sweep_measures.jsonl;
# (2) per-stratum gray-white validity heat maps + summaries (DD-F5).
# Designed to run AFTER the sweep + WM-mask jobs (submit with --dependency).
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/sweep_manifest.txt
SWEEP=/mnt/Validity/sweep
WM=/mnt/Validity/templates_wm
AGGH=$DB/Validity/sweep_aggregate
mkdir -p "$AGGH/heatmaps"
AGG=/mnt/Validity/sweep_aggregate
run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'

# ---- (1) recompute per-cell measures from npz (cheap, robust to WM lag) ----
echo "[agg] recomputing per-cell measures"
run "$ENV : > $AGG/sweep_measures.jsonl
while read EID AGE SEX; do
  [ -z \"\$EID\" ] && continue
  OPP=female; [ \"\$SEX\" = female ] && OPP=male
  d=$SWEEP/\$EID
  mwm=$WM/age\${AGE}_\${SEX}_wm.nii.gz
  xwm=$WM/age\${AGE}_\${OPP}_wm.nii.gz
  if [ -f \$d/surf_matched_syn.npz -a -f \$mwm ]; then
    python3 $SCR/measure_cell.py \$mwm \$d/surf_matched_syn.npz \$AGE \$AGE \$SEX \$EID 6.0 2>/dev/null \
      | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),\"kind\":\"matched_syn\"})) for l in sys.stdin if l.strip()]' >> $AGG/sweep_measures.jsonl
  fi
  if [ -f \$d/surf_matched_affine.npz -a -f \$mwm ]; then
    python3 $SCR/measure_cell.py \$mwm \$d/surf_matched_affine.npz \$AGE \$AGE \$SEX \$EID 6.0 2>/dev/null \
      | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),\"kind\":\"matched_affine\"})) for l in sys.stdin if l.strip()]' >> $AGG/sweep_measures.jsonl
  fi
  if [ -f \$d/surf_cross_affine.npz -a -f \$xwm ]; then
    python3 $SCR/measure_cell.py \$xwm \$d/surf_cross_affine.npz \$AGE \$AGE \$OPP \$EID 6.0 2>/dev/null \
      | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),\"kind\":\"cross_affine\"})) for l in sys.stdin if l.strip()]' >> $AGG/sweep_measures.jsonl
  fi
done < $MAN
echo \"[agg] measures rows: \$(wc -l < $AGG/sweep_measures.jsonl)\""

# ---- (2) per-stratum SyN validity heat maps (DD-F5) ----
echo "[agg] per-stratum heat maps"
for a in 5 6 7 8 9 10 11 12; do
  for s in female male; do
    mwm=$DB/Validity/templates_wm/age${a}_${s}_wm.nii.gz
    [ -f "$mwm" ] || { echo "[skip no-wm] age${a}_${s}"; continue; }
    # gather matched-syn npz for subjects in this stratum
    LIST=""
    while read EID AGE SEX; do
      [ "$AGE" = "$a" -a "$SEX" = "$s" ] || continue
      f=$DB/Validity/sweep/$EID/surf_matched_syn.npz
      [ -f "$f" ] && LIST="$LIST /mnt/Validity/sweep/$EID/surf_matched_syn.npz"
    done < "$MAN"
    n=$(echo $LIST | wc -w)
    [ "$n" -lt 2 ] && { echo "[skip n<2] age${a}_${s} (n=$n)"; continue; }
    echo "[heat] age${a}_${s} n=$n"
    run "$ENV CORTICAL_CUT_MM=6.0 python3 $SCR/validity_heatmap_aggregate_surf.py syn $WM/age${a}_${s}_wm.nii.gz $AGG/heatmaps/age${a}_${s} $LIST" \
      || echo "[FAIL heat] age${a}_${s}"
  done
done
echo "[agg] DONE -> $AGGH"
ls "$AGGH/heatmaps"/*_summary.json 2>/dev/null | wc -l
