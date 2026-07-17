#!/usr/bin/env bash
#SBATCH --job-name=validity-pilot
#SBATCH --output=validity-pilot-%j.out
#SBATCH --error=validity-pilot-%j.err
#SBATCH --time=03:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=14G
#
# PILOT: gray-white interface error heat map (plan 4.1) on a few subjects of
# ONE stratum, so the method + numbers can be reviewed before any full batch.
#
# Usage:
#   sbatch run_validity_pilot.sbatch [TPL_AGE] [TPL_SEX] [N_SUBJECTS]
# Defaults: 6 female 3
set -euo pipefail

TPL_AGE="${1:-6}"
TPL_SEX="${2:-female}"
NSUB="${3:-3}"
NT="${SLURM_CPUS_PER_TASK:-8}"

ROOT_DIR="${PROJECT_ROOT:-/path/to/project}"
DB_DIR="$ROOT_DIR/PediatricMriDB"
CONTAINER="${C_REG:-cast_reg.sif}"
SCRIPTS="$DB_DIR/validity_heatmap_scripts"

TPL_ID="age${TPL_AGE}_${TPL_SEX}"
OUTROOT="$DB_DIR/Validity/heatmap_pilot/$TPL_ID"
TMP="$ROOT_DIR/TemplateCreationTemp/validity_${TPL_ID}_${SLURM_JOB_ID:-local}"
mkdir -p "$OUTROOT" "$TMP"

# Pick the first N test subjects of the template's age. The MOVING image is the
# CSF-normalized, re-centered INTENSITY T1 inside each subject tarball
# (subj_<eid>_csfNorm_rc.nii.gz) -- same preprocessing/space the templates were
# built from. NOT the binary processed_centered mask. (Sex-matching enforced in
# the full run once a sex roster exists; pilot validates the method.)
AGE_DIR="$DB_DIR/TemplateTestSet/hbn_grouped_by_age/$TPL_AGE"
mapfile -t TARS < <(find "$AGE_DIR" -maxdepth 1 -type f -name '*.tar.gz' | sort | head -n "$NSUB")
if (( ${#TARS[@]} == 0 )); then echo "[ERROR] no subject tarballs in $AGE_DIR" >&2; exit 1; fi
echo "[pilot] template=$TPL_ID  n_subjects=${#TARS[@]}"
printf '  tar: %s\n' "${TARS[@]}"

# Container-side (/mnt) paths
TPL_IN="/mnt/Templates/UpdatedTemplates/${TPL_ID}_template.nii.gz"
TMASK_HOST="$DB_DIR/Templates/UpdatedTemplates/${TPL_ID}_brain_mask.nii.gz"

run() {  # run a command inside the container with the DB bound to /mnt
  apptainer exec --bind "$TMP:/writabletemp" --bind "$DB_DIR:/mnt" "$CONTAINER" \
    /bin/bash -c "if [ -f /usr/local/fsl/etc/fslconf/fsl.sh ]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi; \
                  export TMPDIR=/writabletemp; export PATH=\"\$PATH:/opt/ANTs/install/bin\"; \
                  export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$NT OMP_NUM_THREADS=$NT; $1"
}

# 0) FAST WM mask of the TEMPLATE (once) -> defines the gray-white boundary.
TPL_WM_HOST="$OUTROOT/template_wm.nii.gz"
if [[ ! -f "$TPL_WM_HOST" ]]; then
  echo "[pilot] segmenting template WM (FAST)"
  TPL_FAST_OUT="/mnt/Validity/heatmap_pilot/$TPL_ID/template_fast"
  run "fast -t 1 -n 3 -g -o $TPL_FAST_OUT $TPL_IN; \
       fslmaths ${TPL_FAST_OUT}_pve_2.nii.gz -thr 0.5 -bin /mnt/Validity/heatmap_pilot/$TPL_ID/template_wm.nii.gz"
fi

# 1) Per-subject: extract intensity moving image, then register + warp + FAST WM.
SYN_WM=(); AFF_WM=()
for tarf in "${TARS[@]}"; do
  eid="$(basename "$tarf" .tar.gz)"
  sub_out="$OUTROOT/subjects/$eid"
  # Fresh dir: a stale registration from the failed mask-based run must not be
  # reused (different moving image -> must re-register on the intensity T1).
  rm -rf "$sub_out"; mkdir -p "$sub_out"

  # Extract the intensity csfNorm_rc moving image from the tarball.
  member="$eid/subj_${eid}_csfNorm_rc.nii.gz"
  tar xzf "$tarf" -C "$TMP" "$member" 2>/dev/null || { echo "[ERROR] no $member in $tarf" >&2; continue; }
  cp -f "$TMP/$member" "$sub_out/moving_csfNorm_rc.nii.gz"

  mov_in="/mnt/Validity/heatmap_pilot/$TPL_ID/subjects/$eid/moving_csfNorm_rc.nii.gz"
  out_in="/mnt/Validity/heatmap_pilot/$TPL_ID/subjects/$eid"
  echo "[pilot] subject $eid (intensity moving image)"
  run "/bin/bash /mnt/validity_heatmap_scripts/validity_heatmap_subject.sh $mov_in $TPL_IN $out_in $NT"
  SYN_WM+=("$sub_out/subj_syn_wm.nii.gz")
  AFF_WM+=("$sub_out/subj_affine_wm.nii.gz")
done

# 2) Aggregate: signed surface-distance heat map per level.
echo "[pilot] aggregating SyN level"
run "python3 /mnt/validity_heatmap_scripts/validity_heatmap_aggregate.py syn \
     /mnt/Validity/heatmap_pilot/$TPL_ID/template_wm.nii.gz \
     /mnt/Validity/heatmap_pilot/$TPL_ID/${TPL_ID}_syn \
     $(printf '/mnt%s ' "${SYN_WM[@]/#$DB_DIR/}")"
echo "[pilot] aggregating affine level"
run "python3 /mnt/validity_heatmap_scripts/validity_heatmap_aggregate.py affine \
     /mnt/Validity/heatmap_pilot/$TPL_ID/template_wm.nii.gz \
     /mnt/Validity/heatmap_pilot/$TPL_ID/${TPL_ID}_affine \
     $(printf '/mnt%s ' "${AFF_WM[@]/#$DB_DIR/}")"

rm -rf "$TMP" 2>/dev/null || true
echo "[pilot] DONE -> $OUTROOT"
