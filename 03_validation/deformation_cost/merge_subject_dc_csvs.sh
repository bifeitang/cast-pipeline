#!/usr/bin/env bash
set -euo pipefail

# Merge all metrics.txt under PediatricMriDB/DeformationCost into a single CSV

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# DB_DIR is the parent directory of this scripts directory (i.e., PediatricMriDB)
DB_DIR="$(cd "$ROOT_DIR/.." && pwd)"
IN_DIR="$DB_DIR/DeformationCost"
# Allow optional output filename as first argument; default to NKI template CSV name
DEFAULT_OUT="$IN_DIR/test_set_on_all_template_metrics.csv"
OUT_CSV="${1:-$DEFAULT_OUT}"
TARGET_CSV="$OUT_CSV"

# Collect all metrics.txt files under DeformationCost
mapfile -d '' METRICS_FILES < <(find "$IN_DIR" -type f -name "metrics.txt" -print0 | sort -z)

if (( ${#METRICS_FILES[@]} == 0 )); then
  echo "No metrics.txt files found under $IN_DIR" >&2
  exit 0
fi

mkdir -p "$IN_DIR"

# Build header from the first metrics file, and prepend age_dir and subject_id for context
FIRST_FILE="${METRICS_FILES[0]}"
HEADER_LINE="$(head -n 1 "$FIRST_FILE")"
# Normalize any runs of whitespace to commas
HEADER_CSV="$(echo "$HEADER_LINE" | sed -E 's/[[:space:]]+/,/g' | sed -E 's/,$//')"

# If output CSV exists and header matches expected, keep it; else write to a new file
EXPECTED_HEADER="age_dir,subject_id,$HEADER_CSV"
if [[ -f "$OUT_CSV" ]]; then
  CURRENT_HEADER="$(head -n 1 "$OUT_CSV" || true)"
  if [[ "$CURRENT_HEADER" != "$EXPECTED_HEADER" ]]; then
    TS="$(date +%Y%m%d-%H%M%S)"
    TARGET_CSV="$IN_DIR/merged_metrics_header_mismatch_${TS}.csv"
    echo "Header mismatch detected. Writing to $TARGET_CSV instead of $OUT_CSV" >&2
    echo "$EXPECTED_HEADER" > "$TARGET_CSV"
  else
    TARGET_CSV="$OUT_CSV"
  fi
else
  echo "$EXPECTED_HEADER" > "$OUT_CSV"
  TARGET_CSV="$OUT_CSV"
fi

# Append each file's first data row (after header)
for f in "${METRICS_FILES[@]}"; do
  subject_id="$(basename "$(dirname "$f")")"
  age_dir="$(basename "$(dirname "$(dirname "$f")")")"
  # Grab first non-empty line after header
  data_line="$(tail -n +2 "$f" | sed '/^[[:space:]]*$/d' | head -n 1 || true)"
  if [[ -z "${data_line:-}" ]]; then
    continue
  fi
  data_csv="$(echo "$data_line" | sed -E 's/[[:space:]]+/,/g' | sed -E 's/,$//')"
  # Composite key: age_dir,subject_id,moving,template,mode,norm_type (first 6 columns)
  key_suffix="$(echo "$data_csv" | awk -F',' '{print $1","$2","$3","$4}')"
  row_key="$age_dir,$subject_id,$key_suffix"
  # Append only if composite key not already present (skip header line)
  if ! tail -n +2 "$TARGET_CSV" | cut -d, -f1-6 | grep -Fxq "$row_key"; then
    echo "$age_dir,$subject_id,$data_csv" >> "$TARGET_CSV"
  fi
done

echo "Wrote $(wc -l < "$TARGET_CSV") lines to $TARGET_CSV"
