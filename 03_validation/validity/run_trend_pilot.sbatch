#!/usr/bin/env bash
#SBATCH --job-name=gw-trend
#SBATCH --output=gw-trend-%j.out
#SBATCH --error=gw-trend-%j.err
#SBATCH --time=03:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=12G
# Gray-white interface mismatch TREND pilot (surface metric, AFFINE).
# 3 age-6 girls x {age5-14 female + age6 male}. Per cell: affine-register
# subject->template, warp ?h.white surface, measure gray-white distance.
# Resumable (skips done warps), brain-masks templates before FAST, and never
# lets one bad cell abort the sweep.
set -uo pipefail                     # NOT -e: tolerate per-cell failures
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=/mnt/validity_heatmap_scripts
OUT=/mnt/Validity/heatmap_trend_pilot
TPLDIR=/mnt/Templates/UpdatedTemplates
WMDIR=$OUT/templates_wm
OUT_HOST=$DB/Validity/heatmap_trend_pilot
RESULTS=$OUT_HOST/trend_results.jsonl
mkdir -p "$OUT_HOST/templates_wm" "$OUT_HOST/cells"

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV=". /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null; export PATH=\$PATH:/opt/ANTs/install/bin ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$NT OMP_NUM_THREADS=$NT TMPDIR=$OUT;"

declare -A AGE=( [NDARxxxxxxxx]=6.068674 [NDARxxxxxxxx]=6.994182 [NDARxxxxxxxx]=6.695071 )
EIDS=(NDARxxxxxxxx NDARxxxxxxxx NDARxxxxxxxx)
TEMPLATES=(age5_female age6_female age7_female age8_female age9_female age10_female \
           age11_female age12_female age13_female age14_female age6_male)

# 0) brain-masked FAST WM boundary for each template (masking fixes the
#    differently-preprocessed age8_female / age6_male, which carry background).
for T in "${TEMPLATES[@]}"; do
  if [[ ! -f "$OUT_HOST/templates_wm/${T}_wm.nii.gz" ]]; then
    echo "[trend] FAST WM (masked): $T"
    run "$ENV fslmaths $TPLDIR/${T}_template.nii.gz -mas $TPLDIR/${T}_brain_mask.nii.gz $WMDIR/${T}_brain.nii.gz && \
         fast -t 1 -n 3 -g -o $WMDIR/${T}_fast $WMDIR/${T}_brain.nii.gz && \
         fslmaths ${WMDIR}/${T}_fast_pve_2.nii.gz -thr 0.5 -bin $WMDIR/${T}_wm.nii.gz && \
         rm -f $WMDIR/${T}_fast_pve_*.nii.gz $WMDIR/${T}_fast_seg.nii.gz $WMDIR/${T}_fast_mixeltype.nii.gz $WMDIR/${T}_brain.nii.gz" \
      || echo "[FAIL FAST] $T"
  fi
done

# 1) per subject x template cells
for eid in "${EIDS[@]}"; do
  src=/mnt/Validity/heatmap_pilot/age6_female/subjects/$eid
  fs=/mnt/TemplateTestSet/HBN_formatted_all/$eid
  sage=${AGE[$eid]}
  for T in "${TEMPLATES[@]}"; do
    tage=$(echo "$T" | sed -E 's/age([0-9]+)_.*/\1/')
    tsex=$(echo "$T" | sed -E 's/age[0-9]+_(.*)/\1/')
    cell=$OUT/cells/${eid}__${T}
    cell_host=$OUT_HOST/cells/${eid}__${T}
    [[ -f "$OUT_HOST/templates_wm/${T}_wm.nii.gz" ]] || { echo "[skip: no WM] $T"; continue; }
    # expensive affine+warp only if not already done
    if [[ ! -f "$cell_host/surf.npz" ]]; then
      run "$ENV mkdir -p $cell; \
           antsRegistrationSyN.sh -d 3 -f $TPLDIR/${T}_template.nii.gz -m $src/moving_csfNorm_rc.nii.gz \
              -o $cell/aff_ -t a -n $NT >/dev/null 2>&1 && \
           python3 $SCR/warp_surface_to_template.py $fs/mri/orig.mgz $fs/surf/lh.white $fs/surf/rh.white \
              $src/fs2mov_0GenericAffine.mat $cell/aff_0GenericAffine.mat $cell/surf.npz && \
           rm -f $cell/aff_Warped.nii.gz $cell/aff_InverseWarped.nii.gz" \
        || { echo "[FAIL warp] $eid $T"; continue; }
    fi
    # cheap measure (always; against the masked WM) -> per-cell json
    run "$ENV python3 $SCR/measure_cell.py $WMDIR/${T}_wm.nii.gz $cell/surf.npz $sage $tage $tsex $eid 6.0 > $cell/measure.json" \
      || echo "[FAIL measure] $eid $T"
    echo "[trend] $eid -> $T done"
  done
done

# 2) collate all per-cell measures into the results file
cat "$OUT_HOST"/cells/*/measure.json > "$RESULTS" 2>/dev/null || true
echo "[trend] DONE: $(wc -l < "$RESULTS") cells -> $RESULTS"
