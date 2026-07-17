#!/usr/bin/env bash
#SBATCH --job-name=sgnheat
#SBATCH --output=sgnheat-%j.out
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
# Per-stratum SIGNED-bias gray-white heatmap (CAST 0.8mm), using the retained 0.8mm
# warped subject surfaces. Emits *_signedbias_heatmap.nii.gz via the extended aggregator.
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s <<'INNER'
set -uo pipefail
DB=/mnt; SCR=$DB/validity_heatmap_scripts
AGG=$SCR/validity_heatmap_aggregate_surf.py
TPL=$DB/Templates/UpdatedTemplates_0p8
OUT=$DB/Validity/refbench_0p8/signed_heatmaps; mkdir -p "$OUT"
for STR in age7_male age9_female; do
  AGE=$(echo $STR | sed 's/age//; s/_.*//'); SEX=$(echo $STR | sed 's/.*_//')
  WM=$TPL/${STR}_wm.nii.gz
  SURFS=""
  for EID in $(cat $SCR/assd/stratum_${STR}.txt); do
    f=$DB/Validity/refbench_0p8/$EID/surf_cast0p8.npz
    [ -f "$f" ] && SURFS="$SURFS $f"
  done
  echo "[$STR] WM=$WM  n_surf=$(echo $SURFS | wc -w)"
  CORTICAL_CUT_MM=6.0 python3 "$AGG" syn "$WM" "$OUT/${STR}_cast0p8" $SURFS
done
echo "[done] -> $OUT"
ls -la $OUT/*_signedbias_heatmap.nii.gz
INNER
