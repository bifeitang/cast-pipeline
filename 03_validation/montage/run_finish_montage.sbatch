#!/usr/bin/env bash
#SBATCH --job-name=tpl-finish
#SBATCH --output=tpl-finish-%j.out
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=32G
#SBATCH --time=01:30:00
# Self-healing finisher: for any age/sex template missing slices_*.npz, (re)run rigid align
# if needed, FAST, and slice extraction. SEQUENTIAL -> no concurrent-FAST contention.
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}

apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -s <<'INNER'
set -uo pipefail
. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null || true
export PATH="$PATH:/opt/ANTs/install/bin" ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=8 OMP_NUM_THREADS=8
DB=/mnt; SCR=$DB/template_montage_scripts
TPLDIR=$DB/Templates/UpdatedTemplates
REF=$TPLDIR/age11_male_template.nii.gz
for AGE in 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do
  for SEX in male female; do
    OUT=$DB/Templates/montage_aligned/age${AGE}_${SEX}; mkdir -p "$OUT"; cd "$OUT"; export TMPDIR=$OUT
    [ -f "$OUT/slices_age${AGE}_${SEX}.npz" ] && continue   # already done
    TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
    [ -f "$TPL" ] || { echo "[MISS-TPL] age${AGE}_${SEX}"; continue; }
    if [ ! -f al_Warped.nii.gz ]; then
      antsRegistrationSyN.sh -d 3 -f "$REF" -m "$TPL" -o al_ -t r -n 8 >/dev/null 2>&1 \
        || { echo "[ERR-REG] age${AGE}_${SEX}"; continue; }
    fi
    rm -f fast_*.nii.gz al_brain.nii.gz
    # strip the low-amplitude background noise floor (tissue >=~1, noise <0.01) so FAST
    # K-means can init 3 tissue classes; CSF (~1) is well above the 0.25 threshold.
    fslmaths al_Warped.nii.gz -thr 0.25 al_brain.nii.gz
    if ! fast -t 1 -n 3 -g -o fast al_brain.nii.gz >"fast_${AGE}_${SEX}.log" 2>&1; then
      echo "[ERR-FAST] age${AGE}_${SEX} (see log)"; continue
    fi
    python3 "$SCR/extract_slices.py" al_Warped.nii.gz fast_pve_0.nii.gz fast_pve_1.nii.gz fast_pve_2.nii.gz \
      "$OUT/slices_age${AGE}_${SEX}.npz" "$AGE" "$SEX" && echo "[ok] age${AGE}_${SEX}"
  done
done
echo "=== total slices ==="; ls $DB/Templates/montage_aligned/*/slices_*.npz | wc -l
INNER
