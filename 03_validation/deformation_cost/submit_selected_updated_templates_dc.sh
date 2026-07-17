#!/usr/bin/env bash
set -euo pipefail

# Submit DC computation for all subjects age 5–18 against selected UPDATED templates.
# Outputs are written under:
#   PediatricMriDB/DeformationCost/new_template_and_deformation_cal/
# Usage:
#   submit_selected_updated_templates_dc.sh [--dry-run] \
#     [--templates "age5_female age5_male age10_female age10_male age15_female age15_male"] \
#     [--ages "5 6 7 8 9 10 11 12 13 14 15 16 17 18"]

DRY_RUN=0
TEMPLATES=()
AGES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    --templates) IFS=' ' read -r -a TEMPLATES <<< "${2:-}"; shift 2;;
    --ages) IFS=' ' read -r -a AGES <<< "${2:-}"; shift 2;;
    -h|--help)
      grep -m1 -A200 "^# Submit DC computation" "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

if (( ${#TEMPLATES[@]} == 0 )); then
  TEMPLATES=(age5_female age5_male age10_female age10_male age15_female age15_male)
fi
if (( ${#AGES[@]} == 0 )); then
  AGES=(5 6 7 8 9 10 11 12 13 14 15 16 17 18)
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="$(cd "$ROOT_DIR/.." && pwd)"
HBN_DIR="$DB_DIR/TemplateTestSet/hbn_grouped_by_age"

sbatch_script="$ROOT_DIR/sbatch_subject_dc_updated_templates.sh"
[[ -f "$sbatch_script" ]] || { echo "[ERROR] Missing $sbatch_script" >&2; exit 1; }

count=0
for tpl in "${TEMPLATES[@]}"; do
  if [[ "$tpl" =~ ^age([0-9]+)_(male|female)$ ]]; then
    tpl_age="${BASH_REMATCH[1]}"
    tpl_sex="${BASH_REMATCH[2]}"
  else
    echo "[ERROR] Invalid template id '$tpl' (expected age<INT>_male|female)" >&2
    exit 2
  fi

  for age in "${AGES[@]}"; do
    proc_dir="$HBN_DIR/$age/processed_centered"
    [[ -d "$proc_dir" ]] || continue
    while IFS= read -r -d '' img; do
      eid="$(basename "$img" | sed 's/_processed_centered\.nii\.gz//')"
      cmd=( sbatch "$sbatch_script" "$img" "$eid" "$age" "$tpl_age" "$tpl_sex" )
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "DRY sbatch ${cmd[*]}"
      else
        "${cmd[@]}"
      fi
      count=$((count+1))
    done < <(find "$proc_dir" -maxdepth 1 -type f -name "*_processed_centered.nii.gz" -print0 | sort -z)
  done
done

echo "Submitted $count jobs."
