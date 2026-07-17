#!/usr/bin/env bash
# CAST pipeline — environment configuration.
#
# Set these for your environment, then `source config.sh` before running, or
# override per-invocation: `DB=/your/root C_REG=/your/image.sif sbatch 03_validation/...`.
# The defaults below are non-functional placeholders (the pipeline was developed on an
# HPC cluster with Apptainer/Singularity); edit them to point at your data and images.

# DB : data root holding the age/sex-stratified, preprocessed inputs and the
#      Templates/ , Validity/ , TemplateTestSet/ trees.
export DB="${DB:-/path/to/cast_data}"

# IMAGE_DIR : directory holding the Apptainer/Singularity images.
export IMAGE_DIR="${IMAGE_DIR:-/path/to/containers}"
# C / C_REG : image for ANTs registration + template construction
#      (build a license-free one from container/). C is kept as an alias of C_REG.
export C_REG="${C_REG:-$IMAGE_DIR/cast_reg.sif}"
export C="${C:-$C_REG}"
# C_PREPROC : image for the MATLAB-dependent preprocessing phase
#      (01_preprocessing/process_subject_s1.sh, phase 1).
export C_PREPROC="${C_PREPROC:-$IMAGE_DIR/cast_preproc.sif}"

# PROJECT_ROOT : scratch / working root for intermediate job directories.
export PROJECT_ROOT="${PROJECT_ROOT:-/path/to/project}"
# TMPROOT : root for per-job temporary directories.
export TMPROOT="${TMPROOT:-/tmp}"
# NT : threads for ANTs/ITK.
export NT="${NT:-8}"
