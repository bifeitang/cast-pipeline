#!/bin/bash
# refbench_renorm_worker.sh  (runs INSIDE the apptainer container)
# WM-CONTRAST RESTORATION test for ONE held-out age7_male subject. Identical to the
# CAST-0.8 arm of refbench0p8_worker.sh in EVERY respect EXCEPT the fixed image:
# the SyN target is the WM-contrast-restored 0.8 mm age7_male template
# (renorm_wm_contrast.py, Weber 0.277 -> 0.393 toward NKI), while
#   - moving image (csfNorm_rc) is reused verbatim (host extracts it),
#   - the FS->moving rigid bridge is reused verbatim from the CAST sweep,
#   - the MEASUREMENT WM mask is the PUBLISHED age7_male_wm.nii.gz (copied verbatim
#     into the renorm tree) -- NOT regenerated -- so the ONLY thing that differs
#     from the published CAST_0.8 number is the fixed image's deep-WM contrast.
# This isolates "how much of the CAST-vs-NKI interface gap is recoverable by
# restoring CAST's deep-WM contrast."
#
# Args: <EID> <AGE> <SEX> <NT>
set -uo pipefail
EID="${1:?EID}"; AGE="${2:?AGE}"; SEX="${3:?SEX}"; NT="${4:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"

RENORM=/mnt/Validity/refbench_renorm_age7m            # renorm template + published WM mask
SCR=/mnt/validity_heatmap_scripts
FS=/mnt/TemplateTestSet/HBN_formatted_all/$EID
SRC=/mnt/Validity/sweep/$EID                          # fs2mov bridge (CAST sweep)
OUT=/mnt/Validity/refbench_renorm_age7m/$EID
mkdir -p "$OUT"
export TMPDIR=$OUT
cd "$OUT" || { echo "[ERR] no $OUT"; exit 1; }

RN_TPL=$RENORM/templates/age${AGE}_${SEX}_template.nii.gz
RN_WM=$RENORM/templates/age${AGE}_${SEX}_wm.nii.gz    # PUBLISHED mask, verbatim
[[ -f "$RN_TPL" && -f "$RN_WM" ]] || { echo "[ERR] missing renorm tpl/wm for age${AGE}_${SEX}"; exit 1; }

FS2MOV=$SRC/fs2mov_0GenericAffine.mat
[[ -f "$FS2MOV" ]] || { echo "[ERR] missing fs2mov bridge for $EID"; exit 1; }
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving.nii.gz for $EID (host must extract)"; exit 1; }

# 1) moving -> renorm CAST template, SyN (identical settings to the CAST-0.8 arm)
if [[ ! -f castRN_1InverseWarp.nii.gz && ! -f surf_castRN.npz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$RN_TPL" -m moving.nii.gz -o castRN_ -t s -n "$NT" >/dev/null 2>&1 \
    || echo "[WARN] castRN-syn reg $EID"
fi
if [[ -f castRN_1InverseWarp.nii.gz && ! -f surf_castRN.npz ]]; then
  python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
      "$FS2MOV" castRN_0GenericAffine.mat surf_castRN.npz castRN_1InverseWarp.nii.gz \
    || echo "[WARN] warp castRN $EID"
fi
if [[ -f surf_castRN.npz && -f "$RN_WM" ]]; then
  python3 "$SCR/measure_cell.py" "$RN_WM" surf_castRN.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 2>/dev/null \
    | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"reference":"CAST_renorm","ref_tpl":"age'"$AGE"'_'"$SEX"'_renorm","grid_mm":0.8,"kind":"matched_syn_wmcontrast"})) for l in sys.stdin if l.strip()]' \
    > meas_castRN.json || echo "[WARN] measure castRN $EID"
fi

# 2) cleanup heavy intermediates; keep npz + measure + affine
rm -f castRN_1Warp.nii.gz castRN_1InverseWarp.nii.gz castRN_Warped.nii.gz castRN_InverseWarped.nii.gz \
      moving.nii.gz 2>/dev/null || true
echo "[done] $EID age$AGE $SEX  castRN=age${AGE}_${SEX}_renorm"
