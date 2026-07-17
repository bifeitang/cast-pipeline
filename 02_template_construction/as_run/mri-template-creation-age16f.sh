#!/bin/bash

# Job scheduler directives (e.g., Slurm)
#SBATCH --job-name=age16ftemp
#SBATCH --output=mri-template-age16f-creation-%j.out
#SBATCH --error=mri-template-age16f-creation-%j.err
#SBATCH --time=10-30:00:00
#SBATCH --partition=standard
#SBATCH -N 1
#SBATCH -n 48
#SBATCH --mem=64G

SLURM_CPUS_PER_TASK=48
FSLDIR=/usr/local/fsl

# Define a unique temporary directory for this job to avoid conflicts
UNIQUE_TEMP_DIR=${TMPROOT:-/tmp}/TemplateCreationAge16Female
mkdir -p "$UNIQUE_TEMP_DIR"

apptainer exec --bind "$UNIQUE_TEMP_DIR":/writabletemp \
               --bind ${DB:-/path/to/cast_data}:/mnt \
               ${C_REG:-cast_reg.sif} \
               /bin/bash -c "source ${FSLDIR}/etc/fslconf/fsl.sh && \
                    export TMPDIR=/writabletemp && \
                    export PATH=\"\$PATH:/opt/ANTs/install/bin\" && \
                    export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$SLURM_CPUS_PER_TASK && \
                    cd /mnt/Age16/female/intensity_improved_selected_for_template && \
                    antsMultivariateTemplateConstruction2.sh \
                        -d 3 -o template0_ -i 12 \
                        -z /mnt/Age16/female/intensity_improved_selected_for_template/REFERENCE_SUBJECT.nii.gz -r 1 \
                        -g 0.10 -c 0 -k 1 -w 1 -y 0 \
                        -f 8x4x2x1 -s 4x2x1x0vox -q 120x90x60x20 \
                        -l 0 \
                        -t \"SyN[0.1]\" -m \"CC[2]\" \
                        -n 0 -u 1 \
                        /mnt/Age16/female/intensity_improved_selected_for_template/*.nii.gz"

