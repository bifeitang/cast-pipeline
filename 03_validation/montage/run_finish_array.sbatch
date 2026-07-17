#!/usr/bin/env bash
#SBATCH --job-name=tpl-fin5
#SBATCH --output=tpl-fin5-%A_%a.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=24G
#SBATCH --time=00:25:00
#SBATCH --array=1-5
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
STR=(age14_male age15_male age15_female age16_male age17_female)
S=${STR[$((SLURM_ARRAY_TASK_ID-1))]}
AGE=$(echo $S | sed 's/age//;s/_.*//'); SEX=$(echo $S | sed 's/.*_//')
apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s "$AGE" "$SEX" <<'INNER'
set -uo pipefail
AGE="$1"; SEX="$2"
. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null || true
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=8 OMP_NUM_THREADS=8
DB=/mnt; SCR=$DB/template_montage_scripts
OUT=$DB/Templates/montage_aligned/age${AGE}_${SEX}; cd "$OUT"; export TMPDIR=$OUT
[ -f al_Warped.nii.gz ] || { echo "[ERR] no al_Warped age${AGE}_${SEX}"; exit 1; }
rm -f fast_*.nii.gz al_brain.nii.gz
fslmaths al_Warped.nii.gz -thr 0.25 al_brain.nii.gz
fast -t 1 -n 3 -g -o fast al_brain.nii.gz >fast.log 2>&1 || { echo "[ERR-FAST] age${AGE}_${SEX}"; exit 1; }
python3 "$SCR/extract_slices.py" al_Warped.nii.gz fast_pve_0.nii.gz fast_pve_1.nii.gz fast_pve_2.nii.gz \
  "$OUT/slices_age${AGE}_${SEX}.npz" "$AGE" "$SEX" && echo "[ok] age${AGE}_${SEX}"
INNER
