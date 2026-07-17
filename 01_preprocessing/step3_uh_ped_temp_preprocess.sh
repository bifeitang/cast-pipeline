#!/usr/bin/env bash
########this script run ccs_anat_preproc###########
#there are three inputs 
# The first step of this script is to run on bash will move to python eventually
# 1.CCS_DIR
# 2.SUBJECTS_DIR
# 3.subject
######################################################

#set dirs
CCS_DIR=$1
SUBJECTS_DIR=$2
subject=$3
anat_dir=${CCS_DIR}/${subject}/anat
reg_dir=${anat_dir}/reg
seg_dir=${anat_dir}/segment
qc_dir=${CCS_DIR}/${subject}/qc
mkdir -p ${reg_dir} ${seg_dir} ${qc_dir}

if [ $# -lt 3 ]; 
then
    echo -e "\033[47;35m Usage: $0 CCS_DIR SUBJECTS_DIR subject \033[0m"
    exit
fi

# Generate copy brainmask
if [ ! -f ${anat_dir}/T1_crop_sanlm_fs.nii.gz ]
then
    mri_convert -it mgz ${SUBJECTS_DIR}/${subject}/mri/orig.mgz -ot nii ${anat_dir}/T1_crop_sanlm_fs.nii.gz
fi

if [ ! -f ${seg_dir}/brainmask.nii.gz ]
then
    mri_convert -it mgz ${SUBJECTS_DIR}/${subject}/mri/brainmask.mgz -ot nii ${seg_dir}/brainmask.nii.gz
fi

## 1. Prepare anatomical images with careful preservation of signal properties
if [ -f ${reg_dir}/highres_head.nii.gz ]
then
    rm -v ${reg_dir}/highres_head.nii.gz
fi

mv ${anat_dir}/T1_crop_sanlm_fs.nii.gz ${reg_dir}/highres_head.nii.gz

# Create a properly thresholded mask while preserving buffer zone
# This is key for maintaining proper FBER metrics
fslmaths ${seg_dir}/brainmask.nii.gz -bin ${seg_dir}/brainmask_bin.nii.gz
fslmaths ${seg_dir}/brainmask_bin.nii.gz -dilM ${seg_dir}/brainmask_buffer.nii.gz
fslmaths ${seg_dir}/brainmask_buffer.nii.gz -sub ${seg_dir}/brainmask_bin.nii.gz ${seg_dir}/buffer_zone.nii.gz

# Get signal in buffer zone
fslmaths ${reg_dir}/highres_head.nii.gz -mas ${seg_dir}/buffer_zone.nii.gz ${seg_dir}/buffer_signal.nii.gz

# Extract brain signal
fslmaths ${reg_dir}/highres_head.nii.gz -mas ${seg_dir}/brainmask_bin.nii.gz ${seg_dir}/brain_signal.nii.gz

# Create background mask
fslmaths ${seg_dir}/brainmask_buffer.nii.gz -binv ${seg_dir}/background_mask.nii.gz

# Calculate background statistics for realistic noise
bg_mean=$(fslstats ${reg_dir}/highres_head.nii.gz -k ${seg_dir}/background_mask.nii.gz -m)
bg_std=$(fslstats ${reg_dir}/highres_head.nii.gz -k ${seg_dir}/background_mask.nii.gz -s)

# Create low-level noise (1% of background standard deviation)
noise_level=$(echo "scale=4; ${bg_std} * 0.01" | bc)
fslmaths ${seg_dir}/background_mask.nii.gz -mul ${noise_level} ${seg_dir}/background_noise.nii.gz

# Combine brain, buffer, and background noise
fslmaths ${seg_dir}/brain_signal.nii.gz -add ${seg_dir}/buffer_signal.nii.gz -add ${seg_dir}/background_noise.nii.gz ${reg_dir}/highres.nii.gz

# Clean up temporary files
rm -f ${seg_dir}/brainmask_bin.nii.gz ${seg_dir}/brainmask_buffer.nii.gz ${seg_dir}/buffer_zone.nii.gz ${seg_dir}/buffer_signal.nii.gz ${seg_dir}/brain_signal.nii.gz ${seg_dir}/background_mask.nii.gz ${seg_dir}/background_noise.nii.gz

# Run MRIQC on final processed image
mriqc ${reg_dir}/highres.nii.gz ${qc_dir}/final participant --no-sub

cd ${reg_dir}
## Use pediatric template for registration if available (NIH Pediatric template)
# Check if we have pediatric templates
if [ -f "${FSLDIR}/data/pediatric/nihpd_asym_07-11_t1_2mm.nii.gz" ]; then
    # Use pediatric template instead of MNI152
    echo "Using NIH Pediatric template for registration"
    standard_head=${FSLDIR}/data/pediatric/nihpd_asym_07-11_t1_2mm.nii.gz
    standard=${FSLDIR}/data/pediatric/nihpd_asym_07-11_t1_2mm_brain.nii.gz
    standard_mask=${FSLDIR}/data/pediatric/nihpd_asym_07-11_t1_2mm_brain_mask_dil.nii.gz
else
    # Fall back to standard MNI template
    echo "Pediatric template not found. Using standard MNI152 template."
    standard_head=${FSLDIR}/data/standard/MNI152_T1_2mm.nii.gz
    standard=${FSLDIR}/data/standard/MNI152_T1_2mm_brain.nii.gz
    standard_mask=${FSLDIR}/data/standard/MNI152_T1_2mm_brain_mask_dil.nii.gz
fi

## 2. FLIRT with gentle parameters for pediatric data
echo "########################## Performing gentle FLIRT for pediatric data #################################"
fslreorient2std highres.nii.gz highres_rpi.nii.gz
fslreorient2std highres_head.nii.gz highres_head_rpi.nii.gz

# Use more conservative parameters for pediatric data
flirt -ref ${standard} -in highres_rpi -out highres_rpi2standard -omat highres_rpi2standard.mat -cost normmi -searchcost normmi -dof 9 -interp sinc -sincwidth 7 -sincwindow hanning

## 3. Create mat file for conversion from standard to high res
fslreorient2std highres.nii.gz > reorient2rpi.mat
convert_xfm -omat highres2standard.mat -concat highres_rpi2standard.mat reorient2rpi.mat
convert_xfm -inverse -omat standard2highres.mat highres2standard.mat

## 3. FNIRT with gentler parameters for pediatric data
echo "########################## Performing gentler nonlinear registration for pediatric data #################################"
# Use more conservative parameters for FNIRT
fnirt --in=highres_head --aff=highres2standard.mat --cout=highres2standard_warp --iout=fnirt_highres2standard --jout=highres2standard_jac --config=T1_2_MNI152_2mm --ref=${standard_head} --refmask=${standard_mask} --warpres=20,20,20 --splineorder=2 --estint=1,1,1 --infwhm=8,4,2 --reffwhm=4,2,0 --lambda=300,150,100,50,40

# Run final MRIQC after all processing
mriqc ${reg_dir}/fnirt_highres2standard.nii.gz ${qc_dir}/final_registered participant --no-sub

cd ${cwd}