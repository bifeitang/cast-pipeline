#!/usr/bin/env bash
#SBATCH --job-name=validity-surf
#SBATCH --output=validity-surf-%j.out
#SBATCH --error=validity-surf-%j.err
#SBATCH --time=00:40:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=10G
# Option B full pilot: warp all 3 subjects' FreeSurfer ?h.white surfaces into the
# matched template and aggregate the SURFACE-based gray-white validity heat map
# (SyN + affine). Reuses the moving->template reg_* transforms already on disk.
set -euo pipefail

TPL_ID="${1:-age6_female}"
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=/mnt/validity_heatmap_scripts
ROOT=/mnt/Validity/heatmap_pilot/$TPL_ID
TPL_WM=$ROOT/template_wm.nii.gz

# Pilot EIDs (first 3 age-6 test subjects, same as the FAST run).
EIDS=(NDARxxxxxxxx NDARxxxxxxxx NDARxxxxxxxx)

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENVSET=". /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null; export PATH=\$PATH:/opt/ANTs/install/bin ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$NT OMP_NUM_THREADS=$NT;"

SYN=(); AFF=()
for eid in "${EIDS[@]}"; do
  fs=/mnt/TemplateTestSet/HBN_formatted_all/$eid
  out=$ROOT/subjects/$eid
  echo "[surf] warping $eid"
  run "$ENVSET /bin/bash $SCR/warp_subject_surface.sh $fs $out $SCR $NT"
  SYN+=("$out/surf_syn.npz")
  AFF+=("$out/surf_affine.npz")
done

echo "[surf] aggregating SyN"
run "$ENVSET CORTICAL_CUT_MM=6.0 python3 $SCR/validity_heatmap_aggregate_surf.py \
     syn $TPL_WM $ROOT/${TPL_ID}_syn_surf ${SYN[*]}"
echo "[surf] aggregating affine"
run "$ENVSET CORTICAL_CUT_MM=6.0 python3 $SCR/validity_heatmap_aggregate_surf.py \
     affine $TPL_WM $ROOT/${TPL_ID}_affine_surf ${AFF[*]}"

echo "[surf] DONE -> $ROOT (*_surf_*)"
