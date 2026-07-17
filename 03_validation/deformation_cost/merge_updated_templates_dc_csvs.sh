#!/usr/bin/env bash
set -euo pipefail

# Merge all metrics.txt under PediatricMriDB/DeformationCost/UpdatedTemplates into a single CSV.
# Output columns are:
#   template_id,age_dir,subject_id,<metrics fields...>
#
# Also backfills an explicit unnormalized deformation cost column:
#   - warp_value_mm (if missing in metrics.txt) := mean_disp_mm (or normalized_warp_value * L_mm)
#
# Usage:
#   merge_updated_templates_dc_csvs.sh [out_csv]

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="$(cd "$ROOT_DIR/.." && pwd)"
IN_DIR="$DB_DIR/DeformationCost/UpdatedTemplates"
DEFAULT_OUT="$DB_DIR/DeformationCost/test_set_on_updated_templates_metrics.csv"
OUT_CSV="${1:-$DEFAULT_OUT}"

python3 - <<PY
import re
from pathlib import Path

in_dir = Path("${IN_DIR}")
out_csv = Path("${OUT_CSV}")

metrics_files = sorted(in_dir.glob("**/metrics.txt"))
if not metrics_files:
    raise SystemExit(f"No metrics.txt files found under {in_dir}")

def split_fields(line: str):
    # metrics.txt is TSV-ish but sometimes has variable whitespace; normalize to tabs first
    line = line.strip()
    return re.split(r"\\s+", line)

first_header = split_fields(metrics_files[0].read_text().splitlines()[0])
header_fields = first_header[:]  # copy

need_warp_value_mm = "warp_value_mm" not in header_fields
if need_warp_value_mm:
    header_fields.append("warp_value_mm")

out_lines = []
out_lines.append(",".join(["template_id", "age_dir", "subject_id"] + header_fields))

seen = set()
for f in metrics_files:
    # path: UpdatedTemplates/<template_id>/<age>/<subject>/metrics.txt
    try:
        template_id = f.parents[2].name
        age_dir = f.parents[1].name
        subject_id = f.parents[0].name
    except Exception:
        continue

    txt_lines = f.read_text().splitlines()
    if len(txt_lines) < 2:
        continue

    data_line = next((ln for ln in txt_lines[1:] if ln.strip()), "")
    if not data_line:
        continue

    data_fields = split_fields(data_line)
    row = dict(zip(first_header, data_fields))

    # backfill warp_value_mm if needed
    if need_warp_value_mm:
        if "mean_disp_mm" in row and row["mean_disp_mm"] != "":
            row["warp_value_mm"] = row["mean_disp_mm"]
        elif "normalized_warp_value" in row and "L_mm" in row:
            try:
                row["warp_value_mm"] = f"{float(row['normalized_warp_value']) * float(row['L_mm']):.6f}"
            except Exception:
                row["warp_value_mm"] = ""
        else:
            row["warp_value_mm"] = ""

    # composite key to dedupe: template_id,age_dir,subject_id,moving,template,mode,norm_type
    key = (
        template_id,
        age_dir,
        subject_id,
        row.get("moving", ""),
        row.get("template", ""),
        row.get("mode", ""),
        row.get("norm_type", ""),
    )
    if key in seen:
        continue
    seen.add(key)

    ordered = [row.get(col, "") for col in header_fields]
    out_lines.append(",".join([template_id, age_dir, subject_id] + ordered))

out_csv.write_text("\\n".join(out_lines) + "\\n")
print(f"Wrote {len(out_lines)} lines to {out_csv}")
PY
