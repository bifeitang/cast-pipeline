#!/usr/bin/env bash
#SBATCH --job-name=hbn-dc-one
#SBATCH --output=hbn-dc-one-%j.out
#SBATCH --error=hbn-dc-one-%j.err
#SBATCH --time=08:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=24G

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: sbatch sbatch_subject_dc.sh <subject_img_path> <eid> <age_int> [template_age] [template_sex]" >&2
  exit 1
fi

SUBJ_IMG="$1"
EID="$2"
AGE_INT="$3"
TPL_AGE="${4:-9}"
TEMPLATE_SEX="${5:-male}"

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
# Separate results by template age and sex to avoid collisions across templates
OUT_IN="/mnt/DeformationCost/NKI_template_age_${TPL_AGE}/${AGE_INT}/${EID}"

TPL_IN="/mnt/Templates/NKI_age${TPL_AGE}_brain_template.nii.gz"
TMASK_IN="/mnt/Templates/NKI_age${TPL_AGE}_brain_brain_mask.nii.gz"

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
                  --template-mask \"$TMASK_IN\" \
                  --outdir \"$OUT_IN\" \
                  --mode syn \
                  --normalize icv"

