#!/usr/bin/env bash
#SBATCH --job-name=tpl-align
#SBATCH --output=tpl-align-%A_%a.out
#SBATCH -N 1
#SBATCH -n 6
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --array=1-28%14
# Rigidly align each age/sex CAST template to ONE common reference (preserves true brain
# size -> growth visible), FAST-segment GM/WM/CSF in the common grid, and extract matched
# montage slices. One array task = one template. Reference = age11_male (mid-range).
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-6}"
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
SCR=$DB/template_montage_scripts

# task id -> (age,sex)
AGES=(5 6 7 8 9 10 11 12 13 14 15 16 17 18)
i=$((SLURM_ARRAY_TASK_ID-1)); na=${#AGES[@]}
AGE=${AGES[$((i % na))]}
if [ $((i / na)) -eq 0 ]; then SEX=male; else SEX=female; fi

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s "$AGE" "$SEX" "$NT" <<'INNER'
set -uo pipefail
AGE="$1"; SEX="$2"; NT="$3"
. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null || true
export PATH="$PATH:/opt/ANTs/install/bin" ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"
DB=/mnt; SCR=$DB/template_montage_scripts
TPLDIR=$DB/Templates/UpdatedTemplates
REF=$TPLDIR/age11_male_template.nii.gz
OUT=$DB/Templates/montage_aligned/age${AGE}_${SEX}; mkdir -p "$OUT"; cd "$OUT"
export TMPDIR=$OUT
TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
[ -f "$TPL" ] || { echo "[ERR] missing $TPL"; exit 1; }

# 1) rigid (6-dof, NO scaling) -> common reference grid
if [ ! -f al_Warped.nii.gz ]; then
  antsRegistrationSyN.sh -d 3 -f "$REF" -m "$TPL" -o al_ -t r -n "$NT" >/dev/null 2>&1 \
    || { echo "[ERR] rigid reg age${AGE}_${SEX}"; exit 1; }
fi
# 2) FAST 3-class on the aligned brain -> pve_0=CSF, pve_1=GM, pve_2=WM
if [ ! -f fast_pve_2.nii.gz ]; then
  fast -t 1 -n 3 -g -o fast al_Warped.nii.gz >/dev/null 2>&1 || { echo "[ERR] FAST age${AGE}_${SEX}"; exit 1; }
fi
# 3) matched slices + volumes -> compact npz
python3 "$SCR/extract_slices.py" al_Warped.nii.gz fast_pve_0.nii.gz fast_pve_1.nii.gz fast_pve_2.nii.gz \
  "$OUT/slices_age${AGE}_${SEX}.npz" "$AGE" "$SEX"
echo "[done] age${AGE}_${SEX}"
INNER
