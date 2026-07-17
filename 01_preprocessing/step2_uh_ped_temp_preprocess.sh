# #!/bin/sh

#!/usr/bin/env bash
#
#  step2_uh_ped_temp_preprocess_v2.sh  —  FreeSurfer  +  CSF-normalise
#                                      +  export for template (recenter delegated to step2.5)
#
#  USAGE:  step2_uh_ped_temp_preprocess_v2.sh  <CCS_DIR>  <SUBJECTS_DIR>  <subject>
#
#  INPUT  (from step-1)  :   <CCS_DIR>/<subject>/anat/T1_crop_sanlm_n4.nii.gz
#  OUTPUT (for template) :   <CCS_DIR>/<subject>/anat/subj_<subject>_csfNorm_rc.nii.gz
#                            ( _rc  =  re-centred; produced by step2.5_uh_ped_temp_recenter.sh )
#
#  Added sections:
#      6.  (Delegated) Translate image so its centre-of-mass sits at (0,0,0)
#          and apply the same transform to masks via step2.5_uh_ped_temp_recenter.sh
#                                                                     Yang Hu, 2025-05-10
# # -----------------------------------------------------------------------------
# # Runs FreeSurfer (using the DeepBET mask from Step‑1), creates WM/CSF segment
# # masks, and generates a CSF‑normalised brain image ready for template build.

CCS_DIR=$1
SUBJECTS_DIR=$2
subject=$3
anat_dir=${CCS_DIR}/${subject}/anat

if [ $# -lt 3 ]; 
then
    echo -e "\033[47;35m Usage: $0 CCS_DIR SUBJECTS_DIR subject \033[0m"
    exit
fi

#test if file existence
T1image=${anat_dir}/T1_crop_sanlm_n4.nii.gz
if [ ! -f ${T1image} ]
then
    echo "Couldn't find T1 image ${T1image} please check your data"
    exit
fi

OutputImage=${anat_dir}/subj_${subject}_brainmask_csfNorm.nii.gz
if [ -f ${OutputImage} ]
then
    echo "Output image ${OutputImage} already exists, please check your data"
    exit
fi

##############################################################################
# 1.  FreeSurfer autorecon1 with custom skull‑strip                            #
##############################################################################

echo "Running FreeSurfer autorecon1 (noskullstrip) …"

mkdir -p ${SUBJECTS_DIR}/${subject}/mri/orig
mri_convert -i  ${T1image} -o ${SUBJECTS_DIR}/${subject}/mri/orig/001.mgz

# Run recon‑all through autorecon1 **without** FreeSurfer skull‑strip
echo "################# Running FreeSurfer autorecon1 (noskullstrip) ################# "
recon-all -s ${subject} -autorecon1 -noskullstrip -parallel

# Replace FreeSurfer mask with DeepBET mask
echo "################# Replace FreeSurfer mask with DeepBET mask ################# " 
mri_convert ${SUBJECTS_DIR}/${subject}/mri/T1.mgz ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz
3dresample -master ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz \
           -inset ${anat_dir}/T1_crop_sanlm_n4_brain_mask.nii.gz \
           -prefix ${SUBJECTS_DIR}/${subject}/mri/mask.nii.gz

# Create FreeSurfer‑friendly brainmask.mgz (with low‑level background noise)
# -------------------------------------------------------------------------
cp ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz ${SUBJECTS_DIR}/${subject}/mri/T1_orig.nii.gz
[ -f ${SUBJECTS_DIR}/${subject}/mri/brainmask.mgz ] && \
    mv ${SUBJECTS_DIR}/${subject}/mri/brainmask.mgz ${SUBJECTS_DIR}/${subject}/mri/brainmask.fsinit.mgz

fslmaths ${SUBJECTS_DIR}/${subject}/mri/mask.nii.gz -dilM -dilM \
         ${SUBJECTS_DIR}/${subject}/mri/buffer_mask.nii.gz
fslmaths ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz -mas \
         ${SUBJECTS_DIR}/${subject}/mri/mask.nii.gz \
         ${SUBJECTS_DIR}/${subject}/mri/brain.nii.gz
fslmaths ${SUBJECTS_DIR}/${subject}/mri/buffer_mask.nii.gz -sub \
         ${SUBJECTS_DIR}/${subject}/mri/mask.nii.gz \
         ${SUBJECTS_DIR}/${subject}/mri/just_buffer.nii.gz
fslmaths ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz -mas \
         ${SUBJECTS_DIR}/${subject}/mri/just_buffer.nii.gz \
         ${SUBJECTS_DIR}/${subject}/mri/buffer_region.nii.gz
fslmaths ${SUBJECTS_DIR}/${subject}/mri/buffer_mask.nii.gz -binv \
         ${SUBJECTS_DIR}/${subject}/mri/outside.nii.gz

bg_mean=$(fslstats ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz -k \
                   ${SUBJECTS_DIR}/${subject}/mri/outside.nii.gz -m)
bg_std=$(fslstats ${SUBJECTS_DIR}/${subject}/mri/T1.nii.gz -k \
                  ${SUBJECTS_DIR}/${subject}/mri/outside.nii.gz -s)

# Create low-level noise (1% of background standard deviation)
# Note: this is a bit of a hack to avoid having a completely zeroed background
#       in the brainmask.mgz file.  It should be small enough to not affect
#       anything, but large enough to avoid issues with FreeSurfer.
#       (e.g. "Warning: 0 voxels in mask" when running recon-all)
#       This is a workaround for FreeSurfer's inability to handle zeroed
#       background regions in the brainmask.mgz file.
noise_lvl=$(echo "scale=4; ${bg_std} * 0.01" | bc)
fslmaths ${SUBJECTS_DIR}/${subject}/mri/outside.nii.gz -mul ${noise_lvl} \
         ${SUBJECTS_DIR}/${subject}/mri/bg_noise.nii.gz

fslmaths ${SUBJECTS_DIR}/${subject}/mri/brain.nii.gz -add \
         ${SUBJECTS_DIR}/${subject}/mri/buffer_region.nii.gz -add \
         ${SUBJECTS_DIR}/${subject}/mri/bg_noise.nii.gz \
         ${SUBJECTS_DIR}/${subject}/mri/brainmask.nii.gz

mri_convert -i ${SUBJECTS_DIR}/${subject}/mri/brainmask.nii.gz \
            -o ${SUBJECTS_DIR}/${subject}/mri/brainmask.mgz

rm -f ${SUBJECTS_DIR}/${subject}/mri/buffer_* outside.nii.gz bg_noise.nii.gz just_buffer.nii.gz

##############################################################################
# 2.  recon‑all autorecon2/3 (skip segstats)                                  #
##############################################################################
recon-all -s "${subject}" -autorecon2 -noparcstats -parallel
recon-all -s "${subject}" -autorecon3 -noparcstats -parallel

echo "FreeSurfer processing complete.  Creating WM/CSF masks …"

##############################################################################
# 3.  Extract WM & CSF masks in native space                                   #
##############################################################################

# 3a. FAST Segmentation - probabilistic CSF (>0.90)
echo "Running FAST for high-confidence CSF maks …"
mkdir -p "${anat_dir}/segment"
fast -t 1 -n 3 -b -o "${anat_dir}/segment/fast" "${T1image}"

# pve_0 = CSF for T1 images
fslmaths "${anat_dir}/segment/fast_pve_0.nii.gz" -thr 0.90 -bin \
         "${anat_dir}/segment/segment_csf_fast.nii.gz"

# pve_1 = GM for T1 images (high‑confidence > 0.90)
fslmaths "${anat_dir}/segment/fast_pve_1.nii.gz" -thr 0.90 -bin \
         "${anat_dir}/segment/segment_gm_fast.nii.gz"

mri_binarize --i "${SUBJECTS_DIR}/${subject}/mri/aseg.mgz" \
             --o "${anat_dir}/segment/segment_wm.nii.gz" \
             --match 2 41 7 46 251 252 253 254 255 --erode 1

mri_binarize --i "${SUBJECTS_DIR}/${subject}/mri/aseg.mgz" \
             --o "${anat_dir}/segment/segment_csf.nii.gz" \
             --match 4 5 43 44 31 63 --erode 1

##############################################################################
# 4.  CSF‑based intensity normalisation                                        #
##############################################################################

echo "Normalising T1 intensity to mean CSF signal …"
if [ -s "${anat_dir}/segment/segment_csf_fast.nii.gz" ]; then
  csf_mask="${anat_dir}/segment/segment_csf_fast.nii.gz"
else
  echo "⚠ FAST mask empty - falling back to ventricular mask."
  csf_mask="${anat_dir}/segment/segment_csf.nii.gz"
fi

csf_mean=$(fslstats "${T1image}" -k "${csf_mask}" -M)

# First, add debugging to see what's happening
echo "DEBUG: csf_mean using mask '${csf_mask}' ⇒ ${csf_mean}"

# Then modify the condition to be more robust
if [ -z "${csf_mean}" ] || [ "${csf_mean}" = "nan" ] || \
     (( $(echo "${csf_mean} < 1e-6" | bc -l) )); then
  echo "⚠ CSF mask seems empty; falling back to whole brain mean."
  csf_mean=$(fslstats "${T1image}" -M)
fi

fslmaths "${T1image}" -div ${csf_mean} "${anat_dir}/T1_crop_sanlm_n4_csfNorm.nii.gz"

# Mask the normalised image and save with template‑friendly name
fslmaths "${anat_dir}/T1_crop_sanlm_n4_csfNorm.nii.gz" -mas \
         "${anat_dir}/T1_crop_sanlm_n4_brain_mask.nii.gz" \
         "${anat_dir}/subj_${subject}_brainmask_csfNorm.nii.gz"

echo "✓ Generated ${anat_dir}/subj_${subject}_brainmask_csfNorm.nii.gz."

##############################################################################
# 5.  Quantitative QC metrics (saved per subject)                             #
##############################################################################
qc_csv="${anat_dir}/qc_metrics.csv"

# Add header if this is the first subject
if [ ! -f "${qc_csv}" ]; then
  echo "subject,brain_mask_cm3,wm_cv,gm_csf_ratio,wm_csf_ratio" > "${qc_csv}"
fi

# 5a. Brain‑mask completeness (cm³)
brain_mask_cm3=$(fslstats "${anat_dir}/T1_crop_sanlm_n4_brain_mask.nii.gz" -V | awk '{printf("%.2f",$2/1000)}')

# 5b. WM coefficient of variation
wm_stats=$(fslstats "${anat_dir}/T1_crop_sanlm_n4.nii.gz" -k "${anat_dir}/segment/segment_wm.nii.gz" -S -M)
wm_cv=$(echo "${wm_stats}" | awk '{printf("%.3f",$1/$2)}')

# 5c. GM/CSF & WM/CSF intensity ratios (using CSF‑normalised image)
gm_mean=$(fslstats "${anat_dir}/T1_crop_sanlm_n4_csfNorm.nii.gz" -k "${anat_dir}/segment/segment_gm_fast.nii.gz" -M)
csf_mean=$(fslstats "${anat_dir}/T1_crop_sanlm_n4_csfNorm.nii.gz" -k "${anat_dir}/segment/segment_csf_fast.nii.gz" -M)
wm_mean=$(fslstats "${anat_dir}/T1_crop_sanlm_n4_csfNorm.nii.gz" -k "${anat_dir}/segment/segment_wm.nii.gz" -M)

gm_csf_ratio=$(echo "${gm_mean} ${csf_mean}" | awk '{printf("%.2f",$1/$2)}')
wm_csf_ratio=$(echo "${wm_mean} ${csf_mean}" | awk '{printf("%.2f",$1/$2)}')

# 5d. Append to CSV
echo "${subject},${brain_mask_cm3},${wm_cv},${gm_csf_ratio},${wm_csf_ratio}" >> "${qc_csv}"
echo "✓ QC metrics appended to ${qc_csv}"

##############################################################################
# 6.  Re-centre intensity-normalised image (and every mask)                  #
##############################################################################
echo "Recentering image/masks (delegating to step2.5_uh_ped_temp_recenter.sh) …"

this_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
recenter_sh="${this_dir}/step2.5_uh_ped_temp_recenter.sh"
if [ ! -f "${recenter_sh}" ]; then
  echo "Error: recenter script not found: ${recenter_sh}" >&2
  echo "Tip: run step2.5_uh_ped_temp_recenter.sh manually to generate subj_${subject}_csfNorm_rc.nii.gz" >&2
  exit 10
fi

# Default to resample mode to guarantee voxelwise alignment of masks/labels.
bash "${recenter_sh}" "${CCS_DIR}" "${SUBJECTS_DIR}" "${subject}" --mode=resample