#!/usr/bin/env bash
#SBATCH --job-name=nki-morph
#SBATCH --output=nki-morph-%j.out
#SBATCH --error=nki-morph-%j.err
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --mem=6G
#SBATCH --time=00:40:00
# NKI reference-template morphometry (same FAST method as the CAST templates) for the
# DD-F4 quality comparison. NKI templates are brain-extracted -> mask derived.
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
T=/mnt/Templates
SCR=/mnt/validity_heatmap_scripts
OUTH=$DB/tissue_volume_results/nki_morphometry
mkdir -p "$OUTH"
OUT=/mnt/tissue_volume_results/nki_morphometry
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c '
  . /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null
  : > '"$OUT"'/nki_morphometry.jsonl
  for a in 7 8 9 10 11 12 13 14 15 17; do
    tpl='"$T"'/NKI_age${a}_brain_template.nii.gz
    [ -f "$tpl" ] || { echo "[skip] NKI_age${a}"; continue; }
    python3 '"$SCR"'/template_morphometry.py "$tpl" '"$OUT"' "NKI_age${a}" >> '"$OUT"'/nki_morphometry.jsonl 2>>'"$OUT"'/err.log \
      && echo "[done] NKI_age${a}" || echo "[FAIL] NKI_age${a}"
  done
  echo "rows: $(wc -l < '"$OUT"'/nki_morphometry.jsonl)"'
