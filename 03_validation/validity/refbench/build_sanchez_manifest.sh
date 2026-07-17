#!/bin/bash
# build_sanchez_manifest.sh
# WORKSTREAM B: emit the Sanchez third-reference manifest from the authoritative
# 1.0 mm ASSD benchmark manifest (assd1p0_manifest.txt, the n=209 ages 5-12 list
# already used for CAST/NKI/Fonov). Sanchez/Richards coverage tops out at 10.5 y,
# so the Sanchez comparison covers the 5-10 overlap only (ages 11-12 dropped).
#
# Source line (assd1p0):  <EID> <SUBJ_AGE> <TPL_AGE> <SEX> <NKI_TAG> <FONOV_TAG>
# Output line (sanchez):  <EID> <SUBJ_AGE> <TPL_AGE> <SEX> <SANCHEZ_TAG>
#
# Age->Sanchez map: held-out TPL_AGE is integer (subjects' ages are whole years),
# so age N rounds to the Sanchez 0.5-y bin N.0 -> SANCHEZ_TAG=Sanchez_age<N>
#   (-> ANTS<N>-0Years3T_brain.nii.gz + AVG<N>-0Years3T_brain_image_seg_wm.nii.gz)
set -uo pipefail
DB="${DB:-/project/contreras-vidal/Yang/PediatricMriDB}"
SRC="${1:-$DB/validity_heatmap_scripts/assd/assd1p0_manifest.txt}"
OUT="${2:-$DB/validity_heatmap_scripts/sanchez_manifest.txt}"
: > "$OUT"
n=0
while read -r EID SAGE TAGE SEX NKI FON; do
  [ -z "$EID" ] && continue
  case "$TAGE" in 5|6|7|8|9|10) ;; *) echo "[skip out-of-coverage] $EID age$TAGE" >&2; continue ;; esac
  echo "$EID $SAGE $TAGE $SEX Sanchez_age${TAGE}" >> "$OUT"
  n=$((n+1))
done < "$SRC"
echo "[manifest] wrote $n lines -> $OUT"
echo "[manifest] array size = $n  (set --array=1-$n%50 in run_sanchez.sbatch)"
