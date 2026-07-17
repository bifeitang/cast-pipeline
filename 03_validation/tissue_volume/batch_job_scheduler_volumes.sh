#!/bin/bash

# Batch job scheduler to submit tissue volume computation jobs for all subjects
# across all ages (5-18) and both sexes (male, female).
#
# Usage:
#   ./batch_job_scheduler_volumes.sh [--ages "5-18"] [--sexes "male,female"] [--dry-run]
#
# Options:
#   --ages: Age range or comma-separated list (default: "5-18")
#   --sexes: Comma-separated sexes (default: "male,female")
#   --dry-run: Print commands without executing

set -euo pipefail

# Defaults
AGES_SPEC="5-18"
SEXES="male,female"
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ages)
            AGES_SPEC="$2"
            shift 2
            ;;
        --sexes)
            SEXES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Parse age specification into array
parse_ages() {
    local spec="$1"
    local ages=()
    
    # Handle range like "5-18"
    if [[ "$spec" =~ ^([0-9]+)-([0-9]+)$ ]]; then
        local start="${BASH_REMATCH[1]}"
        local end="${BASH_REMATCH[2]}"
        for ((i=start; i<=end; i++)); do
            ages+=("$i")
        done
    else
        # Handle comma-separated list like "5,6,7"
        IFS=',' read -ra ages <<< "$spec"
    fi
    
    echo "${ages[@]}"
}

# Paths
BASE_ROOT="${DB:-/path/to/cast_data}"
SCRIPTS_DIR="${BASE_ROOT}/tissue_volume_scripts"
WORKER="${SCRIPTS_DIR}/process_subject_volumes.sh"
RESULTS_DIR="${BASE_ROOT}/tissue_volume_results/per_subject"

# Parse configurations
AGES=($(parse_ages "$AGES_SPEC"))
IFS=',' read -ra SEX_ARRAY <<< "$SEXES"

echo "=========================================="
echo "Tissue Volume Batch Job Scheduler"
echo "=========================================="
echo "Ages: ${AGES[*]}"
echo "Sexes: ${SEX_ARRAY[*]}"
echo "Worker script: $WORKER"
echo "Results dir: $RESULTS_DIR"
echo "Dry run: $DRY_RUN"
echo "=========================================="

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# Counters
total_subjects=0
skipped_subjects=0
submitted_jobs=0

# Iterate through ages and sexes
for age in "${AGES[@]}"; do
    for sex in "${SEX_ARRAY[@]}"; do
        data_dir="${BASE_ROOT}/Age${age}/${sex}/intensity_improved_formated"
        
        if [ ! -d "$data_dir" ]; then
            echo "SKIP: Directory not found: $data_dir"
            continue
        fi
        
        echo ""
        echo "Scanning: Age${age}/${sex}"
        
        # Iterate through subject directories
        for subj_dir in "$data_dir"/*; do
            [ -d "$subj_dir" ] || continue
            
            subj_name=$(basename "$subj_dir")
            
            # Skip fsaverage and other non-subject directories
            [[ "$subj_name" == "fsaverage" ]] && continue
            [[ "$subj_name" == "scripts" ]] && continue
            [[ "$subj_name" =~ ^\..*$ ]] && continue
            
            total_subjects=$((total_subjects + 1))
            
            # Check if aseg.mgz exists
            aseg_file="${subj_dir}/mri/aseg.mgz"
            if [ ! -f "$aseg_file" ]; then
                echo "  SKIP $subj_name: no aseg.mgz"
                skipped_subjects=$((skipped_subjects + 1))
                continue
            fi
            
            # Check if output already exists
            out_csv="${RESULTS_DIR}/Age${age}_${sex}_${subj_name}.csv"
            if [ -f "$out_csv" ]; then
                echo "  SKIP $subj_name: output already exists"
                skipped_subjects=$((skipped_subjects + 1))
                continue
            fi
            
            # Submit job
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] sbatch $WORKER $subj_name $age $sex"
            else
                echo "  Submitting: $subj_name (Age: $age, Sex: $sex)"
                sbatch "$WORKER" "$subj_name" "$age" "$sex"
            fi
            
            submitted_jobs=$((submitted_jobs + 1))
        done
    done
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Total subjects found: $total_subjects"
echo "Skipped subjects: $skipped_subjects"
echo "Jobs submitted: $submitted_jobs"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "This was a dry run. No jobs were actually submitted."
    echo "Remove --dry-run to submit jobs."
fi
