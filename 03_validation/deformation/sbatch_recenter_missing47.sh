#!/usr/bin/env bash
#SBATCH --job-name=rc-missing47
#SBATCH --output=rc-missing47-%j.out
#SBATCH --error=rc-missing47-%j.err
#SBATCH --time=02:00:00
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --mem=8G

set -uo pipefail

# Regenerate subj_<EID>_csfNorm_rc.nii.gz for the 47 held-out subjects whose centred
# derivatives were removed by the storage cleanup.
#
# CONTEXT: the deformation-cost analysis was run on *_processed_centered.nii.gz, which
# turned out to be BINARY BRAIN MASKS registered against intensity templates. That was an
# input-selection error (author-confirmed 2026-07-27). The rerun uses the CSF-normalised
# INTENSITY images instead -- subj_<EID>_csfNorm_rc.nii.gz -- which is also what the
# tissue-Jacobian pipeline used all along.
#
# 272 of the 319 subjects still have csfNorm_rc inside their per-subject tarball. The other
# 47 have no tarball, but all 47 retain subj_<EID>_brainmask_csfNorm.nii.gz under
# HBN_formatted_all/<EID>/anat/, which is the pre-recentring stage. Only the recentre step
# is missing, so this regenerates exactly that -- no re-preprocessing, no FreeSurfer.
#
# Operation copied from recenter_one.sh: ImageMath 3 <out> RecenterImage 2 <in> <xfm>.
# One job loops over all 47 because each takes seconds; 47 separate jobs would cost more in
# scheduler overhead than in compute.
#
# Usage: sbatch sbatch_recenter_missing47.sh <eid_list.txt>

LIST="${1:?usage: sbatch sbatch_recenter_missing47.sh <eid_list.txt>}"

ROOT_DIR="/project/contreras-vidal/Yang"
DB_DIR="$ROOT_DIR/PediatricMriDB"
FORMATTED="$DB_DIR/TemplateTestSet/HBN_formatted_all"
OUT_ROOT="$ROOT_DIR/RECENTERED_MISSING47_2026-07-27"
CONTAINER_IMAGE="/project/contreras-vidal/Image/mri_template_env_reg.sif"
mkdir -p "$OUT_ROOT"

ok=0; fail=0
while read -r eid; do
  [ -z "${eid:-}" ] && continue
  src="$FORMATTED/$eid/anat/subj_${eid}_brainmask_csfNorm.nii.gz"
  if [ ! -s "$src" ]; then
    echo "[SKIP] $eid: no brainmask_csfNorm" >&2; fail=$((fail+1)); continue
  fi
  out="$OUT_ROOT/subj_${eid}_csfNorm_rc.nii.gz"
  xfm="$OUT_ROOT/recenter_subj_${eid}_csfNorm_rc.mat"
  if [ -s "$out" ]; then echo "[skip] $eid already done"; ok=$((ok+1)); continue; fi

  apptainer exec --bind "$DB_DIR:/mnt" --bind "$OUT_ROOT:/out" "$CONTAINER_IMAGE" \
    /bin/bash -c "export PATH=\$PATH:/opt/ANTs/install/bin; \
                  ImageMath 3 /out/subj_${eid}_csfNorm_rc.nii.gz RecenterImage 2 \
                    /mnt/TemplateTestSet/HBN_formatted_all/$eid/anat/subj_${eid}_brainmask_csfNorm.nii.gz \
                    /out/recenter_subj_${eid}_csfNorm_rc.mat" >/dev/null 2>&1

  if [ -s "$out" ]; then echo "[ok] $eid"; ok=$((ok+1)); else echo "[FAIL] $eid" >&2; fail=$((fail+1)); fi
done < "$LIST"

echo "recentred ok=$ok fail=$fail -> $OUT_ROOT"
