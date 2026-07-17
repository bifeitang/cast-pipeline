#!/bin/bash
# build_refbench_manifest.sh
# Emit the head-to-head benchmark manifest from the authoritative CAST
# sweep_manifest.txt: ages 5-12 only, each subject mapped to its matched NKI
# reference template + Fonov/NIHPD band. Only subjects whose CAST sweep dir
# already has the fs2mov bridge are emitted (so the reference arm can reuse it).
#
# NKI mapping (exact-age 1mm MNI templates on HPC for 7-12; 5-6 fall back to
# the NKI 6-7y band template, which is the youngest NKI atlas available):
#   5->NKI_age6a7  6->NKI_age6a7  7->NKI_age7 ... 12->NKI_age12
# Fonov mapping = nearest band-midpoint among the 4 NIHPD bands present:
#   04.5-08.5 (mid 6.5) | 07.0-11.0 (9.0) | 07.5-13.5 (10.5) | 10.0-14.0 (12.0)
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
SRC=$DB/Validity/sweep_manifest.txt
OUT=$DB/validity_heatmap_scripts/refbench_manifest.txt
: > "$OUT"

nki_for() {  # arg: integer age
  case "$1" in
    5|6) echo "NKI_age6a7_brain_template.nii.gz" ;;
    7|8|9|10|11|12) echo "NKI_age${1}_brain_template.nii.gz" ;;
    *) echo "" ;;
  esac
}
fonov_for() {  # arg: integer age -> nearest band midpoint
  local a=$1
  # midpoints: 6.5, 9.0, 10.5, 12.0  (x10 to stay integer)
  local bands=("nihpd_sym_04.5-08.5:65" "nihpd_sym_07.0-11.0:90" "nihpd_sym_07.5-13.5:105" "nihpd_sym_10.0-14.0:120")
  local best="" bestd=99999
  local a10=$((a*10))
  for b in "${bands[@]}"; do
    local pfx=${b%%:*}; local mid=${b##*:}
    local d=$((a10-mid)); [ $d -lt 0 ] && d=$((-d))
    if [ $d -lt $bestd ]; then bestd=$d; best=$pfx; fi
  done
  echo "$best"
}

n=0
while read -r EID AGE SEX; do
  [ -z "$EID" ] && continue
  case "$AGE" in 5|6|7|8|9|10|11|12) ;; *) continue ;; esac
  # require the CAST sweep dir + fs2mov bridge so the reference arm can reuse it
  [ -f "$DB/Validity/sweep/$EID/fs2mov_0GenericAffine.mat" ] || { echo "[skip no-fs2mov] $EID" >&2; continue; }
  NKI=$(nki_for "$AGE"); FON=$(fonov_for "$AGE")
  [ -z "$NKI" ] && { echo "[skip no-nki] $EID age$AGE" >&2; continue; }
  echo "$EID $AGE $SEX $NKI $FON" >> "$OUT"
  n=$((n+1))
done < "$SRC"
echo "[manifest] wrote $n lines -> $OUT"
echo "[manifest] array size = $n  (set --array=1-$n%50 in run_refbench.sbatch)"
