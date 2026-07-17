#!/usr/bin/env bash
#SBATCH --job-name=gw-refbench
#SBATCH --output=gw-refbench-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --array=1-271%50
# HEAD-TO-HEAD VALIDITY BENCHMARK (NKI + Fonov vs CAST).
# One array task = one held-out test subject (ages 5-12). Registers the SAME
# subject (whose CAST matched-SyN result already lives in $DB/Validity/sweep/<EID>/)
# to the matched NKI reference AND the matched Fonov/NIHPD reference, warps the
# subject's FreeSurfer white surface into each reference space, and measures the
# gray-white interface distance there -> directly comparable to the CAST number.
#
# Manifest line: "<EID> <AGE> <SEX> <NKI_TPL_BASENAME> <FONOV_BAND_PREFIX>"
# Reuses sweep's fs2mov bridge, warp_surface_to_template.py, measure_cell.py.
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/refbench_manifest.txt

LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN")
[ -z "$LINE" ] && exit 0
read -r EID AGE SEX NKI_TPL FONOV_PFX <<< "$LINE"

OUTH=$DB/Validity/refbench/$EID
mkdir -p "$OUTH"

# resumable: skip if both reference measures already present
if [[ -s "$OUTH/meas_nki_syn.json" && -s "$OUTH/meas_fonov_syn.json" ]]; then
  echo "[skip-done] $EID"; exit 0
fi

# host-side: re-extract the csfNorm_rc intensity moving image from the tarball
# (identical source to the CAST sweep, so the moving->reference reg is on the
#  exact same subject image CAST used)
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
  /mnt/validity_heatmap_scripts/refbench_worker.sh "$EID" "$AGE" "$SEX" "$NKI_TPL" "$FONOV_PFX" "$NT"
