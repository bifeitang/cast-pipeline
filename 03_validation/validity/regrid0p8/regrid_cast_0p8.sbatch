#!/usr/bin/env bash
#SBATCH --job-name=regrid0p8
#SBATCH --output=regrid0p8-%j.out
#SBATCH --error=regrid0p8-%j.err
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
# RESOLUTION-ARTIFACT CONTROL, step 1: regrid the SEVEN CAST templates that are
# currently 1.0 mm (176x256x170, ages 5-12) to 0.8 mm isotropic, then re-derive
# the WM mask the SAME way the benchmark did for CAST (brain-mask -> FAST 3-class
# -> pve_2>0.5). Also emit GM/WM/CSF TPMs at 0.8 mm for the eventual release.
#
# Intensity image  -> ResampleImage linear  (interp code 0)
# Brain mask       -> ResampleImage NN      (interp code 1)  then re-binarize
# World space (origin/direction) is preserved by ResampleImage; only the grid
# spacing/size changes. Output size = round(old_size * old_spacing / 0.8).
#
# Output tree: $DB/Templates/UpdatedTemplates_0p8/
#   age<a>_<sex>_template.nii.gz     (0.8 mm intensity, brain-masked-region intact)
#   age<a>_<sex>_brain_mask.nii.gz   (0.8 mm, NN-resampled, binarized)
#   age<a>_<sex>_wm.nii.gz           (0.8 mm WM mask, FAST pve_2>0.5)   <- benchmark target
#   age<a>_<sex>_{gm,wm,csf}.nii.gz  (0.8 mm TPM-derived tissue masks, for release)
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SRC=/mnt/Templates/UpdatedTemplates
DST=/mnt/Templates/UpdatedTemplates_0p8
DSTH=$DB/Templates/UpdatedTemplates_0p8
mkdir -p "$DSTH"

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='export PATH=$PATH:/opt/ANTs/install/bin; . /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'

# The 7 currently-1.0mm CAST templates covering ages 5-12.
TEMPLATES="age5_male age6_female age7_male age8_male age8_female age9_female age10_female"

for T in $TEMPLATES; do
  echo "==================== $T ===================="
  if [[ -f "$DSTH/${T}_wm.nii.gz" && -f "$DSTH/${T}_template.nii.gz" ]]; then
    echo "[skip] $T already regridded"; continue
  fi

  # 1) Resample intensity (linear) and brain mask (NN) to 0.8 mm isotropic.
  #    ResampleImage <dim> <in> <out> MxNxO <size=1,spacing=0> <interp>
  #    Here MxNxO is the desired SPACING, so the 5th arg MUST be 0 (spacing mode);
  #    interp: 0=linear, 1=nearestneighbor. World space (origin/direction) is
  #    preserved; only grid spacing/size change (176x256x170 -> 220x320x213).
  run "$ENV \
    ResampleImage 3 $SRC/${T}_template.nii.gz   $DST/${T}_template.nii.gz   0.8x0.8x0.8 0 0 && \
    ResampleImage 3 $SRC/${T}_brain_mask.nii.gz $DST/${T}_brain_mask.nii.gz 0.8x0.8x0.8 0 1 && \
    fslmaths $DST/${T}_brain_mask.nii.gz -thr 0.5 -bin $DST/${T}_brain_mask.nii.gz" \
    || { echo "[FAIL resample] $T"; continue; }

  # 2) Brain-mask the 0.8 mm intensity (background shell breaks FAST 3-class KMeans),
  #    then FAST 3-class. pve_2 = WM, pve_1 = GM, pve_0 = CSF (FSL convention,
  #    matched to make_template_wm.sbatch / make_template_tissue_masks.sbatch).
  run "$ENV \
    fslmaths $DST/${T}_template.nii.gz -mas $DST/${T}_brain_mask.nii.gz $DST/${T}_brain.nii.gz && \
    fast -t 1 -n 3 -g -o $DST/${T}_fast $DST/${T}_brain.nii.gz && \
    fslmaths $DST/${T}_fast_pve_2.nii.gz -thr 0.5 -bin $DST/${T}_wm.nii.gz && \
    fslmaths $DST/${T}_fast_pve_1.nii.gz -thr 0.5 -bin $DST/${T}_gm.nii.gz && \
    fslmaths $DST/${T}_fast_pve_0.nii.gz -thr 0.5 -bin $DST/${T}_csf.nii.gz && \
    rm -f $DST/${T}_fast_pve_*.nii.gz $DST/${T}_fast_seg*.nii.gz $DST/${T}_fast_mixeltype.nii.gz $DST/${T}_fast_pveseg.nii.gz $DST/${T}_brain.nii.gz" \
    || { echo "[FAIL fast] $T"; continue; }

  # 3) QC: confirm 0.8 mm headers on the three benchmark-relevant volumes.
  run "$ENV python3 - <<PY
import nibabel as nib
for suf in ('template','brain_mask','wm'):
    i=nib.load('$DST/${T}_'+suf+'.nii.gz')
    z=tuple(round(float(x),4) for x in i.header.get_zooms()[:3])
    print('  [QC] $T',suf,'dim',i.shape,'zooms',z,'nvox>0',int((i.get_fdata()>0.5).sum()) if suf!='template' else '-')
PY"
  echo "[ok] $T"
done

echo "==================== DONE ===================="
ls -la "$DSTH"/*_template.nii.gz 2>/dev/null
echo "templates regridded: $(ls "$DSTH"/*_template.nii.gz 2>/dev/null | wc -l) / 7"
echo "wm masks present:    $(ls "$DSTH"/*_wm.nii.gz 2>/dev/null | wc -l) / 7"
