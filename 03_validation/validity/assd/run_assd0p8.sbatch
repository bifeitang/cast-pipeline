#!/usr/bin/env bash
#SBATCH --job-name=assd0p8
#SBATCH --output=assd0p8-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
# Symmetric-ASSD RE-MEASURE on the grid-matched 0.8 mm benchmark (n=144, ages 5-10).
# NO re-registration: the warped subject surfaces (surf_cast0p8.npz / surf_nki0p8.npz)
# already exist from refbench_0p8. This job only runs the extended metric
# (measure_cell_assd.py) on each existing surface + the matching template WM mask,
# emitting forward (== published directional fields, self-checked) + reverse + symmetric
# ASSD + signed bias. Single sequential job -> no array race on the shared output jsonl.
#
# Manifest line: "<EID> <SUBJ_AGE> <TPL_AGE> <SEX> <CAST_REFTPL> <NKI_TAG>"
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s <<'INNER'
set -uo pipefail
DB=/mnt
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/assd/assd0p8_manifest.txt
TPL=$DB/Templates/UpdatedTemplates_0p8
NKI=$DB/Validity/refbench_0p8/templates_nki0p8
OUT=$DB/Validity/refbench_0p8
RES=$OUT/assd_0p8_measures.jsonl
MC=$SCR/assd/measure_cell_assd.py
: > "$RES"
n=0; ok_c=0; ok_n=0
while read -r EID SAGE TAGE SEX CAST_REFTPL NKI_TAG; do
  [ -z "${EID:-}" ] && continue
  n=$((n+1))
  SC=$OUT/$EID/surf_cast0p8.npz; CW=$TPL/age${TAGE}_${SEX}_wm.nii.gz
  SN=$OUT/$EID/surf_nki0p8.npz;  NW=$NKI/${NKI_TAG}_wm.nii.gz
  if [[ -f "$SC" && -f "$CW" ]]; then
    if L=$(python3 "$MC" "$CW" "$SC" "$SAGE" "$TAGE" "$SEX" "$EID" 6.0 CAST_0.8); then
      echo "$L" >> "$RES"; ok_c=$((ok_c+1))
    else echo "[WARN] CAST measure failed $EID"; fi
  else echo "[MISS] CAST inputs $EID (SC=$SC CW=$CW)"; fi
  if [[ -f "$SN" && -f "$NW" ]]; then
    if L=$(python3 "$MC" "$NW" "$SN" "$SAGE" "$TAGE" na "$EID" 6.0 NKI_0.8); then
      echo "$L" >> "$RES"; ok_n=$((ok_n+1))
    else echo "[WARN] NKI measure failed $EID"; fi
  else echo "[MISS] NKI inputs $EID (SN=$SN NW=$NW)"; fi
done < "$MAN"
echo "[done] subjects=$n  CAST_ok=$ok_c  NKI_ok=$ok_n  -> $RES"
wc -l "$RES"
INNER
