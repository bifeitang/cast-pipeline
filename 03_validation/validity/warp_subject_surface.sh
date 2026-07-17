#!/bin/bash
# warp_subject_surface.sh  (runs INSIDE the apptainer container)
# Option B: bridge a subject's FreeSurfer ?h.white surface into template space.
# Reuses the existing moving->template transforms (reg_*) from the FAST pilot run;
# only adds a cheap FS->moving rigid registration + two point warps (SyN, affine).
#
# Usage: warp_subject_surface.sh <fs_dir> <subj_out_dir> <scripts_dir> [nthreads]
#   <fs_dir>      = FreeSurfer recon dir (has mri/orig.mgz, mri/brain.mgz, surf/?h.white)
#   <subj_out_dir>= pilot subject dir (has moving_csfNorm_rc.nii.gz + reg_* transforms)
set -euo pipefail

FS_DIR="${1:?need FreeSurfer recon dir}"
OUT="${2:?need subject out dir}"
SCRIPTS="${3:?need scripts dir}"
NT="${4:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT"
export OMP_NUM_THREADS="$NT"
cd "$OUT"

for f in moving_csfNorm_rc.nii.gz reg_0GenericAffine.mat reg_1InverseWarp.nii.gz; do
  [[ -f "$f" ]] || { echo "[ERROR] missing $f in $OUT (need the FAST-run transforms)" >&2; exit 1; }
done

# 1) FS brain (conformed scanner-RAS) -> NIfTI for the rigid registration.
python3 -c "import nibabel as nib; img=nib.load('$FS_DIR/mri/brain.mgz'); nib.save(nib.Nifti1Image(img.get_fdata().astype('float32'), img.affine), 'brain_fs.nii.gz')"

# 2) FS -> moving rigid (same subject, same raw scan: recovers any re-center/rotate).
if [[ ! -f fs2mov_0GenericAffine.mat ]]; then
  antsRegistrationSyN.sh -d 3 -f moving_csfNorm_rc.nii.gz -m brain_fs.nii.gz \
    -o fs2mov_ -t r -n "$NT"
fi

# 3) Warp the ?h.white surface into template space: SyN (full) and affine (linear).
python3 "$SCRIPTS/warp_surface_to_template.py" \
  "$FS_DIR/mri/orig.mgz" "$FS_DIR/surf/lh.white" "$FS_DIR/surf/rh.white" \
  fs2mov_0GenericAffine.mat reg_0GenericAffine.mat surf_syn.npz reg_1InverseWarp.nii.gz
python3 "$SCRIPTS/warp_surface_to_template.py" \
  "$FS_DIR/mri/orig.mgz" "$FS_DIR/surf/lh.white" "$FS_DIR/surf/rh.white" \
  fs2mov_0GenericAffine.mat reg_0GenericAffine.mat surf_affine.npz

rm -f fs2mov_Warped.nii.gz fs2mov_InverseWarped.nii.gz brain_fs.nii.gz 2>/dev/null || true
echo "[done] surfaces warped -> $OUT/surf_syn.npz , surf_affine.npz"
