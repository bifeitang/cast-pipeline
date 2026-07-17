# MRI Processing Pipeline

## Overview

This script automates the neuroimaging data processing pipeline for pediatric MRI data. It is designed to run in a high-performance computing environment using the SLURM job scheduler and Apptainer (formerly Singularity) containers. The pipeline is divided into two phases:

1. **Phase 1**: MATLAB-dependent preprocessing steps
2. **Phase 2**: ANTs-based registration and additional non-MATLAB processing steps

The script supports various data organization structures by allowing you to specify age groups, gender subdivisions, and additional subfolders.

## Features

- **Configurable Data Paths**: Dynamically builds directory paths based on age group, gender, and subfolder parameters
- **Two-Phase Processing**: Separates MATLAB and non-MATLAB dependent steps
- **Automatic Phase Scheduling**: Can automatically schedule Phase 2 after Phase 1 completes
- **Lock File System**: Prevents duplicate processing of the same subject
- **Robust Error Handling**: Verifies successful completion of each phase before proceeding
- **Clean-up Mechanism**: Automatically removes temporary files after successful processing

## Requirements

- SLURM job scheduler
- Apptainer/Singularity
- Access to the required container images:
  - `$C_PREPROC` (preprocessing image) (for Phase 1)
  - `$C_REG` (registration image) (for Phase 2)
- FSL installed at `/usr/local/fsl`
- Project directory structure following the expected pattern

## Usage

```
./process_mri.sh <subject_id> [phase] [age] [gender] [subfolder]
```

### Parameters

- **subject_id** (required): Identifier for the subject to process
- **phase** (optional): Processing phase to run
  - `1`: Run only Phase 1 (MATLAB steps)
  - `2`: Run only Phase 2 (ANTs and other steps)
  - `both`: Run both phases sequentially
  - Default: `1`
- **age** (optional): Age group folder name
  - Examples: `Age9`, `Age10`, `Sample`
  - Default: `Sample`
- **gender** (optional): Gender subfolder
  - Examples: `male`, `female`
  - Default: empty (no gender subfolder)
- **subfolder** (optional): Additional subfolder
  - Example: `formated`
  - Default: empty (no additional subfolder)

### Directory Structure

The script builds paths dynamically based on the provided parameters:

```
${DB}/<age>[/<gender>[/<subfolder>]]
```

For container mounting:
```
/mnt/<age>[/<gender>[/<subfolder>]]
```

### Examples

```bash
# Process subject 'SUBJ001' with default paths (Sample)
./process_mri.sh SUBJ001

# Process both phases for subject 'SUBJ002' in Age9/male/formated
./process_mri.sh SUBJ002 both Age9 male formated

# Process only Phase 2 for subject 'SUBJ003' in Age10/female/formated
./process_mri.sh SUBJ003 2 Age10 female formated

# Process Phase 1 for subject 'SUBJ004' in Age9 (no gender subdivision)
./process_mri.sh SUBJ004 1 Age9
```

## Output Files

- Job output: `mri-process-<jobid>.out`
- Job errors: `mri-process-<jobid>.err`
- Temporary files: `${TMPROOT}/Temp_reverse_<subject>/`
- Phase completion flags:
  - Phase 1: `${TMPROOT}/Temp_reverse_<subject>/<subject>_phase1_complete`
  - Phase 2: `${TMPROOT}/Temp_reverse_<subject>/<subject>_phase2_complete`

## Error Handling

The script includes robust error checking:

1. Validates required parameters
2. Verifies successful completion of each container operation
3. Creates phase completion flags only upon successful execution
4. Automatically cleans up temporary files only after successful processing
5. Provides detailed error messages for troubleshooting

## Notes

- The script uses a locking mechanism to prevent concurrent processing of the same subject and phase
- When running only Phase 1, it automatically schedules Phase 2 as a separate job
- Temporary directories are automatically cleaned up after successful completion of Phase 2
- Processing logs are stored in SLURM output files for debugging purposes