#!/usr/bin/env bash
#SBATCH --job-name=tpl-morph
#SBATCH --output=tpl-morph-%A_%a.out
#SBATCH --error=tpl-morph-%A_%a.err
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --mem=6G
#SBATCH --time=00:25:00
#SBATCH --array=1-26
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
T=/mnt/Templates/UpdatedTemplates
SCR=/mnt/validity_heatmap_scripts
OUT=/mnt/tissue_volume_results/template_morphometry/cells
mkdir -p "$DB/tissue_volume_results/template_morphometry/cells"
mapfile -t NAMES < <(for a in 5 6 7 8 9 10 11 12 13 14 15 17 18; do for s in female male; do echo age${a}_${s}; done; done)
NAME="${NAMES[$((SLURM_ARRAY_TASK_ID-1))]}"
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "
  . /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null
  tpl=$T/${NAME}_template.nii.gz
  [ -f \$tpl ] || { echo skip-missing $NAME; exit 0; }
  python3 $SCR/template_morphometry.py \$tpl $OUT $NAME > $OUT/${NAME}.json 2>$OUT/${NAME}.err && echo done $NAME"
