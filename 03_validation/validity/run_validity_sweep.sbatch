#!/usr/bin/env bash
#SBATCH --job-name=gw-sweep
#SBATCH --output=gw-sweep-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --array=1-319%60
# STEP 2 CENTERPIECE: at-scale gray-white validity sweep (Option B, surface metric).
# One task = one test subject. Matched template -> SyN; cross-sex template -> affine.
# Manifest line: "<EID> <AGE> <SEX>"
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/sweep_manifest.txt
LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN")
[ -z "$LINE" ] && exit 0
read -r EID AGE SEX <<< "$LINE"
OUTH=$DB/Validity/sweep/$EID
mkdir -p "$OUTH"
# resumable: skip if both matched-syn and cross-affine measures already present
if [[ -s "$OUTH/meas_matched_syn.json" && -s "$OUTH/meas_cross_affine.json" ]]; then
  echo "[skip-done] $EID"; exit 0
fi
# host-side: extract the csfNorm_rc intensity moving image from the tarball
TAR=$DB/TemplateTestSet/hbn_grouped_by_age/$AGE/$EID.tar.gz
if [[ ! -f "$OUTH/moving.nii.gz" ]]; then
  if [[ ! -f "$TAR" ]]; then echo "[ERR] no tarball $TAR"; exit 1; fi
  TMPX=$(mktemp -d)
  tar xzf "$TAR" -C "$TMPX" "$EID/subj_${EID}_csfNorm_rc.nii.gz" 2>/dev/null \
    || { echo "[ERR] no csfNorm_rc member in $TAR"; rm -rf "$TMPX"; exit 1; }
  cp -f "$TMPX/$EID/subj_${EID}_csfNorm_rc.nii.gz" "$OUTH/moving.nii.gz"
  rm -rf "$TMPX"
fi
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash /mnt/validity_heatmap_scripts/sweep_worker.sh "$EID" "$AGE" "$SEX" "$NT"
