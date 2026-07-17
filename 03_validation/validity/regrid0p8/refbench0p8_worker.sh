#!/bin/bash
# refbench0p8_worker.sh  (runs INSIDE the apptainer container)
# RESOLUTION-ARTIFACT CONTROL re-benchmark for ONE held-out subject whose matched
# CAST template was regridded to 0.8 mm. Mirrors EXACTLY the CAST matched-SyN arm
# of sweep_worker.sh (and refbench_worker.sh's reference arm), changing ONLY the
# fixed template to the 0.8 mm CAST template (and, for the grid-neutral control,
# the 0.8 mm NKI template). The subject's moving image (csfNorm_rc) and the
# FS->moving rigid bridge are reused verbatim from the original CAST sweep, so
# the ONLY thing that differs from the published CAST(1.0) number is the template
# grid spacing -> isolates the resolution artifact.
#
# Re-registration (not mask-only re-measure) is REQUIRED: the original matched-SyN
# warp fields were deleted by sweep_worker.sh after the surface was warped, and the
# surface must be transported through a SyN field defined in the NEW (0.8 mm)
# template's space. We therefore re-run moving->(0.8mm template) SyN with identical
# antsRegistrationSyN.sh settings (-t s), then warp + measure.
#
# Args: <EID> <AGE> <SEX> <NKI_TPL_BASENAME> <NT>
set -uo pipefail
EID="${1:?EID}"; AGE="${2:?AGE}"; SEX="${3:?SEX}"; NKI_TPL_BN="${4:?NKI template basename}"; NT="${5:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"

TPLDIR=/mnt/Templates/UpdatedTemplates_0p8        # 0.8mm CAST templates + WM
NKI0P8=/mnt/Validity/refbench_0p8/templates_nki0p8 # 0.8mm NKI templates + WM
SCR=/mnt/validity_heatmap_scripts
FS=/mnt/TemplateTestSet/HBN_formatted_all/$EID
SRC=/mnt/Validity/sweep/$EID                       # fs2mov_0GenericAffine.mat (CAST sweep)
OUT=/mnt/Validity/refbench_0p8/$EID
mkdir -p "$OUT"
export TMPDIR=$OUT
cd "$OUT" || { echo "[ERR] no $OUT"; exit 1; }

# 0.8mm CAST matched template + WM mask for this stratum
CAST_TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
CAST_WM=$TPLDIR/age${AGE}_${SEX}_wm.nii.gz
[[ -f "$CAST_TPL" && -f "$CAST_WM" ]] || { echo "[ERR] missing 0.8mm CAST tpl/wm for age${AGE}_${SEX}"; exit 1; }

# 0.8mm NKI matched template + WM mask (grid-neutral control)
NKI_TAG=${NKI_TPL_BN%_brain_template.nii.gz}       # e.g. NKI_age8
NKI_TPL=$NKI0P8/${NKI_TAG}_brain_template.nii.gz
NKI_WM=$NKI0P8/${NKI_TAG}_wm.nii.gz

# FS->moving bridge MUST already exist (CAST sweep). Do NOT rebuild.
FS2MOV=$SRC/fs2mov_0GenericAffine.mat
[[ -f "$FS2MOV" ]] || { echo "[ERR] missing fs2mov bridge for $EID"; exit 1; }
# moving image extracted host-side (csfNorm_rc, same source as CAST sweep)
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving.nii.gz for $EID (host must extract)"; exit 1; }

# ---------------------------------------------------------------------------
# 1) CAST-0.8: moving -> 0.8mm CAST template, SyN  (mirror sweep_worker.sh m_ arm)
# ---------------------------------------------------------------------------
if [[ ! -f cast0p8_1InverseWarp.nii.gz && ! -f surf_cast0p8.npz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$CAST_TPL" -m moving.nii.gz -o cast0p8_ -t s -n "$NT" >/dev/null 2>&1 \
    || echo "[WARN] cast0p8-syn reg $EID"
fi
if [[ -f cast0p8_1InverseWarp.nii.gz && ! -f surf_cast0p8.npz ]]; then
  python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
      "$FS2MOV" cast0p8_0GenericAffine.mat surf_cast0p8.npz cast0p8_1InverseWarp.nii.gz \
    || echo "[WARN] warp cast0p8 $EID"
fi
if [[ -f surf_cast0p8.npz && -f "$CAST_WM" ]]; then
  python3 "$SCR/measure_cell.py" "$CAST_WM" surf_cast0p8.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 2>/dev/null \
    | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"reference":"CAST_0.8","ref_tpl":"age'"$AGE"'_'"$SEX"'","grid_mm":0.8,"kind":"matched_syn"})) for l in sys.stdin if l.strip()]' \
    > meas_cast0p8.json || echo "[WARN] measure cast0p8 $EID"
fi

# ---------------------------------------------------------------------------
# 2) NKI-0.8 (grid-neutral control): moving -> 0.8mm NKI template, SyN
#    (mirror refbench_worker.sh NKI arm, only the grid changed)
# ---------------------------------------------------------------------------
if [[ -f "$NKI_TPL" && -f "$NKI_WM" ]]; then
  if [[ ! -f nki0p8_1InverseWarp.nii.gz && ! -f surf_nki0p8.npz ]]; then
    antsRegistrationSyN.sh -d 3 -f "$NKI_TPL" -m moving.nii.gz -o nki0p8_ -t s -n "$NT" >/dev/null 2>&1 \
      || echo "[WARN] nki0p8-syn reg $EID"
  fi
  if [[ -f nki0p8_1InverseWarp.nii.gz && ! -f surf_nki0p8.npz ]]; then
    python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
        "$FS2MOV" nki0p8_0GenericAffine.mat surf_nki0p8.npz nki0p8_1InverseWarp.nii.gz \
      || echo "[WARN] warp nki0p8 $EID"
  fi
  if [[ -f surf_nki0p8.npz ]]; then
    python3 "$SCR/measure_cell.py" "$NKI_WM" surf_nki0p8.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 2>/dev/null \
      | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"reference":"NKI_0.8","ref_tpl":"'"$NKI_TAG"'","grid_mm":0.8,"kind":"ref_syn"})) for l in sys.stdin if l.strip()]' \
      > meas_nki0p8.json || echo "[WARN] measure nki0p8 $EID"
  fi
else
  echo "[note] no 0.8mm NKI template for $NKI_TAG -> skipping NKI-0.8 control arm for $EID"
fi

# ---------------------------------------------------------------------------
# 3) cleanup heavy intermediates; keep npz + measures + affine mats
# ---------------------------------------------------------------------------
rm -f cast0p8_1Warp.nii.gz cast0p8_1InverseWarp.nii.gz cast0p8_Warped.nii.gz cast0p8_InverseWarped.nii.gz \
      nki0p8_1Warp.nii.gz nki0p8_1InverseWarp.nii.gz nki0p8_Warped.nii.gz nki0p8_InverseWarped.nii.gz \
      moving.nii.gz 2>/dev/null || true
echo "[done] $EID age$AGE $SEX  cast0p8=age${AGE}_${SEX} nki0p8=$NKI_TAG"
