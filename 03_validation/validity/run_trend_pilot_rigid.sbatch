#!/usr/bin/env bash
#SBATCH --job-name=gw-trend-rigid
#SBATCH --output=gw-trend-rigid-%j.out
#SBATCH --error=gw-trend-rigid-%j.err
#SBATCH --time=02:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=12G
# Gray-white mismatch TREND, RIGID registration (no scaling) -> keeps the
# subject's true brain SIZE, so a 6 y-old aligned to an older template carries a
# size mismatch and the gray-white error should RISE with age mismatch (the
# age-specificity trend). Reuses the masked templates_wm + per-subject fs2mov
# bridges already on disk; only the rigid moving->template reg is new.
set -uo pipefail
NT="${SLURM_CPUS_PER_TASK:-8}"
DB="${DB:-${DB:-/path/to/cast_data}}"
C="${C:-${C_REG:-cast_reg.sif}}"
SCR=/mnt/validity_heatmap_scripts
OUT=/mnt/Validity/heatmap_trend_pilot
TPLDIR=/mnt/Templates/UpdatedTemplates
WMDIR=$OUT/templates_wm
OUT_HOST=$DB/Validity/heatmap_trend_pilot
RESULTS=$OUT_HOST/trend_results_rigid.jsonl
mkdir -p "$OUT_HOST/cells_rigid"

run() { apptainer exec --bind "$DB:/mnt" "$C" /bin/bash -c "$1"; }
ENV=". /usr/local/fsl/etc/fslconf/fsl.sh 2>/dev/null; export PATH=\$PATH:/opt/ANTs/install/bin ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$NT OMP_NUM_THREADS=$NT TMPDIR=$OUT;"

declare -A AGE=( [NDARxxxxxxxx]=6.068674 [NDARxxxxxxxx]=6.994182 [NDARxxxxxxxx]=6.695071 )
EIDS=(NDARxxxxxxxx NDARxxxxxxxx NDARxxxxxxxx)
TEMPLATES=(age5_female age6_female age7_female age8_female age9_female age10_female \
           age11_female age12_female age13_female age14_female age6_male)

for eid in "${EIDS[@]}"; do
  src=/mnt/Validity/heatmap_pilot/age6_female/subjects/$eid
  fs=/mnt/TemplateTestSet/HBN_formatted_all/$eid
  sage=${AGE[$eid]}
  for T in "${TEMPLATES[@]}"; do
    tage=$(echo "$T" | sed -E 's/age([0-9]+)_.*/\1/')
    tsex=$(echo "$T" | sed -E 's/age[0-9]+_(.*)/\1/')
    cell=$OUT/cells_rigid/${eid}__${T}
    cell_host=$OUT_HOST/cells_rigid/${eid}__${T}
    [[ -f "$OUT_HOST/templates_wm/${T}_wm.nii.gz" ]] || { echo "[skip: no WM] $T"; continue; }
    if [[ ! -f "$cell_host/surf.npz" ]]; then
      run "$ENV mkdir -p $cell; \
           antsRegistrationSyN.sh -d 3 -f $TPLDIR/${T}_template.nii.gz -m $src/moving_csfNorm_rc.nii.gz \
              -o $cell/rig_ -t r -n $NT >/dev/null 2>&1 && \
           python3 $SCR/warp_surface_to_template.py $fs/mri/orig.mgz $fs/surf/lh.white $fs/surf/rh.white \
              $src/fs2mov_0GenericAffine.mat $cell/rig_0GenericAffine.mat $cell/surf.npz && \
           rm -f $cell/rig_Warped.nii.gz $cell/rig_InverseWarped.nii.gz" \
        || { echo "[FAIL warp] $eid $T"; continue; }
    fi
    run "$ENV python3 $SCR/measure_cell.py $WMDIR/${T}_wm.nii.gz $cell/surf.npz $sage $tage $tsex $eid 6.0 > $cell/measure.json" \
      || echo "[FAIL measure] $eid $T"
    echo "[rigid] $eid -> $T done"
  done
done
cat "$OUT_HOST"/cells_rigid/*/measure.json > "$RESULTS" 2>/dev/null || true
echo "[rigid] DONE: $(wc -l < "$RESULTS") cells -> $RESULTS"
