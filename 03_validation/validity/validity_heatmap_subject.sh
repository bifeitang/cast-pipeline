#!/bin/bash
# validity_heatmap_subject.sh  (runs INSIDE the apptainer container)
# Register one held-out subject to the matched template and produce the
# warped subject T1 (both SyN and affine-only levels) plus a FAST WM mask
# for each, so the gray-white interface error can be measured downstream.
#
# Usage: validity_heatmap_subject.sh <subject_t1> <template_t1> <outdir> [nthreads]
set -euo pipefail

SUBJ="${1:?need subject T1}"
TPL="${2:?need template T1}"
OUTDIR="${3:?need outdir}"
NT="${4:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT"
export OMP_NUM_THREADS="$NT"

mkdir -p "$OUTDIR"; cd "$OUTDIR"

# 1) Register subject -> template (rigid+affine+SyN). Reuse if already present.
if [[ ! -f reg_1Warp.nii.gz || ! -f reg_0GenericAffine.mat ]]; then
  antsRegistrationSyN.sh -d 3 -f "$TPL" -m "$SUBJ" -o reg_ -n "$NT" -t s
fi

# SyN-warped subject in template space is reg_Warped.nii.gz
cp -f reg_Warped.nii.gz subj_syn.nii.gz

# 2) Affine-only warped subject in template space (linear alignment, no SyN)
antsApplyTransforms -d 3 -i "$SUBJ" -r "$TPL" \
  -t reg_0GenericAffine.mat -n Linear -o subj_affine.nii.gz

# 3) FAST 3-class segmentation on each warped subject -> WM mask.
#    For a T1, 3-class FAST orders classes by increasing intensity:
#    pve_0 = CSF, pve_1 = GM, pve_2 = WM. WM mask = pve_2 thresholded at 0.5.
for lvl in subj_syn subj_affine; do
  fast -t 1 -n 3 -g -o "${lvl}_fast" "${lvl}.nii.gz"
  fslmaths "${lvl}_fast_pve_2.nii.gz" -thr 0.5 -bin "${lvl}_wm.nii.gz"
done

# Trim bulky reg intermediates we no longer need (keep transforms + wm masks)
rm -f reg_Warped.nii.gz reg_InverseWarped.nii.gz \
      subj_syn_fast_seg.nii.gz subj_affine_fast_seg.nii.gz \
      subj_syn_fast_mixeltype.nii.gz subj_affine_fast_mixeltype.nii.gz 2>/dev/null || true

echo "[done] $OUTDIR"
