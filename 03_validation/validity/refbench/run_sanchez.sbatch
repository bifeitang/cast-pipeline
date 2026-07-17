#!/usr/bin/env bash
#SBATCH --job-name=gw-sanchez
#SBATCH --output=gw-sanchez-%A_%a.out
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --array=1-189%50
# WORKSTREAM B: add the Sanchez/Richards Neurodevelopmental MRI Database as a THIRD
# reference atlas to the held-out gray-white interface benchmark. One array task =
# one held-out test subject (ages 5-10, the Sanchez coverage overlap). Registers the
# SAME subject (whose CAST matched-SyN result already lives in Validity/sweep/<EID>/,
# and whose NKI/Fonov results live in Validity/refbench/<EID>/) to the matched Sanchez
# reference, warps the subject's FreeSurfer white surface into Sanchez space, and
# measures the symmetric ASSD there -> directly comparable to the CAST/NKI/Fonov rows.
#
# Manifest line: "<EID> <SUBJ_AGE> <TPL_AGE> <SEX> <SANCHEZ_TAG>"
# Reuses sweep's fs2mov bridge, warp_surface_to_template.py, measure_cell_assd.py.
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB=/project/contreras-vidal/Yang/PediatricMriDB
C=/project/contreras-vidal/Image/mri_template_env_reg.sif
SCR=$DB/validity_heatmap_scripts
MAN=$SCR/sanchez_manifest.txt

LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MAN")
[ -z "$LINE" ] && exit 0
read -r EID SUBJ_AGE TPL_AGE SEX SANCHEZ_TAG <<< "$LINE"

OUTH=$DB/Validity/refbench/$EID
mkdir -p "$OUTH"

# resumable: skip if the Sanchez measure is already present
if [[ -s "$OUTH/meas_sanchez_assd.json" ]]; then
  echo "[skip-done] $EID"; exit 0
fi

# host-side: re-extract the csfNorm_rc intensity moving image from the SAME tarball
# CAST/NKI/Fonov used, so the moving->Sanchez reg is on the exact same subject image.
TAR=$DB/TemplateTestSet/hbn_grouped_by_age/$TPL_AGE/$EID.tar.gz
if [[ ! -f "$OUTH/moving.nii.gz" ]]; then
  if [[ ! -f "$TAR" ]]; then echo "[ERR] no tarball $TAR"; exit 1; fi
  TMPX=$(mktemp -d)
  tar xzf "$TAR" -C "$TMPX" "$EID/subj_${EID}_csfNorm_rc.nii.gz" 2>/dev/null \
    || { echo "[ERR] no csfNorm_rc member in $TAR"; rm -rf "$TMPX"; exit 1; }
  cp -f "$TMPX/$EID/subj_${EID}_csfNorm_rc.nii.gz" "$OUTH/moving.nii.gz"
  rm -rf "$TMPX"
fi

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash \
  /mnt/validity_heatmap_scripts/sanchez_worker.sh \
  "$EID" "$SUBJ_AGE" "$TPL_AGE" "$SEX" "$SANCHEZ_TAG" "$NT"
