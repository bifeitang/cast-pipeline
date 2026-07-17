#!/bin/bash
# sweep_worker.sh  (runs INSIDE the apptainer container)
# One subject of the at-scale gray-white validity sweep.
#   MATCHED template -> SyN  (sub-voxel validity heat map + affine sex baseline)
#   CROSS-SEX template -> affine (opposite-sex penalty; affine isolates shape)
# Args: <EID> <AGE> <SEX> <NT>
# Assumes host already extracted OUT/moving.nii.gz from the subject tarball.
set -uo pipefail
EID="${1:?EID}"; AGE="${2:?AGE}"; SEX="${3:?SEX}"; NT="${4:-8}"
if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"
OPP=female; [[ "$SEX" == female ]] && OPP=male
TPLDIR=/mnt/Templates/UpdatedTemplates
WMDIR=/mnt/Validity/templates_wm
SCR=/mnt/validity_heatmap_scripts
FS=/mnt/TemplateTestSet/HBN_formatted_all/$EID
OUT=/mnt/Validity/sweep/$EID
M_TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
X_TPL=$TPLDIR/age${AGE}_${OPP}_template.nii.gz
M_WM=$WMDIR/age${AGE}_${SEX}_wm.nii.gz
X_WM=$WMDIR/age${AGE}_${OPP}_wm.nii.gz
export TMPDIR=$OUT
cd "$OUT" || { echo "[ERR] no $OUT"; exit 1; }
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving.nii.gz for $EID"; exit 1; }
# 1) FS brain -> NIfTI for the FS->moving rigid bridge
if [[ ! -f fs2mov_0GenericAffine.mat ]]; then
  python3 -c "import nibabel as nib; i=nib.load('$FS/mri/brain.mgz'); nib.save(nib.Nifti1Image(i.get_fdata().astype('float32'), i.affine), 'brain_fs.nii.gz')" || { echo "[ERR] brain_fs $EID"; exit 1; }
  antsRegistrationSyN.sh -d 3 -f moving.nii.gz -m brain_fs.nii.gz -o fs2mov_ -t r -n "$NT" >/dev/null 2>&1 || { echo "[ERR] fs2mov $EID"; exit 1; }
fi
# 2) MATCHED template: SyN
if [[ ! -f m_1InverseWarp.nii.gz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$M_TPL" -m moving.nii.gz -o m_ -t s -n "$NT" >/dev/null 2>&1 || { echo "[ERR] matched-syn $EID"; exit 1; }
fi
# matched SyN + affine surfaces
[[ -f surf_matched_syn.npz ]]    || python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" fs2mov_0GenericAffine.mat m_0GenericAffine.mat surf_matched_syn.npz m_1InverseWarp.nii.gz || echo "[WARN] warp matched_syn $EID"
[[ -f surf_matched_affine.npz ]] || python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" fs2mov_0GenericAffine.mat m_0GenericAffine.mat surf_matched_affine.npz || echo "[WARN] warp matched_aff $EID"
[[ -f surf_matched_syn.npz ]]    && python3 "$SCR/measure_cell.py" "$M_WM" surf_matched_syn.npz    "$AGE" "$AGE" "$SEX" "$EID" 6.0 > meas_matched_syn.json    2>/dev/null
[[ -f surf_matched_affine.npz ]] && python3 "$SCR/measure_cell.py" "$M_WM" surf_matched_affine.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 > meas_matched_affine.json 2>/dev/null
# 3) CROSS-SEX template: affine only
if [[ ! -f x_0GenericAffine.mat ]]; then
  antsRegistrationSyN.sh -d 3 -f "$X_TPL" -m moving.nii.gz -o x_ -t a -n "$NT" >/dev/null 2>&1 || echo "[WARN] cross-aff reg $EID"
fi
[[ -f x_0GenericAffine.mat && ! -f surf_cross_affine.npz ]] && python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" fs2mov_0GenericAffine.mat x_0GenericAffine.mat surf_cross_affine.npz || true
[[ -f surf_cross_affine.npz ]] && python3 "$SCR/measure_cell.py" "$X_WM" surf_cross_affine.npz "$AGE" "$AGE" "$OPP" "$EID" 6.0 > meas_cross_affine.json 2>/dev/null
# 4) cleanup heavy intermediates; keep npz + measures + the affine mats
rm -f m_1Warp.nii.gz m_1InverseWarp.nii.gz m_Warped.nii.gz m_InverseWarped.nii.gz \
      x_Warped.nii.gz x_InverseWarped.nii.gz fs2mov_Warped.nii.gz fs2mov_InverseWarped.nii.gz \
      brain_fs.nii.gz moving.nii.gz 2>/dev/null || true
echo "[done] $EID age$AGE $SEX"
