#!/usr/bin/env bash
#SBATCH --job-name=hbn-dc-updated
#SBATCH --output=hbn-dc-updated-%j.out
#SBATCH --error=hbn-dc-updated-%j.err
#SBATCH --time=08:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: sbatch sbatch_subject_dc_updated_templates.sh <subject_img_path> <eid> <age_int> [template_age] [template_sex]" >&2
  exit 1
fi

SUBJ_IMG="$1"
EID="$2"
AGE_INT="$3"
TPL_AGE="${4:-5}"
TEMPLATE_SEX="${5:-female}"

case "$TEMPLATE_SEX" in
  male|female) ;;
  *) echo "[ERROR] template_sex must be 'male' or 'female', got '$TEMPLATE_SEX'" >&2; exit 2;;
esac

export SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-8}
export FSLDIR=${FSLDIR:-/usr/local/fsl}

ROOT_DIR="${PROJECT_ROOT:-/path/to/project}"
DB_DIR="$ROOT_DIR/PediatricMriDB"
UNIQUE_TEMP_DIR="$ROOT_DIR/TemplateCreationTemp/${EID}_${SLURM_JOB_ID:-local}"
mkdir -p "$UNIQUE_TEMP_DIR"

CONTAINER_IMAGE="${C_REG:-cast_reg.sif}"

# Map subject image path into container under /mnt
SUBJ_IN="/mnt${SUBJ_IMG#$DB_DIR}"
# Separate results by template id to avoid collisions across templates
TPL_ID="age${TPL_AGE}_${TEMPLATE_SEX}"
# Rerun results go here (requested):
#   PediatricMriDB/DeformationCost/new_template_and_deformation_cal/<tpl>/<age>/<eid>/
OUT_IN="/mnt/DeformationCost/new_template_and_deformation_cal/${TPL_ID}/${AGE_INT}/${EID}"

TPL_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_template.nii.gz"
TMASK_HOST="$DB_DIR/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"
TMASK_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"
TMASK_ARG=""
if [[ -f "$TMASK_HOST" ]]; then
  TMASK_ARG="--template-mask \"$TMASK_IN\""
fi

apptainer exec --bind "$UNIQUE_TEMP_DIR:/writabletemp" --bind "$DB_DIR:/mnt" "$CONTAINER_IMAGE" \
  /bin/bash -c "if [ -f ${FSLDIR}/etc/fslconf/fsl.sh ]; then . ${FSLDIR}/etc/fslconf/fsl.sh; fi; \
                export TMPDIR=/writabletemp; \
                export PATH=\"\$PATH:/opt/ANTs/install/bin\"; \
                export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK; \
                cd /mnt; \
                mkdir -p \"$OUT_IN\"; \
                /bin/bash deformation_cost_scripts/cal_deformation_cost.sh \
                  --moving \"$SUBJ_IN\" \
                  --template \"$TPL_IN\" \
                  $TMASK_ARG \
                  --outdir \"$OUT_IN\" \
                  --mode syn"
