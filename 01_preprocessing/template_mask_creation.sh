#!/bin/bash

# Job scheduler directives (e.g., Slurm)
#SBATCH --job-name=mri-template-mask-creation
#SBATCH --output=mri-template-mask-creation-%j.out
#SBATCH --error=mri-template-mask-creation-%j.err
#SBATCH --time=30:00:00
#SBATCH --partition=standard
#SBATCH -N 1 
#SBATCH -n 4
#SBATCH --mem=32G


SLURM_CPUS_PER_TASK=4
FSLDIR=/usr/local/fsl

# Define a unique temporary directory for this job to avoid conflicts
UNIQUE_TEMP_DIR=${TMPROOT:-/tmp}/TemplateMaskCreationTemp
mkdir -p $UNIQUE_TEMP_DIR

apptainer exec --bind $UNIQUE_TEMP_DIR:/writabletemp --bind ${DB:-/path/to/cast_data}:/mnt ${C_REG:-cast_reg.sif} \
    /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                    export TMPDIR=/writabletemp &&\
                    export PATH="$PATH:/opt/ANTs/install/bin" &&\
                    export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK &&\
                    /bin/bash /mnt/deformation_cost_scripts/compute_template_masks.sh \
                    /mnt/Templates/age9_female_template.nii.gz" 