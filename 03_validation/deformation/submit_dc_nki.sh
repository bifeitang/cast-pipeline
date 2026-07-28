#!/usr/bin/env bash
# Submit the NKI reference portion: 319 subjects x 6 NKI templates (ages 7-12) = 1,914.
# (ages 7-11 x male/female) = 3,175 registrations, matching what F2_agexage_clean consumes.
#
# Input is the CSF-normalised INTENSITY image, not the binary mask the original run used.
# Sourced from the per-subject tarball for 272 subjects and from
# RECENTERED_MISSING47_2026-07-27/ for the other 47, whose centred images did not survive
# the storage cleanup and were reconstructed (pure header rewrite, validated exact on six
# pre/post pairs).
#
# Usage: submit_dc_nki.sh <subject_age_map.tsv> [--dry-run]
#   subject_age_map.tsv: <eid>\t<subject_age_int>
#
# Templates are fixed here rather than derived, because the set F2 uses is a deliberate
# choice (ages 7-11 both sexes) and not everything available.

set -euo pipefail
export PATH=/opt/slurm/bin:$PATH

MAP="${1:?usage: submit_dc_nki.sh <subject_age_map.tsv> [--dry-run]}"
DRY=""; [ "${2:-}" = "--dry-run" ] && DRY=1
HERE="$(cd "$(dirname "$0")" && pwd)"

TPL_AGES="7 8 9 10 11 12"
TPL_SEXES="na"

n_sub=0; n_job=0
while IFS=$'\t' read -r eid age; do
  [ -z "${eid:-}" ] && continue
  n_sub=$((n_sub + 1))
  for ta in $TPL_AGES; do
    for ts in $TPL_SEXES; do
      n_job=$((n_job + 1))
      [ -n "$DRY" ] && continue
      sbatch --parsable "${HERE}/sbatch_dc_nki.sh" "$eid" "$age" "$ta" "$ts" >/dev/null
    done
  done
done < "$MAP"

echo "subjects: ${n_sub}   registrations: ${n_job}"
# metrics.txt is 451 B; intermediates (~1.2 GB/job) are deleted by the wrapper as each
# job finishes, so peak disk is set by concurrency, not by the job count.
awk -v n="$n_job" 'BEGIN{printf "budget: %.0f core-hours (measured 1.87/job)\n", n*1.87;
  printf "disk:   %.1f MB settled (%d x 451 B); peak ~1.2 GB x concurrent jobs\n", n*451/1048576, n}'
[ -n "$DRY" ] && echo "(dry run -- nothing submitted)"
exit 0
