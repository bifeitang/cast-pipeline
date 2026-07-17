#!/usr/bin/env bash
#SBATCH --job-name=surf-validate
#SBATCH --output=surf-validate-%j.out
#SBATCH --error=surf-validate-%j.err
#SBATCH --time=00:30:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=10G
# Validate the Option B transform chain on ONE subject (the 40mm-shift hard case)
# before committing to the full run. Confirms antsApplyTransformsToPoints order is
# correct by checking the warped surface lands on the template gray-white boundary.
set -euo pipefail

EID="${1:-NDARxxxxxxxx}"
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
TPL_ID=age6_female

FS_DIR=/mnt/TemplateTestSet/HBN_formatted_all/$EID
OUT=/mnt/Validity/heatmap_pilot/$TPL_ID/subjects/$EID
SCR=/mnt/validity_heatmap_scripts
TPL_WM=/mnt/Validity/heatmap_pilot/$TPL_ID/template_wm.nii.gz

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }

echo "[validate] warping surface for $EID"
run ". /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null; export PATH=\$PATH:/opt/ANTs/install/bin ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$NT OMP_NUM_THREADS=$NT; \
     /bin/bash $SCR/warp_subject_surface.sh $FS_DIR $OUT $SCR $NT"

echo "[validate] self-check: does the warped SyN surface land on the template WM?"
run "python3 - <<'PY'
import numpy as np, nibabel as nib
from scipy import ndimage
from scipy.spatial import cKDTree
t = nib.load('$TPL_WM'); wm = t.get_fdata() > 0.5
bd = wm & ~ndimage.binary_erosion(wm)
vox = np.argwhere(bd)
ras = (t.affine @ np.c_[vox, np.ones(len(vox))].T).T[:, :3]
d = np.load('$OUT/surf_syn.npz'); v = d['verts'].astype(float)
dist, _ = cKDTree(v).query(ras, k=1)
print(f'  template boundary voxels   : {len(ras):,}')
print(f'  warped surf vertices       : {len(v):,}')
print(f'  median nearest dist (mm)   : {np.median(dist):.3f}')
print(f'  mean   nearest dist (mm)   : {dist.mean():.3f}')
print(f'  p95    nearest dist (mm)   : {np.percentile(dist,95):.3f}')
print(f'  frac boundary within 2mm   : {(dist<=2).mean():.3f}')
print(f'  surf centroid (template RAS): {v.mean(0).round(1)}')
print(f'  boundary centroid (RAS)     : {ras.mean(0).round(1)}')
print(f'  centroid |offset| (mm)      : {np.linalg.norm(v.mean(0)-ras.mean(0)):.1f}')
PY"
echo "[validate] DONE"
