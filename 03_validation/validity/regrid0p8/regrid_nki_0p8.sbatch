#!/usr/bin/env bash
#SBATCH --job-name=regridnki0p8
#SBATCH --output=regridnki0p8-%j.out
#SBATCH --error=regridnki0p8-%j.err
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
# GRID-NEUTRAL CONTROL, step 1: regrid the NKI reference templates used by the
# affected (5-12, matched to a regridded CAST template) subjects from 1.0 mm
# (182x218x182) to 0.8 mm isotropic, and re-derive their WM masks the SAME way
# the original refbench did for NKI: FAST 3-class directly on the (already
# skull-stripped) NKI intensity volume, pve_2>0.5. This lets us run a pure
# grid-matched CAST-0.8 vs NKI-0.8 comparison on the exact same subjects.
#
# NKI volumes are skull-stripped already (no brain_mask file), so we FAST the
# resampled intensity directly -- identical recipe to refbench_worker.sh step 0.
set -uo pipefail
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SRC=/mnt/Templates
DST=/mnt/Validity/refbench_0p8/templates_nki0p8
DSTH=$DB/Validity/refbench_0p8/templates_nki0p8
mkdir -p "$DSTH"

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='export PATH=$PATH:/opt/ANTs/install/bin; . /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'

# Distinct NKI templates used by the affected subjects (ages 5-12 mapped to the
# 7 regridded CAST strata). 5,6 -> 6a7; 7->7; 8->8; 9->9; 10->10.
NKI_TAGS="NKI_age6a7 NKI_age7 NKI_age8 NKI_age9 NKI_age10"

for TAG in $NKI_TAGS; do
  echo "==================== $TAG ===================="
  if [[ -f "$DSTH/${TAG}_wm.nii.gz" && -f "$DSTH/${TAG}_brain_template.nii.gz" ]]; then
    echo "[skip] $TAG already regridded"; continue
  fi
  run "$ENV \
    ResampleImage 3 $SRC/${TAG}_brain_template.nii.gz $DST/${TAG}_brain_template.nii.gz 0.8x0.8x0.8 0 0 && \
    fast -t 1 -n 3 -g -o $DST/${TAG}_fast $DST/${TAG}_brain_template.nii.gz && \
    fslmaths $DST/${TAG}_fast_pve_2.nii.gz -thr 0.5 -bin $DST/${TAG}_wm.nii.gz && \
    rm -f $DST/${TAG}_fast_pve_*.nii.gz $DST/${TAG}_fast_seg*.nii.gz $DST/${TAG}_fast_mixeltype.nii.gz $DST/${TAG}_fast_pveseg.nii.gz" \
    || { echo "[FAIL] $TAG"; continue; }
  run "$ENV python3 - <<PY
import nibabel as nib
for suf in ('brain_template','wm'):
    i=nib.load('$DST/${TAG}_'+suf+'.nii.gz')
    z=tuple(round(float(x),4) for x in i.header.get_zooms()[:3])
    print('  [QC] $TAG',suf,'dim',i.shape,'zooms',z)
PY"
  echo "[ok] $TAG"
done
echo "==================== DONE ===================="
ls -la "$DSTH"/*_brain_template.nii.gz 2>/dev/null
echo "nki regridded: $(ls "$DSTH"/*_wm.nii.gz 2>/dev/null | wc -l) / 5"
