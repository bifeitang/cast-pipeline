#!/bin/bash

# SBATCH script to compute tissue volumes for a single subject using apptainer.
#
# Usage: sbatch process_subject_volumes.sh <subject_id> <age> <sex>
#
# Arguments:
#   subject_id: Subject directory name (e.g., SUBJECT_ID)
#   age: Age number (e.g., 5, 10, 18)
#   sex: male or female

#SBATCH --job-name=tissue-vol
#SBATCH --output=tissue-vol-%j.out
#SBATCH --error=tissue-vol-%j.err
#SBATCH --time=1:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --mem=4G

# Arguments
subject=$1
age=${2:-"10"}
sex=${3:-"male"}

# Validate arguments
if [ -z "$subject" ]; then
    echo "Error: Subject ID is required"
    echo "Usage: $0 <subject_id> <age> <sex>"
    echo "  subject_id: ID of the subject to process (e.g., SUBJECT_ID)"
    echo "  age: Age group number (e.g., 5, 10, 18)"
    echo "  sex: male or female"
    exit 1
fi

# Paths
HOST_ROOT="${DB:-/path/to/cast_data}"
CONTAINER="${C_REG:-cast_reg.sif}"
SCRIPTS_DIR="${HOST_ROOT}/tissue_volume_scripts"
RESULTS_DIR="${HOST_ROOT}/tissue_volume_results/per_subject"

# Container paths
CCS_DIR="/mnt/Age${age}/${sex}/intensity_improved_formated"
FSLDIR=/usr/local/fsl

# Output file
OUT_CSV="${RESULTS_DIR}/Age${age}_${sex}_${subject}.csv"

# Echo configuration
echo "=========================================="
echo "Tissue Volume Computation"
echo "=========================================="
echo "Subject: $subject"
echo "Age: $age"
echo "Sex: $sex"
echo "Container SUBJECTS_DIR: $CCS_DIR"
echo "Output CSV: $OUT_CSV"
echo "=========================================="

# Check if subject directory exists
SUBJECT_DIR="${HOST_ROOT}/Age${age}/${sex}/intensity_improved_formated/${subject}"
if [ ! -d "$SUBJECT_DIR" ]; then
    echo "ERROR: Subject directory not found: $SUBJECT_DIR"
    exit 1
fi

# Check if aseg.mgz exists
ASEG_FILE="${SUBJECT_DIR}/mri/aseg.mgz"
if [ ! -f "$ASEG_FILE" ]; then
    echo "ERROR: aseg.mgz not found: $ASEG_FILE"
    exit 1
fi

# Create unique temp directory
UNIQUE_TEMP_DIR="${HOST_ROOT}/Temp_tissue_vol_${subject}"
mkdir -p "$UNIQUE_TEMP_DIR"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Lock file to prevent duplicate processing
lock_file="${UNIQUE_TEMP_DIR}/${subject}.lock"
if [ -f "$lock_file" ]; then
    echo "Subject $subject is already being processed."
    exit 0
fi
touch "$lock_file"

# Run apptainer with the inner script
echo "Starting apptainer execution..."
apptainer exec \
    --bind "$UNIQUE_TEMP_DIR:/writabletemp" \
    --bind "${HOST_ROOT}:/mnt" \
    "$CONTAINER" \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                  export TMPDIR=/writabletemp && \
                  export SUBJECTS_DIR=${CCS_DIR} && \
                  /bin/bash /mnt/tissue_volume_scripts/compute_tissue_volumes_inner.sh \
                      '$subject' '$age' '$sex' '/mnt/tissue_volume_results/per_subject/Age${age}_${sex}_${subject}.csv'"

# Check exit status
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "Processing completed successfully for subject $subject"
else
    echo "ERROR: Processing failed for subject $subject with exit code $exit_code"
fi

# Clean up
rm -f "$lock_file"
rmdir "$UNIQUE_TEMP_DIR" 2>/dev/null || true

echo "Done."
exit $exit_code
