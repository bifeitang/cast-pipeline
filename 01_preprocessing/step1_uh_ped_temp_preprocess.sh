#!/bin/sh

# Usage: step1_uh_ped_temp_preprocess.sh <CCS_DIR> <SUBJECTS_DIR> <subject> [phase]
# -----------------------------------------------------------------------------
# Phase 1 – MATLAB‑dependent (SANLM denoise).
# Phase 2 – Non‑MATLAB (N4, DeepBET mask, buffer‑aware brain extraction).
# Default is to run both phases.

CCS_DIR=$1
SUBJECTS_DIR=$2
subject=$3
phase=${4:-"both"}

anat_dir=${CCS_DIR}/${subject}/anat
qc_dir=${CCS_DIR}/${subject}/qc
mkdir -p "${qc_dir}"

if [ $# -lt 3 ]; then
    echo "\nUsage: $0 CCS_DIR SUBJECTS_DIR subject [phase]"
    echo "phase: 1 | 2 | both (default)\n"; exit 1; fi

T1image="${anat_dir}/T1.nii.gz"
[ ! -f "${T1image}" ] && { echo "Missing T1 image: ${T1image}"; exit 1; }

cd "${anat_dir}"

################################ PHASE 1 ######################################
if [ "$phase" = "1" ] || [ "$phase" = "both" ]; then
    echo "----- Phase 1: MATLAB-dependent steps -----"

    # 1. Re‑orient to RPI for ANTs/FSL compatibility
    [ ! -f T1_ro.nii.gz ] && 3dresample -orient RPI -inset T1.nii.gz -prefix T1_ro.nii.gz

    # 2. Robust FOV crop (FSL)
    [ ! -f T1_crop.nii.gz ] && robustfov -i T1_ro -r T1_crop

    # 3. SANLM denoise – reduced strength (v=1) for paediatric contrast
    if [ ! -f T1_crop_sanlm.nii.gz ]; then
        mkdir -p denoise && \
        mri_convert -i T1_crop.nii.gz -o denoise/T1_crop.nii && \
        matlab -nodesktop -nosplash -nojvm -r "addpath('/opt/spm12');addpath('/opt/spm12/toolbox/cat12');data='${anat_dir}/denoise/T1_crop.nii';cat_vol_sanlm(struct('data',data,'prefix','sanlm_','v',1));quit"
        mri_convert -i denoise/sanlm_T1_crop.nii -o T1_crop_sanlm.nii.gz && \
        rm -rf denoise
    fi
    touch phase1_complete
fi

################################ PHASE 2 ######################################
if [ "$phase" = "2" ] || [ "$phase" = "both" ]; then
    echo "----- Phase 2: Non-MATLAB steps -----"
    [ "$phase" = "2" ] && [ ! -f phase1_complete ] && { echo "Phase 1 incomplete"; exit 1; }

    # 4. N4 bias‑field correction (gentle defaults)
    [ ! -f T1_crop_sanlm_n4.nii.gz ] && \
        N4BiasFieldCorrection -d 3 -i T1_crop_sanlm.nii.gz -o T1_crop_sanlm_n4.nii.gz

    # 5. DeepBET skull‑strip → brain mask
    if [ ! -f T1_crop_sanlm_n4_brain_mask.nii.gz ]; then
        python3 ${DEEP_BET_DIR}/UNet_Model/muSkullStrip.py \
            -in T1_crop_sanlm_n4.nii.gz \
            -model ${CCS_APP}/models/model-04-epoch \
            -out . && \
        mv T1_crop_sanlm_n4_pre_mask.nii.gz T1_crop_sanlm_n4_brain_mask.nii.gz
    fi

    # 6. Buffer zone around mask (2‑voxel dilation)
    [ ! -f T1_crop_sanlm_n4_buffermask.nii.gz ] && \
        fslmaths T1_crop_sanlm_n4_brain_mask.nii.gz -dilM -dilM T1_crop_sanlm_n4_buffermask.nii.gz

    # 7. Brain extraction with realistic background for FBER / QC
    if [ ! -f T1_crop_sanlm_n4_brain.nii.gz ]; then
        fslmaths T1_crop_sanlm_n4.nii.gz -mas T1_crop_sanlm_n4_brain_mask.nii.gz brain_signal.nii.gz
        fslmaths T1_crop_sanlm_n4_buffermask.nii.gz -sub T1_crop_sanlm_n4_brain_mask.nii.gz buffer_mask.nii.gz
        fslmaths T1_crop_sanlm_n4.nii.gz -mas buffer_mask.nii.gz buffer_signal.nii.gz
        fslmaths T1_crop_sanlm_n4_buffermask.nii.gz -binv outside_mask.nii.gz
        bg_std=$(fslstats T1_crop_sanlm_n4.nii.gz -k outside_mask.nii.gz -s)
        noise_lvl=$(echo "${bg_std} * 0.01" | bc -l)
        fslmaths outside_mask.nii.gz -mul ${noise_lvl} background_noise.nii.gz
        fslmaths brain_signal.nii.gz -add buffer_signal.nii.gz -add background_noise.nii.gz T1_crop_sanlm_n4_brain.nii.gz
        rm -f brain_signal.nii.gz buffer_* outside_mask.nii.gz background_noise.nii.gz
    fi

    touch phase2_complete
fi

[ -f phase1_complete ] && [ -f phase2_complete ] && echo "✓ Step 1 completed for ${subject}"