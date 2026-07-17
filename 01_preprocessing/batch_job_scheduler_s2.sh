#!/bin/bash

# Schedule sbatch jobs for male and female between ages 14–18
BASE_DIR=${DB:-/path/to/cast_data}

for age in Age5 Age6; do
    for sex in male female; do
        DATA_DIR="$BASE_DIR/$age/$sex/intensity_improved_formated"

        # Loop over subjects in reverse alphabetical order
        for subject_folder in $(ls -d "$DATA_DIR"/* 2>/dev/null | sort -r); do
            if [ -d "$subject_folder" ]; then
                # Extract subject name from folder
                subject=$(basename "$subject_folder")

                # Submit a job for each subject
                sbatch process_subject_s2.sh "$subject" "$age" "$sex" intensity_improved_formated
            fi
        done
    done
done
