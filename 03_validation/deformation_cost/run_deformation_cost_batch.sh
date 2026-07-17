#!/usr/bin/env bash
set -euo pipefail

# Batch: register HBN ages 5–12 to age-9 male and female templates and compute deformation cost (DC)
# Inputs:
# - Subject images: PediatricMriDB/TemplateTestSet/hbn_grouped_by_age/<age>/processed_centered/*_processed_centered.nii.gz
# - Templates: PediatricMriDB/Templates/age9_male_template.nii.gz and age9_female_template.nii.gz (accept .gz without .nii)
# - Subject info CSV: PediatricMriDB/TemplateTestSet/hbn_subject_info_all.txt
# - DC script: PediatricMriDB/cal_deformation_cost.sh
# Output:
# - CSV at PediatricMriDB/TemplateTestSet/deformation_cost_age5_12_to_age9.csv

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_DIR="$ROOT_DIR/PediatricMriDB"
HBN_DIR="$DB_DIR/TemplateTestSet/hbn_grouped_by_age"
INFO_CSV="$DB_DIR/TemplateTestSet/hbn_subject_info_all.txt"
DC_SCRIPT="$DB_DIR/cal_deformation_cost.sh"
OUT_CSV="$DB_DIR/TemplateTestSet/deformation_cost_age5_12_to_age9.csv"
WORK_DIR="$DB_DIR/TemplateTestSet/deformation_cost_work"
mkdir -p "$WORK_DIR"

# Resolve template paths and generate masks if available; else use whole-brain
TPL_DIR="$DB_DIR/Templates"
TPL_MALE=""
TPL_FEMALE=""

if [[ -f "$TPL_DIR/age9_male_template.nii.gz" ]]; then
  TPL_MALE="$TPL_DIR/age9_male_template.nii.gz"
elif [[ -f "$TPL_DIR/age9_male_template.gz" ]]; then
  TPL_MALE="$TPL_DIR/age9_male_template.gz"
else
  echo "[ERROR] Missing age9 male template in $TPL_DIR" >&2
  exit 1
fi

if [[ -f "$TPL_DIR/age9_female_template.nii.gz" ]]; then
  TPL_FEMALE="$TPL_DIR/age9_female_template.nii.gz"
elif [[ -f "$TPL_DIR/age9_female_template.gz" ]]; then
  TPL_FEMALE="$TPL_DIR/age9_female_template.gz"
else
  echo "[ERROR] Missing age9 female template in $TPL_DIR" >&2
  exit 1
fi

# Try to find masks alongside templates or allow user-specified
TPL_MALE_MASK=""
TPL_FEMALE_MASK=""
for candidate in \
  "${TPL_MALE%.nii.gz}_brain_mask.nii.gz" \
  "${TPL_MALE%.gz}_brain_mask.nii.gz" \
  "$TPL_DIR/age9_male_brain_mask.nii.gz"; do
  [[ -f "$candidate" ]] && TPL_MALE_MASK="$candidate" && break || true
done
for candidate in \
  "${TPL_FEMALE%.nii.gz}_brain_mask.nii.gz" \
  "${TPL_FEMALE%.gz}_brain_mask.nii.gz" \
  "$TPL_DIR/age9_female_brain_mask.nii.gz"; do
  [[ -f "$candidate" ]] && TPL_FEMALE_MASK="$candidate" && break || true
done

if ! command -v antsRegistration >/dev/null 2>&1; then
  echo "[ERROR] antsRegistration not found in PATH" >&2
  exit 1
fi
for t in antsApplyTransforms ImageMath; do
  command -v "$t" >/dev/null 2>&1 || { echo "[ERROR] Missing $t" >&2; exit 1; }
done

[[ -x "$DC_SCRIPT" ]] || chmod +x "$DC_SCRIPT"

# Build an awk associative map from INFO_CSV: EID -> Sex_Text, Age
declare -A ID_TO_SEX
declare -A ID_TO_AGE
while IFS=',' read -r EID Sex_Code Sex_Text Age Age_Int; do
  [[ "$EID" == "EID" ]] && continue
  ID_TO_SEX["$EID"]="$Sex_Text"
  ID_TO_AGE["$EID"]="$Age_Int"
done < "$INFO_CSV"

echo "subject_id,subject_age,subject_sex,template,dc_mm2,rms_mm" > "$OUT_CSV"

# Registration function (SyN) producing warp to template space
register_to_template() {
  local subj_img="$1"    # subject image path
  local template_img="$2" # template image path
  local out_prefix="$3"  # output prefix
  antsRegistration \
    --dimensionality 3 \
    --float 0 \
    --output ["${out_prefix}","${out_prefix}Warped.nii.gz","${out_prefix}InverseWarped.nii.gz"] \
    --interpolation Linear \
    --winsorize-image-intensities [0.005,0.995] \
    --use-histogram-matching 1 \
    --initial-moving-transform ["${template_img}","${subj_img}",1] \
    --transform Rigid[0.1] \
    --metric MI["${template_img}","${subj_img}",1,32,Regular,0.25] \
    --convergence [1000x500x250x0,1e-6,10] \
    --shrink-factors 8x4x2x1 \
    --smoothing-sigmas 3x2x1x0vox \
    --transform Affine[0.1] \
    --metric MI["${template_img}","${subj_img}",1,32,Regular,0.25] \
    --convergence [1000x500x250x0,1e-6,10] \
    --shrink-factors 8x4x2x1 \
    --smoothing-sigmas 3x2x1x0vox \
    --transform SyN[0.1,3,0] \
    --metric CC["${template_img}","${subj_img}",1,4] \
    --convergence [100x70x50x20,1e-6,10] \
    --shrink-factors 8x4x2x1 \
    --smoothing-sigmas 3x2x1x0vox
}

# Iterate ages 5..12
for age in 5 6 7 8 9 10 11 12; do
  proc_dir="$HBN_DIR/$age/processed_centered"
  [[ -d "$proc_dir" ]] || continue
  for img in "$proc_dir"/*_processed_centered.nii.gz; do
    [[ -f "$img" ]] || continue
    eid="$(basename "$img" | sed 's/_processed_centered\.nii\.gz//')"
    subj_sex="${ID_TO_SEX[$eid]:-unknown}"
    subj_age="${ID_TO_AGE[$eid]:-$age}"

    for tpl in male female; do
      if [[ "$tpl" == "male" ]]; then
        tpl_img="$TPL_MALE"
        tpl_mask="$TPL_MALE_MASK"
      else
        tpl_img="$TPL_FEMALE"
        tpl_mask="$TPL_FEMALE_MASK"
      fi
      out_pref="$WORK_DIR/${eid}_to_age9_${tpl}_"

      # Run registration only if warp not present
      if [[ ! -f "${out_pref}1Warp.nii.gz" ]]; then
        register_to_template "$img" "$tpl_img" "$out_pref"
      fi

      # Determine mask to use for DC: template mask if present else whole-template threshold mask
      mask_to_use="$tpl_mask"
      if [[ -z "${mask_to_use}" ]]; then
        mask_to_use="$WORK_DIR/age9_${tpl}_autogen_mask.nii.gz"
        if [[ ! -f "$mask_to_use" ]]; then
          # crude mask: Otsu on template
          ImageMath 3 "$mask_to_use" ThresholdAtMean "$tpl_img" 1
        fi
      fi

      # Compute DC
      dc_prefix="$WORK_DIR/${eid}_to_age9_${tpl}"
      "$DC_SCRIPT" "${out_pref}1Warp.nii.gz" "$mask_to_use" "$dc_prefix" > "${dc_prefix}_dc.txt"
      dc_val="$(awk -F'=' '/DC_mm2/ {print $2}' "${dc_prefix}_dc.txt" | tr -d '\r\n' )"
      rms_val="$(awk -F'=' '/RMS_mm/ {print $2}' "${dc_prefix}_dc.txt" | tr -d '\r\n' )"

      echo "$eid,$subj_age,$subj_sex,age9_${tpl},$dc_val,$rms_val" >> "$OUT_CSV"
    done
  done
done

echo "Wrote $(wc -l < "$OUT_CSV") rows to $OUT_CSV"


