#!/usr/bin/env bash
#SBATCH --job-name=gw-refprep
#SBATCH --output=gw-refprep-%j.out
#SBATCH --error=gw-refprep-%j.err
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=01:30:00
# Pre-build every reference-atlas WM mask ONCE, serially, before the per-subject
# refbench array runs. Avoids 50 array tasks racing to FAST the same NKI volume
# (they share a fast- output prefix). The array's own guards then just find the
# masks already present. References = the distinct NKI templates + Fonov bands
# actually used by refbench_manifest.txt.
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
MAN=$DB/validity_heatmap_scripts/refbench_manifest.txt
REFWM=$DB/Validity/refbench/templates_wm
mkdir -p "$REFWM"
run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV='. /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null;'

# distinct NKI templates used
for NKI_BN in $(awk '{print $4}' "$MAN" | sort -u); do
  TAG=${NKI_BN%_brain_template.nii.gz}
  WM=$REFWM/${TAG}_wm.nii.gz
  [[ -f "$WM" ]] && { echo "[have] $TAG"; continue; }
  echo "[prep] FAST WM $TAG"
  run "$ENV fast -t 1 -n 3 -g -o /mnt/Validity/refbench/templates_wm/${TAG}_fast /mnt/Templates/$NKI_BN && \
       fslmaths /mnt/Validity/refbench/templates_wm/${TAG}_fast_pve_2.nii.gz -thr 0.5 -bin /mnt/Validity/refbench/templates_wm/${TAG}_wm.nii.gz && \
       rm -f /mnt/Validity/refbench/templates_wm/${TAG}_fast_pve_*.nii.gz /mnt/Validity/refbench/templates_wm/${TAG}_fast_seg.nii.gz /mnt/Validity/refbench/templates_wm/${TAG}_fast_mixeltype.nii.gz" \
    || echo "[FAIL NKI WM] $TAG"
done

# distinct Fonov bands used (0-1 prob map -> threshold 0.5)
for FON_PFX in $(awk '{print $5}' "$MAN" | sort -u); do
  TAG=$(echo "$FON_PFX" | tr '.' 'p' | tr '-' '_')
  WM=$REFWM/${TAG}_wm.nii.gz
  [[ -f "$WM" ]] && { echo "[have] $TAG"; continue; }
  echo "[prep] threshold WM $TAG"
  run "$ENV fslmaths /mnt/Templates/Fonov/${FON_PFX}_wm.nii -thr 0.5 -bin /mnt/Validity/refbench/templates_wm/${TAG}_wm.nii.gz" \
    || echo "[FAIL Fonov WM] $TAG"
done

echo "[prep] reference WM masks present:"; ls -1 "$REFWM"/*_wm.nii.gz 2>/dev/null
