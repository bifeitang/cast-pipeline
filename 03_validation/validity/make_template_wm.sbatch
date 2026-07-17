#!/usr/bin/env bash
#SBATCH --job-name=tpl-wm
#SBATCH --output=tpl-wm-%j.out
#SBATCH --error=tpl-wm-%j.err
#SBATCH --time=01:00:00
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=8G
# STEP 1: per-template WM masks (FAST pve_2>0.5 on brain-masked template) for all
# matched strata used by the validity sweep. Brain-mask before FAST (background
# shell breaks 3-class KMeans). Canonical output: Validity/templates_wm/<id>_wm.nii.gz
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
TPLDIR=/mnt/Templates/UpdatedTemplates
WMH=$DB/Validity/templates_wm
mkdir -p "$WMH"
WM=/mnt/Validity/templates_wm
run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'
IDS=""
for a in 5 6 7 8 9 10 11 12; do for s in female male; do IDS="$IDS age${a}_${s}"; done; done
for T in $IDS; do
  if [[ -f "$WMH/${T}_wm.nii.gz" ]]; then echo "[skip] $T"; continue; fi
  echo "[wm] $T"
  run "$ENV fslmaths $TPLDIR/${T}_template.nii.gz -mas $TPLDIR/${T}_brain_mask.nii.gz $WM/${T}_brain.nii.gz && \
       fast -t 1 -n 3 -g -o $WM/${T}_fast $WM/${T}_brain.nii.gz && \
       fslmaths $WM/${T}_fast_pve_2.nii.gz -thr 0.5 -bin $WM/${T}_wm.nii.gz && \
       rm -f $WM/${T}_fast_pve_*.nii.gz $WM/${T}_fast_seg*.nii.gz $WM/${T}_fast_mixeltype.nii.gz $WM/${T}_fast_pveseg.nii.gz $WM/${T}_brain.nii.gz" \
    && echo "[ok] $T" || echo "[FAIL] $T"
done
echo DONE
ls -la "$WMH"/*_wm.nii.gz 2>/dev/null | wc -l
