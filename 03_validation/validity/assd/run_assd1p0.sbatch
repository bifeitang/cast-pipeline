#!/usr/bin/env bash
#SBATCH --job-name=assd1p0
#SBATCH --output=assd1p0-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
# Symmetric-ASSD RE-MEASURE on the 1.0 mm 3-way benchmark (CAST vs NKI vs Fonov, n=209,
# ages 5-12).  NO re-registration: warped surfaces already exist.  Adds the symmetric/
# signed metric to the published directional 3-way comparison (Fonov corroboration).
#
# Manifest line: "<EID> <SUBJ_AGE> <TPL_AGE> <SEX> <NKI_TAG> <FONOV_TAG>"
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s <<'INNER'
set -uo pipefail
DB=/mnt
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/assd/assd1p0_manifest.txt
MC=$SCR/assd/measure_cell_assd.py
CAST_WM=$DB/Validity/templates_wm                 # age{A}_{sex}_wm.nii.gz
REFWM=$DB/Validity/refbench/templates_wm          # NKI_* + nihpd_* wm
SWEEP=$DB/Validity/sweep                          # surf_matched_syn.npz (CAST)
REF=$DB/Validity/refbench                         # surf_nki_syn / surf_fonov_syn
RES=$REF/assd_1p0_measures.jsonl
: > "$RES"
n=0; oc=0; on=0; of=0
while read -r EID SAGE TAGE SEX NKI_TAG FONOV_TAG; do
  [ -z "${EID:-}" ] && continue
  n=$((n+1))
  # CAST
  SC=$SWEEP/$EID/surf_matched_syn.npz; CW=$CAST_WM/age${TAGE}_${SEX}_wm.nii.gz
  if [[ -f "$SC" && -f "$CW" ]]; then
    L=$(python3 "$MC" "$CW" "$SC" "$SAGE" "$TAGE" "$SEX" "$EID" 6.0 CAST) && { echo "$L" >> "$RES"; oc=$((oc+1)); }
  else echo "[MISS] CAST $EID"; fi
  # NKI
  SN=$REF/$EID/surf_nki_syn.npz; NW=$REFWM/${NKI_TAG}_wm.nii.gz
  if [[ -f "$SN" && -f "$NW" ]]; then
    L=$(python3 "$MC" "$NW" "$SN" "$SAGE" "$TAGE" na "$EID" 6.0 NKI) && { echo "$L" >> "$RES"; on=$((on+1)); }
  else echo "[MISS] NKI $EID"; fi
  # Fonov
  SF=$REF/$EID/surf_fonov_syn.npz; FW=$REFWM/${FONOV_TAG}_wm.nii.gz
  if [[ -f "$SF" && -f "$FW" ]]; then
    L=$(python3 "$MC" "$FW" "$SF" "$SAGE" "$TAGE" na "$EID" 6.0 Fonov) && { echo "$L" >> "$RES"; of=$((of+1)); }
  else echo "[MISS] Fonov $EID"; fi
done < "$MAN"
echo "[done] subjects=$n CAST_ok=$oc NKI_ok=$on Fonov_ok=$of -> $RES"
wc -l "$RES"
INNER
