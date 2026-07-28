#!/usr/bin/env bash
# Submit the SyN-only ("clean") displacement validation against the age-9-female template.
#
# Reads a TSV of candidates produced by joining the surviving 2025-11 expected values with
# the centred images still on disk. Columns:
#   1 eid   2 age_dir(expected)   3 expected_mean_disp_mm   4 expected_mean_logJ
#   5 subject_age(from image path)   6 absolute image path
#
# Written as a file rather than an inline ssh one-liner on purpose: the first attempt used
# IFS=$"\t", which is locale translation and NOT a tab, so every field collapsed into $eid
# and 48 jobs were queued with garbage arguments. They were cancelled while still PENDING.
# Quoting through ssh is not worth the risk for something that submits jobs.
#
# Usage: submit_cleandisp_validate.sh <candidates.tsv> [per_age_cap]

set -euo pipefail
export PATH=/opt/slurm/bin:$PATH

SRC="${1:?usage: submit_cleandisp_validate.sh <candidates.tsv> [per_age_cap]}"
CAP="${2:-6}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="/project/contreras-vidal/Yang/PediatricMriDB"

SAMPLE="$(mktemp)"
awk -F'\t' -v cap="$CAP" '{c[$5]++; if (c[$5] <= cap) print}' "$SRC" > "$SAMPLE"

n_total=$(wc -l < "$SAMPLE")
echo "sample: ${n_total} jobs (<= ${CAP} per subject-age)"
echo "per age: $(cut -f5 "$SAMPLE" | sort -n | uniq -c | tr '\n' ' ')"
awk -v n="$n_total" 'BEGIN{printf "budget: %.0f core-hours, %.0f GB peak disk before per-job cleanup\n", n*3.96, n*1177/1024}'
echo

submitted=0
while IFS=$'\t' read -r eid age_dir edisp elogj age path; do
  [ -z "${eid:-}" ] && continue
  if [ ! -s "$path" ]; then
    echo "  SKIP ${eid}: image missing or empty: ${path}" >&2
    continue
  fi
  jid=$(sbatch --parsable "${HERE}/sbatch_cleandisp_validate.sh" "$path" "$eid" "$age" 9 female)
  submitted=$((submitted + 1))
  if [ "$submitted" -le 3 ]; then
    echo "  ${eid}  subject-age ${age}  expected ${edisp} mm  -> job ${jid}"
  fi
done < "$SAMPLE"

echo "SUBMITTED: ${submitted} of ${n_total}"
rm -f "$SAMPLE"
