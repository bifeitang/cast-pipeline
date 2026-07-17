#!/usr/bin/env bash
set -euo pipefail

# Submit DC computation for all subjects age 5–12 against selected template ages
# Usage: submit_all_subjects_dc.sh [--dry-run]

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="$(cd "$ROOT_DIR/.." && pwd)"
HBN_DIR="$DB_DIR/TemplateTestSet/hbn_grouped_by_age"

sbatch_script="$ROOT_DIR/sbatch_subject_dc.sh"
[[ -f "$sbatch_script" ]] || { echo "[ERROR] Missing $sbatch_script" >&2; exit 1; }

count=0
TEMPLATE_AGES="7 8 10 11"
SEXES="male female"
for tpl_age in $TEMPLATE_AGES; do
for sex in $SEXES; do
for age in 5 6 7 8 9 10 11 12; do
  proc_dir="$HBN_DIR/$age/processed_centered"
  [[ -d "$proc_dir" ]] || continue
  while IFS= read -r -d '' img; do
    eid="$(basename "$img" | sed 's/_processed_centered\.nii\.gz//')"
    cmd=( sbatch "$sbatch_script" "$img" "$eid" "$age" "$tpl_age" "$sex" )
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY sbatch ${cmd[*]}"
    else
      "${cmd[@]}"
    fi
    count=$((count+1))
  done < <(find "$proc_dir" -maxdepth 1 -type f -name "*_processed_centered.nii.gz" -print0 | sort -z)
done
done
done

echo "Submitted $count jobs."



