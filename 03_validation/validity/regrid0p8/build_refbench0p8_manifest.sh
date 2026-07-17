#!/bin/bash
# build_refbench0p8_manifest.sh
# Emit the 0.8mm re-benchmark manifest: every held-out subject (ages 5-12) whose
# MATCHED CAST template is one of the SEVEN regridded-to-0.8mm strata
# (age5_male, age6_female, age7_male, age8_male, age8_female, age9_female,
#  age10_female). Pulled from the authoritative refbench_manifest.txt so the
# NKI mapping column is carried through verbatim for the grid-neutral control.
#
# Manifest line: "<EID> <AGE> <SEX> <NKI_TPL_BASENAME>"
# (Fonov is not regridded here; CAST-0.8 vs NKI-0.8 is the grid-matched contrast.)
# Requires the CAST sweep fs2mov bridge to exist (re-registration reuses it).
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
SRC=$DB/validity_heatmap_scripts/refbench_manifest.txt
OUT=$DB/validity_heatmap_scripts/refbench0p8_manifest.txt
: > "$OUT"

# (age,sex) pairs whose CAST template was regridded to 0.8 mm.
is_affected() { # $1=age $2=sex
  case "$1:$2" in
    5:male|6:female|7:male|8:male|8:female|9:female|10:female) return 0 ;;
    *) return 1 ;;
  esac
}

n=0
while read -r EID AGE SEX NKI FON; do
  [ -z "$EID" ] && continue
  is_affected "$AGE" "$SEX" || continue
  [ -f "$DB/Validity/sweep/$EID/fs2mov_0GenericAffine.mat" ] || { echo "[skip no-fs2mov] $EID" >&2; continue; }
  echo "$EID $AGE $SEX $NKI" >> "$OUT"
  n=$((n+1))
done < "$SRC"
echo "[manifest] wrote $n lines -> $OUT"
echo "[manifest] array size = $n  (set --array=1-$n%50 in run_refbench0p8.sbatch)"
echo "[manifest] age_sex breakdown:"
awk '{print $2"_"$3}' "$OUT" | sort | uniq -c
