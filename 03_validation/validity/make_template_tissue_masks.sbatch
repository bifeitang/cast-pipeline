#!/usr/bin/env bash
#SBATCH --job-name=tpl-tiss
#SBATCH --output=tpl-tiss-%j.out
#SBATCH --error=tpl-tiss-%j.err
#SBATCH --time=02:00:00
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=8G
# Template GM/WM/CSF masks (FAST 3-class on brain-masked template) for the tissue-specific
# Jacobian (section 4.3). Keeps all three pve maps. Also (re)creates age12_male WM, which
# the earlier WM job left unfinished (15/16).
set -uo pipefail
DB=${DB:-/path/to/cast_data}
C=${C_REG:-cast_reg.sif}
TPLDIR=/mnt/Templates/UpdatedTemplates
TH=$DB/Validity/templates_tissue
WMH=$DB/Validity/templates_wm
mkdir -p "$TH" "$WMH"
T=/mnt/Validity/templates_tissue
run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'
for a in 5 6 7 8 9 10 11 12; do for s in female male; do
  ID=age${a}_${s}
  if [[ -f "$TH/${ID}_gm.nii.gz" && -f "$TH/${ID}_wm.nii.gz" && -f "$TH/${ID}_csf.nii.gz" ]]; then echo "[skip] $ID"; continue; fi
  echo "[tiss] $ID"
  run "$ENV fslmaths $TPLDIR/${ID}_template.nii.gz -mas $TPLDIR/${ID}_brain_mask.nii.gz $T/${ID}_brain.nii.gz && \
       fast -t 1 -n 3 -g -o $T/${ID}_fast $T/${ID}_brain.nii.gz && \
       fslmaths $T/${ID}_fast_pve_0.nii.gz -thr 0.5 -bin $T/${ID}_csf.nii.gz && \
       fslmaths $T/${ID}_fast_pve_1.nii.gz -thr 0.5 -bin $T/${ID}_gm.nii.gz && \
       fslmaths $T/${ID}_fast_pve_2.nii.gz -thr 0.5 -bin $T/${ID}_wm.nii.gz && \
       rm -f $T/${ID}_fast_pve_*.nii.gz $T/${ID}_fast_seg*.nii.gz $T/${ID}_fast_mixeltype.nii.gz $T/${ID}_fast_pveseg.nii.gz $T/${ID}_brain.nii.gz" \
    && { echo "[ok] $ID"; cp -f "$TH/${ID}_wm.nii.gz" "$WMH/${ID}_wm.nii.gz" 2>/dev/null || true; } || echo "[FAIL] $ID"
done; done
echo DONE; ls "$TH"/*_wm.nii.gz 2>/dev/null | wc -l
