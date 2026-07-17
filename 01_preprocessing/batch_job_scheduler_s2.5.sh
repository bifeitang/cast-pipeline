#!/bin/bash

# Submit step 2.5 recentering for Age 8 and 10, male and female, under intensity_improved_formated

BASE_ROOT=${DB:-/path/to/cast_data}
SELF_DIR=${IMAGE_DIR:-/path/to/containers}/20250330_latest_working_script
WORKER="$SELF_DIR/process_subject_s2.5.sh"

ages="5 6"
sexes="male female"

echo "Starting batch job submission for step 2.5 (Ages: $ages; Sexes: $sexes) …"

for age in $ages; do
  for sex in $sexes; do
    root_dir="$BASE_ROOT/Age${age}/${sex}/intensity_improved_formated"
    if [ ! -d "$root_dir" ]; then
      echo "Skip: root not found $root_dir"
      continue
    fi
    echo "Scanning $root_dir"

    # Iterate subjects by directory name (skip non-directories and fsaverage)
    for subj_dir in "$root_dir"/*; do
      [ -d "$subj_dir" ] || continue
      subj_name=$(basename "$subj_dir")
      [ "$subj_name" = "fsaverage" ] && continue

      anat_dir="$subj_dir/anat"
      if [ ! -d "$anat_dir" ]; then
        echo "Skip $subj_name: anat/ not found"
        continue
      fi

      # Presence check of at least one expected intensity file
      brainmask="$anat_dir/subj_${subj_name}_brainmask_csfNorm.nii.gz"
      alt_intensity="$anat_dir/T1_crop_sanlm_n4_csfNorm.nii.gz"
      if [ ! -f "$brainmask" ] && [ ! -f "$alt_intensity" ]; then
        echo "Skip $subj_name: no intensity found ($brainmask or $alt_intensity)"
        continue
      fi

      echo "Submitting job for subject: $subj_name (Age: $age, Sex: $sex)"
      sbatch "$WORKER" "$subj_name" "$age" "$sex"
    done
  done
done

echo "Batch job submission completed."
