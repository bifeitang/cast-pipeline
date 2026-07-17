#!/bin/bash
# CAST — per-stratum template construction (generalized, parameterized form of the
# 30 as-run scripts in as_run/).  Builds one unbiased group-average template for a
# single age x sex cohort with ANTs antsMultivariateTemplateConstruction2.sh.
#
# Usage:   ./mri_template_construction.sh <age> <sex>
# Example: ./mri_template_construction.sh 9 male
#
# Override DB / C_REG / TMPROOT / NT in the environment or in ../config.sh.
#
#SBATCH --job-name=cast-tmpl
#SBATCH --output=cast-tmpl-%j.out
#SBATCH --error=cast-tmpl-%j.err
#SBATCH --time=10-30:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
set -euo pipefail

AGE="${1:?usage: $0 <age> <sex>}"
SEX="${2:?usage: $0 <age> <sex>}"

# --- configuration (defaults overridable via env or ../config.sh) ------------
DB="${DB:-/path/to/cast_data}"                            # data root (bound to /mnt)
C_REG="${C_REG:-cast_reg.sif}"                            # ANTs registration image
TMPROOT="${TMPROOT:-/tmp}"                                 # scratch root
NT="${NT:-16}"                                             # ITK/ANTs threads
FSLDIR="${FSLDIR:-/usr/local/fsl}"

# Preprocessed, CSF-anchored, selected-for-template inputs for this stratum.
INPUT_SUBDIR="Age${AGE}/${SEX}/intensity_improved_selected_for_template"
# Single in-stratum scan used to seed ANTs (-z); the exact reference subject for
# each published template is recorded in the data-deposit manifest, not here.
REF="${REF:-/mnt/${INPUT_SUBDIR}/REFERENCE_SUBJECT.nii.gz}"

UNIQUE_TEMP_DIR="${TMPROOT}/TemplateCreation_age${AGE}_${SEX}"
mkdir -p "$UNIQUE_TEMP_DIR"

# As-run ANTs invocation (identical across all 28 published strata):
#   SyN[0.1] transform, CC[2] metric, gradient step 0.10, 12 iterations,
#   4-level 8x4x2x1 / 4x2x1x0vox / 120x90x60x20 schedule, -n 0 (no per-iter N4,
#   preserves the CSF-anchored native tissue contrast set in preprocessing).
apptainer exec --bind "$UNIQUE_TEMP_DIR:/writabletemp" \
               --bind "${DB}:/mnt" \
               "$C_REG" \
  /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
    export TMPDIR=/writabletemp && \
    export PATH=\"\$PATH:/opt/ANTs/install/bin\" && \
    export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=${NT} && \
    cd /mnt/${INPUT_SUBDIR} && \
    antsMultivariateTemplateConstruction2.sh \
        -d 3 -o template0_ -i 12 \
        -z ${REF} -r 1 \
        -g 0.10 -c 0 -k 1 -w 1 -y 0 \
        -f 8x4x2x1 -s 4x2x1x0vox -q 120x90x60x20 \
        -l 0 \
        -t \"SyN[0.1]\" -m \"CC[2]\" \
        -n 0 -u 1 \
        /mnt/${INPUT_SUBDIR}/*.nii.gz"
