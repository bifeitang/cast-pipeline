#!/usr/bin/env bash
#SBATCH --job-name=cleandisp-val
#SBATCH --output=cleandisp-val-%j.out
#SBATCH --error=cleandisp-val-%j.err
#SBATCH --time=08:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G

set -euo pipefail

# Validate the SyN-only ("clean") displacement metric against the surviving 2025-11 values.
#
# Usage: sbatch sbatch_cleandisp_validate.sh <subject_img_path> <eid> <age_int> <tpl_age> <tpl_sex>
#
# WHY A SEPARATE WRAPPER, AND DO NOT "SIMPLIFY" THIS BACK INTO sbatch_test_set_dc.sh:
# that script writes to DeformationCost/test_set_dc/<tpl>/<age>/<eid>/, which still holds
# the ONLY surviving record of the 2025-11 generation -- the transforms were deleted by the
# storage cleanup, so those metrics.txt files cannot be regenerated. Running it would
# overwrite the very reference this job exists to check. Output therefore goes to a
# dedicated root that touches nothing else.
#
# Resource directives are copied verbatim from sbatch_test_set_dc.sh. In particular -n 8
# must not change: it sets ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS below, and ANTs is not
# bit-reproducible across thread counts, so altering it would confound "different metric"
# with "different threading" -- exactly the comparison this job is trying to make.

if [[ $# -lt 5 ]]; then
  echo "Usage: sbatch sbatch_cleandisp_validate.sh <subject_img_path> <eid> <age_int> <tpl_age> <tpl_sex>" >&2
  exit 1
fi

SUBJ_IMG="$1"
EID="$2"
AGE_INT="$3"
TPL_AGE="$4"
TEMPLATE_SEX="$5"

case "$TEMPLATE_SEX" in
  male|female) ;;
  *) echo "[ERROR] template_sex must be 'male' or 'female', got '$TEMPLATE_SEX'" >&2; exit 2;;
esac

export SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-8}
export FSLDIR=${FSLDIR:-/usr/local/fsl}

ROOT_DIR="/project/contreras-vidal/Yang"
DB_DIR="$ROOT_DIR/PediatricMriDB"
VAL_ROOT="$ROOT_DIR/CLEANDISP_VALIDATION_2026-07-27"
UNIQUE_TEMP_DIR="$ROOT_DIR/TemplateCreationTemp/${EID}_cdv_${SLURM_JOB_ID:-local}"
mkdir -p "$UNIQUE_TEMP_DIR" "$VAL_ROOT"

CONTAINER_IMAGE="/project/contreras-vidal/Image/mri_template_env_reg.sif"

SUBJ_IN="/mnt${SUBJ_IMG#$DB_DIR}"
TPL_ID="age${TPL_AGE}_${TEMPLATE_SEX}"

# Output OUTSIDE the DB bind, so there is no path under which this can land in test_set_dc.
OUT_HOST="$VAL_ROOT/${TPL_ID}/${AGE_INT}/${EID}"
mkdir -p "$OUT_HOST"

TPL_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_template.nii.gz"
TMASK_HOST="$DB_DIR/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"
TMASK_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"
TMASK_ARG=""
if [[ -f "$TMASK_HOST" ]]; then
  TMASK_ARG="--template-mask \"$TMASK_IN\""
fi

apptainer exec \
  --bind "$UNIQUE_TEMP_DIR:/writabletemp" \
  --bind "$DB_DIR:/mnt" \
  --bind "$OUT_HOST:/out" \
  "$CONTAINER_IMAGE" \
  /bin/bash -c "if [ -f ${FSLDIR}/etc/fslconf/fsl.sh ]; then . ${FSLDIR}/etc/fslconf/fsl.sh; fi; \
                export TMPDIR=/writabletemp; \
                export PATH=\"\$PATH:/opt/ANTs/install/bin\"; \
                export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK; \
                cd /mnt; \
                /bin/bash deformation_cost_scripts/cal_deformation_cost.sh \
                  --moving \"$SUBJ_IN\" \
                  --template \"$TPL_IN\" \
                  $TMASK_ARG \
                  --outdir /out \
                  --mode syn \
                  -disp-component syn"

# Keep only metrics.txt. Each job leaves ~1.2 GB of intermediates and the validation set is
# ~50 jobs, so this bounds the run at a few MB instead of ~60 GB. Safe to do inline here --
# unlike the fleet-wide sweep, this deletes only within THIS job's own freshly created
# directory, so it cannot race a concurrently running job (the bug that killed 20 jobs).
find "$OUT_HOST" -mindepth 1 ! -name metrics.txt -delete 2>/dev/null || true

echo "[done] $EID -> $OUT_HOST/metrics.txt"
