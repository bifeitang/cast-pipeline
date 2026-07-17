#!/usr/bin/env bash
#SBATCH --job-name=tiss-jac
#SBATCH --output=tiss-jac-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --array=1-96%48
# Tissue-specific Jacobian (section 4.3, Mayerich M9) over a balanced subject subset.
# Manifest line: "<EID> <AGE> <SEX>"
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
MAN=$DB/validity_heatmap_scripts/jac_subset_manifest.txt
LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN"); [ -z "$LINE" ] && exit 0
read -r EID AGE SEX <<< "$LINE"
OUTH=$DB/Validity/tissue_jac/$EID; mkdir -p "$OUTH"
OUTJSON=$OUTH/tissue_jac.json
[ -s "$OUTJSON" ] && { echo "[skip-done] $EID"; exit 0; }
TAR=$DB/TemplateTestSet/hbn_grouped_by_age/$AGE/$EID.tar.gz
if [[ ! -f "$OUTH/moving.nii.gz" ]]; then
  [ -f "$TAR" ] || { echo "[ERR] no tarball $TAR"; exit 1; }
  TMPX=$(mktemp -d)
  tar xzf "$TAR" -C "$TMPX" "$EID/subj_${EID}_csfNorm_rc.nii.gz" 2>/dev/null || { echo "[ERR] no member"; rm -rf "$TMPX"; exit 1; }
  cp -f "$TMPX/$EID/subj_${EID}_csfNorm_rc.nii.gz" "$OUTH/moving.nii.gz"; rm -rf "$TMPX"
fi
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash /mnt/validity_heatmap_scripts/tissue_jacobian_worker.sh "$EID" "$AGE" "$SEX" "$NT" > "$OUTJSON" 2>"$OUTH/tissue_jac.err"
[ -s "$OUTJSON" ] && echo "[ok] $EID" || echo "[FAIL] $EID"
