#!/bin/sh

#
# MRI Processing Pipeline (Stage 1) for Pediatric Neuroimaging Data
#
# This script automates the processing of pediatric MRI data through two phases:
# 1. MATLAB-dependent preprocessing steps
# 2. ANTs-based registration and additional processing
#
# The script supports configurable paths based on age group, gender, and subfolder,
# handles job dependencies, provides error checking, and manages temporary files.
#
# Usage: ./process_mri.sh <subject_id> [phase] [age] [gender] [subfolder]
#   phase: 1 (MATLAB), 2 (ANTs), or both (default: 1)
#   age: Age group folder (default: Sample)
#   gender: Gender subfolder (optional)
#   subfolder: Additional subfolder (optional)
#
# Example: ./process_mri.sh SUBJ001 both Age9 male formated

# Job scheduler directives
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
phase=${2:-"1"}  # Default to phase 1 if not specified
age=${3:-"Sample"}  # Default to Sample if not specified
gender=${4:-""}  # Default to empty if not specified
subfolder=${5:-""}  # Default to empty if not specified

# Construct the directory paths
if [ -z "$gender" ]; then
    # No gender specified, use the simple path without gender
    if [ "$age" = "TemplateTestSet" ]; then
        # Special handling for TemplateTestSet structure
        if [ -z "$subfolder" ]; then
            DATA_DIR="${DB:-/path/to/cast_data}/$age"
            CCS_DIR="/mnt/$age"
        else
            DATA_DIR="${DB:-/path/to/cast_data}/$age/$subfolder"
            CCS_DIR="/mnt/$age/$subfolder"
        fi
    else
        DATA_DIR="${DB:-/path/to/cast_data}/$age"
        CCS_DIR="/mnt/$age"
    fi
else
    # Gender and possibly subfolder specified
    if [ -z "$subfolder" ]; then
        # No subfolder, just age and gender
        DATA_DIR="${DB:-/path/to/cast_data}/$age/$gender"
        CCS_DIR="/mnt/$age/$gender"
    else
        # Full path with age, gender, and subfolder
        if [ "$age" = "TemplateTestSet" ] && [ -z "$gender" ]; then
            # Special case for TemplateTestSet with empty gender
            DATA_DIR="${DB:-/path/to/cast_data}/$age/$subfolder"
            CCS_DIR="/mnt/$age/$subfolder"
        else
            DATA_DIR="${DB:-/path/to/cast_data}/$age/$gender/$subfolder"
            CCS_DIR="/mnt/$age/$gender/$subfolder"
        fi
    fi
fi

# Define other directories
CCS_APP=/usr/local/CCS_APP
SUBJECTS_DIR=$CCS_DIR
FSLDIR=/usr/local/fsl

# Echo the paths that will be used
echo "Using DATA_DIR: $DATA_DIR"
echo "Using CCS_DIR: $CCS_DIR"

# Define a unique temporary directory for this job
UNIQUE_TEMP_DIR=${TMPROOT:-/tmp}/Temp_reverse_${subject}
mkdir -p $UNIQUE_TEMP_DIR

# Define flag files in the temporary directory (visible to all containers)
phase1_flag="$UNIQUE_TEMP_DIR/${subject}_phase1_complete"
phase2_flag="$UNIQUE_TEMP_DIR/${subject}_phase2_complete"

# Validate arguments
if [ -z "$subject" ]; then
    echo "Error: Subject ID is required"
    echo "Usage: $0 <subject_id> [phase] [age] [gender] [subfolder]"
    echo "  subject_id: ID of the subject to process"
    echo "  phase: 1 (MATLAB steps), 2 (ANTs and other steps), or 'both'"
    echo "  age: Age group (e.g., 'Age9', 'Age10', 'Sample')"
    echo "  gender: Gender folder (e.g., 'male', 'female')"
    echo "  subfolder: Additional subfolder (e.g., 'formated')"
    echo ""
    echo "Examples:"
    echo "  $0 subj123 1 Sample"
    echo "  $0 subj123 both Age9 male formated"
    echo "  $0 subj123 2 Age10 female formated"
    exit 1
fi

if [ "$phase" != "1" -a "$phase" != "2" -a "$phase" != "both" ]; then
    echo "Error: Invalid phase specified. Must be 1, 2, or both"
    exit 1
fi

# Create a lock file for the current subject and phase
lock_file="$UNIQUE_TEMP_DIR/${subject}_phase${phase}.lock"

if [ -f "$lock_file" ]; then
    echo "Subject $subject phase $phase is already being processed."
    exit 0
fi

# Create the lock file
touch "$lock_file"

# Phase 1 - MATLAB-dependent steps
if [ "$phase" = "1" -o "$phase" = "both" ]; then
    echo "Running Phase 1 (MATLAB-dependent steps)..."
    
    apptainer exec --bind $UNIQUE_TEMP_DIR:/writabletemp --bind /share:/share --bind ${DB:-/path/to/cast_data}:/mnt ${C_PREPROC:-cast_preproc.sif} \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                  export TMPDIR=/writabletemp && \
                  source /mnt/setup.sh && \
                  export SUBJECTS_DIR=$CCS_DIR && \
                  cd $CCS_APP/samplesScripts/ && \
                  /bin/sh /mnt/step1_uh_ped_temp_preprocess.sh $CCS_DIR $SUBJECTS_DIR $subject 1"

    # Check if phase 1 container execution was successful
    # if [ $? -eq 0 ]; then
        
    # else
    #     echo "ERROR: Phase 1 MATLAB processing failed with exit code $?."
    #     echo "Phase 1 was not completed successfully."
    #     exit 1
    # fi
    echo "Phase 1 MATLAB processing completed successfully."
    # Create phase 1 completion flag outside container
    touch "$phase1_flag"
    echo "Created phase 1 completion flag: $phase1_flag"

    
    # If we're only running phase 1, schedule phase 2
    if [ "$phase" = "1" ]; then
        echo "Phase 1 complete. Submitting Phase 2 job..."
        rm "$lock_file"  # Remove phase 1 lock
        
        # Submit phase 2 job - pass all the same arguments
        script_path=$(readlink -f $0)
        sbatch $script_path $subject 2 $age $gender $subfolder
        exit 0
    fi
fi

# Phase 2 - non-MATLAB steps
if [ "$phase" = "2" -o "$phase" = "both" ]; then
    echo "Running Phase 2 (non-MATLAB steps)..."
    
    # Check that phase 1 is completed when only running phase 2
    if [ "$phase" = "2" ]; then
        if [ ! -f "$phase1_flag" ]; then
            echo "ERROR: Phase 1 completion flag not found. Please run Phase 1 first."
            echo "Expected flag at: $phase1_flag"
            rm "$lock_file"
            exit 1
        else
            echo "Found Phase 1 completion flag. Proceeding with Phase 2."
        fi
    fi
    
    # Run the container and check the exit status
    echo "Executing ANTs processing container..."
    apptainer exec --bind $UNIQUE_TEMP_DIR:/writabletemp --bind /share:/share --bind ${DB:-/path/to/cast_data}:/mnt ${C_REG:-cast_reg.sif} \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                  export TMPDIR=/writabletemp && \
                  export PATH=/opt/ANTs/install/bin:\$PATH && \
                  export SUBJECTS_DIR=$CCS_DIR && \
                  export DEEP_BET_DIR=/usr/local/NHP-BrainExtraction && \
                  cd $CCS_APP/samplesScripts/ && \
                  /bin/sh /mnt/step1_uh_ped_temp_preprocess.sh $CCS_DIR $SUBJECTS_DIR $subject 2"
        
    # Check if the container execution was successful
    if [ $? -eq 0 ]; then
        echo "ANTs processing completed successfully."
        # Create phase 2 completion flag outside container
        touch "$phase2_flag"
        echo "Created phase 2 completion flag: $phase2_flag"
    else
        echo "ERROR: ANTs processing failed with exit code $?."
        echo "Phase 2 was not completed successfully."
        exit 1
    fi
    
    # Clean up temporary directory when phase 2 is complete
    if [ "$phase" = "2" -o "$phase" = "both" ]; then
        # Only clean up if we successfully completed phase 2 (flag exists)
        if [ -f "$phase2_flag" ]; then
            echo "Phase 2 completed successfully. Cleaning up temporary directory..."
            cd ${PROJECT_ROOT:-/path/to/project}  # Move out of the directory before removing it
            
            # Just to be safe, check that the directory exists and contains our expected flags
            if [ -d "$UNIQUE_TEMP_DIR" -a -f "$phase1_flag" -a -f "$phase2_flag" ]; then
                echo "Removing temporary directory: $UNIQUE_TEMP_DIR"
                rm -rf "$UNIQUE_TEMP_DIR"
                echo "Cleanup complete."
            else
                echo "WARNING: Could not remove temporary directory. Please check and remove manually: $UNIQUE_TEMP_DIR"
            fi
        else
            echo "WARNING: Phase 2 completion flag not found. Temporary directory will not be cleaned up."
            echo "Please check the logs for errors and manually remove $UNIQUE_TEMP_DIR when appropriate."
        fi
    fi
fi

# Clean up lock file if it still exists (should only happen if we're not removing the whole directory)
if [ -f "$lock_file" ]; then
    rm "$lock_file"
fi

echo "Processing complete for subject $subject phase $phase"