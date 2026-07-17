#!/usr/bin/env bash
#SBATCH --job-name=gw-refbench0p8
#SBATCH --output=gw-refbench0p8-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --array=1-144%50
# RESOLUTION-ARTIFACT CONTROL re-benchmark array. One task = one held-out subject
# whose matched CAST template was regridded to 0.8 mm. Re-registers the SAME
# subject (moving = csfNorm_rc, fs2mov bridge reused from the CAST sweep) to the
# 0.8 mm CAST template (and, grid-neutral control, the 0.8 mm NKI template),
# warps the FreeSurfer white surface, and measures gray-white interface error
# against the 0.8 mm WM masks -- emitting the SAME fields as the published
# benchmark so the gap can be re-evaluated at a matched 0.8 mm grid.
#
# Manifest line: "<EID> <AGE> <SEX> <NKI_TPL_BASENAME>"
# Right-sized like run_refbench.sbatch: 8c/16G, ~0:45 (2 SyN regs/subject), %50.
# NOTE: set --array=1-N%50 to the line count printed by build_refbench0p8_manifest.sh.
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/refbench0p8_manifest.txt

LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN")
[ -z "$LINE" ] && exit 0
read -r EID AGE SEX NKI_TPL <<< "$LINE"

OUTH=$DB/Validity/refbench_0p8/$EID
mkdir -p "$OUTH"

# resumable: skip if both CAST-0.8 and NKI-0.8 measures already present
if [[ -s "$OUTH/meas_cast0p8.json" && -s "$OUTH/meas_nki0p8.json" ]]; then
  echo "[skip-done] $EID"; exit 0
fi

# host-side: re-extract the csfNorm_rc moving image (identical source to the CAST
# sweep and to the published refbench)
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
  /mnt/validity_heatmap_scripts/refbench0p8_worker.sh "$EID" "$AGE" "$SEX" "$NKI_TPL" "$NT"
