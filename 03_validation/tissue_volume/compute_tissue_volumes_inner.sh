#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   compute_tissue_volumes_inner.sh <subject_id> <age> <sex> <output_csv>
#
# Requirements:
#   SUBJECTS_DIR set
#   FreeSurfer environment sourced (mri_segstats available)

SUBJECT_ID="${1:?Need subject_id}"
AGE="${2:?Need age}"
SEX="${3:?Need sex}"
OUT_CSV="${4:?Need output_csv}"

if [ -z "${SUBJECTS_DIR:-}" ]; then
  echo "ERROR: SUBJECTS_DIR is not set" >&2
  exit 1
fi

aseg="${SUBJECTS_DIR}/${SUBJECT_ID}/mri/aseg.mgz"
asegstats="${SUBJECTS_DIR}/${SUBJECT_ID}/stats/aseg.stats"

if [ ! -f "$aseg" ]; then
  echo "ERROR: Missing aseg.mgz for $SUBJECT_ID at $aseg" >&2
  exit 1
fi

# ---------- Label sets (FreeSurfer aseg IDs) ----------
# WM: cerebral WM (2,41) + cerebellar WM (7,46) + corpus callosum (251-255)
WM_LABELS=(2 41 7 46 251 252 253 254 255)

# GM: cerebral cortex (3,42) + cerebellar cortex (8,47) + brainstem (16)
#     + subcortical: thalamus (10,49), caudate (11,50), putamen (12,51),
#       pallidum (13,52), hippocampus (17,53), amygdala (18,54),
#       accumbens (26,58), ventralDC (28,60)
GM_LABELS=(3 42 8 47 16 10 49 11 50 12 51 13 52 17 53 18 54 26 58 28 60)

# CSF: lateral ventricles (4,43), inf-lat ventricles (5,44),
#      3rd ventricle (14), 4th ventricle (15), CSF label (24)
CSF_LABELS=(4 43 5 44 14 15 24)

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

sumfile="${tmpdir}/aseg.sum"
mri_segstats --seg "$aseg" --sum "$sumfile" >/dev/null 2>&1

# mri_segstats output format (data rows):
#   Col 1: Index
#   Col 2: SegId
#   Col 3: NVoxels
#   Col 4: Volume_mm3
#   Col 5: StructName
# Data rows do NOT start with #

sum_vol_mm3_by_ids() {
  local -a ids=("$@")
  awk -v idlist="${ids[*]}" '
    BEGIN {
      n = split(idlist, a, " ");
      for (i = 1; i <= n; i++) keep[a[i]] = 1;
      total = 0;
    }
    /^#/ { next }           # skip comment lines
    /^[[:space:]]*$/ { next }  # skip empty lines
    {
      segid = $2;           # SegId is column 2
      vol = $4;             # Volume_mm3 is column 4
      if (segid in keep) {
        total += vol;
      }
    }
    END { printf "%.1f", total }
  ' "$sumfile"
}

wm_mm3="$(sum_vol_mm3_by_ids "${WM_LABELS[@]}")"
gm_mm3="$(sum_vol_mm3_by_ids "${GM_LABELS[@]}")"
csf_mm3="$(sum_vol_mm3_by_ids "${CSF_LABELS[@]}")"

# eTIV from aseg.stats if present
etiv_mm3=""
if [ -f "$asegstats" ]; then
  etiv_mm3="$(grep -i 'EstimatedTotalIntraCranialVol' "$asegstats" \
    | awk -F',' '{gsub(/ /,"",$2); print $2}' 2>/dev/null || true)"
fi

# Convert mm3 to mL (divide by 1000)
wm_ml="$(awk -v v="$wm_mm3" 'BEGIN{printf "%.3f", v/1000.0}')"
gm_ml="$(awk -v v="$gm_mm3" 'BEGIN{printf "%.3f", v/1000.0}')"
csf_ml="$(awk -v v="$csf_mm3" 'BEGIN{printf "%.3f", v/1000.0}')"

icv_mm3="$(awk -v w="$wm_mm3" -v g="$gm_mm3" -v c="$csf_mm3" 'BEGIN{printf "%.1f", w+g+c}')"
icv_ml="$(awk -v v="$icv_mm3" 'BEGIN{printf "%.3f", v/1000.0}')"

etiv_ml=""
if [ -n "${etiv_mm3:-}" ]; then
  etiv_ml="$(awk -v v="$etiv_mm3" 'BEGIN{printf "%.3f", v/1000.0}')"
fi

mkdir -p "$(dirname "$OUT_CSV")"
echo "subject_id,age,sex,wm_mm3,gm_mm3,csf_mm3,icv_mm3,wm_ml,gm_ml,csf_ml,icv_ml,etiv_mm3,etiv_ml" > "$OUT_CSV"
echo "${SUBJECT_ID},${AGE},${SEX},${wm_mm3},${gm_mm3},${csf_mm3},${icv_mm3},${wm_ml},${gm_ml},${csf_ml},${icv_ml},${etiv_mm3:-},${etiv_ml:-}" >> "$OUT_CSV"

echo "Done: $SUBJECT_ID  WM=${wm_ml}mL GM=${gm_ml}mL CSF=${csf_ml}mL ICV(sum)=${icv_ml}mL eTIV=${etiv_ml:-NA}mL"
