#!/usr/bin/env bash
#SBATCH --job-name=dc-trans
#SBATCH --output=dc-trans-%j.out
#SBATCH --error=dc-trans-%j.err
#SBATCH --time=08:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G

set -uo pipefail

# Deformation cost on the CSF-normalised INTENSITY images, emitting BOTH components.
#
# PURPOSE (2026-07-29). Identical to sbatch_dc_intensity.sh except for the output root.
# It exists to rebuild the translation-artifact panel, which plots the composite
# affine o SyN cost against the clean SyN-only cost. The 2026-07-27 run could not feed that
# panel: it wrote only the SyN-only displacement, and its transforms were deleted, so the
# composite was unrecoverable.
#
# cal_deformation_cost.sh now emits mean/median/p95_disp_total_mm from the composed field,
# which -disp-component syn already builds for the Jacobian. So a single registration yields
# both numbers, and both describe the SAME registration -- the published panel paired rows
# from two separately-run tables, where one point could mix two registrations of a subject.
#
# The mask-era panel it replaces was drawn from *_processed_centered.nii.gz, i.e. binary
# brain masks; see below.
#

# WHY THIS REPLACES sbatch_test_set_dc.sh FOR THE REBUILD
# The original ran on TemplateTestSet/hbn_grouped_by_age/<age>/processed_centered/
# *_processed_centered.nii.gz. Those files are BINARY BRAIN MASKS -- 2 unique values,
# {0,1} -- registered against greyscale intensity templates (1.3M unique values). Verified
# on four subjects across four ages, and consistent with all 353 files being under 500 KB.
# antsRegistrationSyN's CC metric would key almost entirely on the brain outline, leaving
# the interior regularisation-driven rather than data-driven. Author confirmed 2026-07-27
# that this was an input-selection error, not a deliberate shape-cost design.
#
# This wrapper uses subj_<EID>_csfNorm_rc.nii.gz, the same CSF-normalised intensity image
# the tissue-Jacobian pipeline used all along, sourced from:
#   272 subjects  the per-subject tarball hbn_grouped_by_age/<age>/<EID>.tar.gz
#    47 subjects  RECENTERED_MISSING47_2026-07-27/ (regenerated; they have no tarball)
#
# Also passes -disp-component syn so mean_disp_mm is the translation-free displacement the
# age-by-age figure needs. The Jacobian still comes from the composed field -- see
# cal_deformation_cost.sh, where mixing those two was caught and fixed.
#
# Output goes to its own root. test_set_dc still holds the only surviving record of the
# 2025-11 generation and must not be written to.
#
# Usage: sbatch sbatch_dc_intensity.sh <eid> <subject_age> <tpl_age> <tpl_sex>

if [[ $# -lt 4 ]]; then
  echo "Usage: sbatch sbatch_dc_intensity.sh <eid> <subject_age> <tpl_age> <tpl_sex>" >&2
  exit 1
fi

EID="$1"; AGE_INT="$2"; TPL_AGE="$3"; TEMPLATE_SEX="$4"
case "$TEMPLATE_SEX" in male|female) ;; *) echo "[ERR] tpl_sex must be male|female" >&2; exit 2;; esac

export SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-8}
export FSLDIR=${FSLDIR:-/usr/local/fsl}

ROOT_DIR="/project/contreras-vidal/Yang"
DB_DIR="$ROOT_DIR/PediatricMriDB"
HBN="$DB_DIR/TemplateTestSet/hbn_grouped_by_age"
RC47="$ROOT_DIR/RECENTERED_MISSING47_2026-07-27"
OUT_ROOT="${DC_OUT_ROOT:-$ROOT_DIR/DC_TRANSLATION_2026-07-29}"
STAGE="$ROOT_DIR/TemplateCreationTemp/${EID}_dct_${SLURM_JOB_ID:-local}"
CONTAINER_IMAGE="/project/contreras-vidal/Image/mri_template_env_reg.sif"

TPL_ID="age${TPL_AGE}_${TEMPLATE_SEX}"
OUT_HOST="$OUT_ROOT/${TPL_ID}/${AGE_INT}/${EID}"
mkdir -p "$STAGE" "$OUT_HOST"
trap 'rm -rf "$STAGE"' EXIT

# ---- stage the intensity image ------------------------------------------------------
MOV="$STAGE/moving.nii.gz"
if [[ -s "$RC47/subj_${EID}_csfNorm_rc.nii.gz" ]]; then
  cp -f "$RC47/subj_${EID}_csfNorm_rc.nii.gz" "$MOV"
else
  TAR="$(ls "$HBN"/*/"${EID}".tar.gz 2>/dev/null | head -1)"
  if [[ -z "$TAR" ]]; then echo "[ERR] $EID: no tarball and no recentred image" >&2; exit 3; fi
  tar xzf "$TAR" -C "$STAGE" "${EID}/subj_${EID}_csfNorm_rc.nii.gz" 2>/dev/null \
    || { echo "[ERR] $EID: csfNorm_rc not in tarball" >&2; exit 4; }
  mv "$STAGE/${EID}/subj_${EID}_csfNorm_rc.nii.gz" "$MOV"
fi

# Refuse to proceed on a binary image -- that is the exact bug this rerun exists to undo,
# and it must fail loudly rather than silently reproduce the old result.
NUNIQ=$(apptainer exec --bind "$STAGE:/stage" "$CONTAINER_IMAGE" \
        /bin/bash -c "export PATH=\$PATH:/opt/ANTs/install/bin; \
                      ImageMath 3 /dev/null Byte /stage/moving.nii.gz >/dev/null 2>&1; \
                      fslstats /stage/moving.nii.gz -R" 2>/dev/null | awk '{print $2}')
case "$NUNIQ" in
  1.0*|1) echo "[ERR] $EID: moving image max=1 -- looks binary, refusing" >&2; exit 5;;
esac

TPL_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_template.nii.gz"
TMASK_HOST="$DB_DIR/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"
TMASK_ARG=""
[[ -f "$TMASK_HOST" ]] && TMASK_ARG="--template-mask \"/mnt/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz\""

apptainer exec --bind "$STAGE:/writabletemp" --bind "$DB_DIR:/mnt" --bind "$OUT_HOST:/out" \
  "$CONTAINER_IMAGE" \
  /bin/bash -c "if [ -f ${FSLDIR}/etc/fslconf/fsl.sh ]; then . ${FSLDIR}/etc/fslconf/fsl.sh; fi; \
                export TMPDIR=/writabletemp; \
                export PATH=\"\$PATH:/opt/ANTs/install/bin\"; \
                export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK; \
                cd /mnt; \
                /bin/bash deformation_cost_scripts/cal_deformation_cost.sh \
                  --moving /writabletemp/moving.nii.gz \
                  --template \"$TPL_IN\" \
                  $TMASK_ARG \
                  --outdir /out \
                  --mode syn \
                  -disp-component syn"

# keep only metrics.txt (451 B); intermediates are ~1.2 GB per job
find "$OUT_HOST" -mindepth 1 ! -name metrics.txt -delete 2>/dev/null || true
echo "[done] $EID -> $OUT_HOST/metrics.txt"
