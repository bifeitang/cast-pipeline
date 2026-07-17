#!/usr/bin/env bash
set -euo pipefail

# Submit DC computation for all test set subjects (ages 5-22) against selected templates.
# Default templates: ages 6,7,8,9,11,12,13,14 (male and female) - 16 templates
# Outputs are written under:
#   PediatricMriDB/DeformationCost/test_set_dc/<template_id>/<age>/<eid>/
#
# Usage:
#   submit_test_set_dc.sh [--dry-run] \
#     [--templates "age6_female age6_male age7_female age7_male ..."] \
#     [--ages "5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22"]

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

# Default templates: ages 6,7,8,9,11,12,13,14 male and female (16 templates)
if (( ${#TEMPLATES[@]} == 0 )); then
  TEMPLATES=(
    age6_female age6_male
    age7_female age7_male
    age8_female age8_male
    age9_female age9_male
    age11_female age11_male
    age12_female age12_male
    age13_female age13_male
    age14_female age14_male
  )
fi

# Default ages: all available test set ages (5-22)
if (( ${#AGES[@]} == 0 )); then
  AGES=(5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22)
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="$(cd "$ROOT_DIR/.." && pwd)"
HBN_DIR="$DB_DIR/TemplateTestSet/hbn_grouped_by_age"

sbatch_script="$ROOT_DIR/sbatch_test_set_dc.sh"
[[ -f "$sbatch_script" ]] || { echo "[ERROR] Missing $sbatch_script" >&2; exit 1; }

echo "Templates: ${TEMPLATES[*]}"
echo "Test ages: ${AGES[*]}"
echo "Test set directory: $HBN_DIR"
echo ""

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

echo ""
echo "Submitted $count jobs."
