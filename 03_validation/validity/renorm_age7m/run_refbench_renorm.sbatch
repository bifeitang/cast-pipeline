#!/usr/bin/env bash
#SBATCH --job-name=gw-renorm7m
#SBATCH --output=gw-renorm7m-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --array=1-35%35
# WM-CONTRAST RESTORATION re-benchmark array (age7_male stratum, 35 held-out subj).
# One task = one held-out subject re-registered (moving=csfNorm_rc, fs2mov bridge
# reused from the CAST sweep) to the WM-contrast-RESTORED 0.8 mm age7_male template
# (Weber 0.277 -> 0.393, NKI-matched). Warps the FreeSurfer white surface and
# measures gray-white interface error against the PUBLISHED age7_male 0.8 mm WM
# mask -- emitting the SAME fields (full_median_mm / cort_median_mm) as the
# published CAST_0.8 / NKI_0.8 numbers so the recovered fraction of the gap is
# directly comparable. 8c/16G, 1:30 walltime (one 0.8 mm SyN per task; slow).
#
# Manifest line: "<EID> <AGE> <SEX>"  (age7_male only)
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/refbench_renorm_age7m_manifest.txt

LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN")
[ -z "$LINE" ] && exit 0
read -r EID AGE SEX <<< "$LINE"

OUTH=$DB/Validity/refbench_renorm_age7m/$EID
mkdir -p "$OUTH"

# resumable: skip if the renorm measure already present
if [[ -s "$OUTH/meas_castRN.json" ]]; then
  echo "[skip-done] $EID"; exit 0
fi

# host-side: re-extract the csfNorm_rc moving image (identical source to the CAST
# sweep / published refbench / CAST-0.8 arm)
TAR=$DB/TemplateTestSet/hbn_grouped_by_age/$AGE/$EID.tar.gz
if [[ ! -f "$OUTH/moving.nii.gz" ]]; then
  if [[ ! -f "$TAR" ]]; then echo "[ERR] no tarball $TAR"; exit 1; fi
  TMPX=$(mktemp -d)
  tar xzf "$TAR" -C "$TMPX" "$EID/subj_${EID}_csfNorm_rc.nii.gz" 2>/dev/null \
    || { echo "[ERR] no csfNorm_rc member in $TAR"; rm -rf "$TMPX"; exit 1; }
  cp -f "$TMPX/$EID/subj_${EID}_csfNorm_rc.nii.gz" "$OUTH/moving.nii.gz"
  rm -rf "$TMPX"
fi

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash \
  /mnt/validity_heatmap_scripts/refbench_renorm_worker.sh "$EID" "$AGE" "$SEX" "$NT"
