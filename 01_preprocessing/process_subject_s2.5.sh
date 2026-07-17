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
age=${2:-"10"}  # Default to age 10 if not specified
sex=${3:-"male"} # Default to male if not specified

# Construct the directory paths for Age/sex intensity_improved_formated structure
HOST_ROOT="${DB:-/path/to/cast_data}"
DATA_DIR="$HOST_ROOT/Age${age}/${sex}/intensity_improved_formated"
CCS_DIR="/mnt/Age${age}/${sex}/intensity_improved_formated"

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
    echo "Usage: $0 <subject_id> [age] [sex]"
    echo "  subject_id: ID of the subject to process (e.g., SUBJECT_ID)"
    echo "  age: Age group (e.g., '8', '10', '15', '20') - defaults to '10'"
    echo "  sex: male|female - defaults to 'male'"
    echo ""
    echo "Examples:"
    echo "  $0 SUBJECT_ID"
    echo "  $0 SUBJECT_ID 8 female"
    echo "  $0 SUBJECT_ID 10 male"
    exit 1
fi

# Create a lock file for the current subject to avoid conflicts with other jobs
lock_file="$UNIQUE_TEMP_DIR/${subject}.lock"
if [ ! -f "$lock_file" ]; then
    # Mark this subject as being processed
    touch "$lock_file"
    
    # Run Apptainer with the script for each subject
    apptainer exec --bind $UNIQUE_TEMP_DIR:/writabletemp --bind /share:/share --bind $HOST_ROOT:/mnt ${C_REG:-cast_reg.sif} \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                  export TMPDIR=/writabletemp && \
                  export PATH=/opt/ANTs/install/bin:\$PATH && \
                  export SUBJECTS_DIR=$CCS_DIR && \
                  export DEEP_BET_DIR=/usr/local/NHP-BrainExtraction && \
                  cd $CCS_APP/samplesScripts/ && \
                  /bin/bash /mnt/step2.5_uh_ped_temp_recenter.sh $CCS_DIR $SUBJECTS_DIR $subject"
    
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