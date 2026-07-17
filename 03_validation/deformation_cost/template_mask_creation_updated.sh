#!/usr/bin/env bash
#SBATCH --job-name=mri-template-mask-updated
#SBATCH --output=mri-template-mask-updated-%j.out
#SBATCH --error=mri-template-mask-updated-%j.err
#SBATCH --time=30:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=32G

set -euo pipefail

SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-4}
FSLDIR=${FSLDIR:-/usr/local/fsl}

ROOT_DIR="${PROJECT_ROOT:-/path/to/project}"
DB_DIR="$ROOT_DIR/PediatricMriDB"
TEMPLATE_DIR="$DB_DIR/Templates/UpdatedTemplates"
CONTAINER_IMAGE="${C_REG:-cast_reg.sif}"

# Define a unique temporary directory for this job to avoid conflicts
UNIQUE_TEMP_DIR="$ROOT_DIR/TemplateMaskCreationTemp"
mkdir -p "$UNIQUE_TEMP_DIR"

# Default template list - ages 6,7,8,9,11,12,13,14 male and female
TEMPLATES=(
  "$TEMPLATE_DIR/age6_female_template.nii.gz"
  "$TEMPLATE_DIR/age6_male_template.nii.gz"
  "$TEMPLATE_DIR/age7_female_template.nii.gz"
  "$TEMPLATE_DIR/age7_male_template.nii.gz"
  "$TEMPLATE_DIR/age8_female_template.nii.gz"
  "$TEMPLATE_DIR/age8_male_template.nii.gz"
  "$TEMPLATE_DIR/age9_female_template.nii.gz"
  "$TEMPLATE_DIR/age9_male_template.nii.gz"
  "$TEMPLATE_DIR/age11_female_template.nii.gz"
  "$TEMPLATE_DIR/age11_male_template.nii.gz"
  "$TEMPLATE_DIR/age12_female_template.nii.gz"
  "$TEMPLATE_DIR/age12_male_template.nii.gz"
  "$TEMPLATE_DIR/age13_female_template.nii.gz"
  "$TEMPLATE_DIR/age13_male_template.nii.gz"
  "$TEMPLATE_DIR/age14_female_template.nii.gz"
  "$TEMPLATE_DIR/age14_male_template.nii.gz"
)

# If user passes templates as args, use those instead
if (( $# > 0 )); then
  TEMPLATES=("$@")
fi

apptainer exec --bind "$UNIQUE_TEMP_DIR:/writabletemp" --bind "$DB_DIR:/mnt" "$CONTAINER_IMAGE" \
  /bin/bash -c "if [ -f ${FSLDIR}/etc/fslconf/fsl.sh ]; then . ${FSLDIR}/etc/fslconf/fsl.sh; fi; \
                export TMPDIR=/writabletemp; \
                export PATH=\"\$PATH:/opt/ANTs/install/bin\"; \
                export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK; \
                /bin/bash /mnt/deformation_cost_scripts/compute_template_masks.sh ${TEMPLATES[*]//"$DB_DIR"/\/mnt}"
