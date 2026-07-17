#!/bin/bash

# Job scheduler directives (e.g., Slurm)
#SBATCH --job-name=mri-process
#SBATCH --output=mri-process-%j.out
#SBATCH --error=mri-process-%j.err
#SBATCH --time=50:00:00
#SBATCH --partition=standard
#SBATCH -N 1 
#SBATCH -n 4
#SBATCH --mem=8G

# Arguments
subject=$1
age=${2:-"Sample"}  # Default to Sample if not specified
gender=${3:-""}  # Default to empty if not specified
subfolder=${4:-""}  # Default to empty if not specified

# Construct the directory paths
if [ -z "$gender" ]; then
    # No gender specified, use the simple path without gender
    DATA_DIR="${DB:-/path/to/cast_data}/$age"
    CCS_DIR="/mnt/$age"
else
    # Gender and possibly subfolder specified
    if [ -z "$subfolder" ]; then
        # No subfolder, just age and gender
        DATA_DIR="${DB:-/path/to/cast_data}/$age/$gender"
        CCS_DIR="/mnt/$age/$gender"
    else
        # Full path with age, gender, and subfolder
        DATA_DIR="${DB:-/path/to/cast_data}/$age/$gender/$subfolder"
        CCS_DIR="/mnt/$age/$gender/$subfolder"
    fi
fi

# Define other directories
CCS_APP=/usr/local/CCS_APP
SUBJECTS_DIR=$CCS_DIR
FSLDIR=/usr/local/fsl

# Echo the paths that will be used
echo "Using DATA_DIR: $DATA_DIR"
echo "Using CCS_DIR: $CCS_DIR"

# Define a unique temporary directory for this job to avoid conflicts
UNIQUE_TEMP_DIR=${TMPROOT:-/tmp}/Temp_reverse_${subject}
mkdir -p $UNIQUE_TEMP_DIR

# Validate arguments
if [ -z "$subject" ]; then
    echo "Error: Subject ID is required"
    echo "Usage: $0 <subject_id> [age] [gender] [subfolder] [container]"
    echo "  subject_id: ID of the subject to process"
    echo "  age: Age group (e.g., 'Age9', 'Age10', 'Sample')"
    echo "  gender: Gender folder (e.g., 'male', 'female')"
    echo "  subfolder: Additional subfolder (e.g., 'formated')"
    echo ""
    echo "Examples:"
    echo "  $0 subj123"
    echo "  $0 subj123 Age9 male formated"
    echo "  $0 subj123 Age10 female"
    exit 1
fi

# Create a lock file for the current subject to avoid conflicts with other jobs
lock_file="$UNIQUE_TEMP_DIR/${subject}.lock"
if [ ! -f "$lock_file" ]; then
    # Mark this subject as being processed
    touch "$lock_file"
    
    # Run Apptainer with the script for each subject
    apptainer exec --bind $UNIQUE_TEMP_DIR:/writabletemp --bind /share:/share --bind ${DB:-/path/to/cast_data}:/mnt ${IMAGE_DIR:-/path/to/containers}/obsolete_container/${C_REG:-cast_reg.sif} \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                    export TMPDIR=/writabletemp &&\
                    export SUBJECTS_DIR=$CCS_DIR &&\
                    cd $CCS_APP/samplesScripts/ && \
                    /bin/sh /mnt/step2_uh_ped_temp_preprocess.sh $CCS_DIR $SUBJECTS_DIR $subject"
    
    # Check if container execution was successful
    if [ $? -eq 0 ]; then
        echo "Processing completed successfully for subject $subject"
    else
        echo "ERROR: Processing failed for subject $subject with exit code $?"
    fi
    
    # Clean up lock file after processing
    rm "$lock_file"
else
    echo "Subject $subject is already being processed."
fi