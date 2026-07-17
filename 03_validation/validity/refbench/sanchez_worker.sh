#!/bin/bash
# sanchez_worker.sh  (runs INSIDE the apptainer container)
# WORKSTREAM B: add the Sanchez/Richards Neurodevelopmental MRI Database as a
# THIRD reference atlas to the held-out gray-white interface benchmark, exactly
# parallel to the NKI block of refbench_worker.sh, but emitting the SYMMETRIC
# ASSD metric directly (forward + reverse + symmetric ASSD + signed bias) so the
# Sanchez rows drop straight into assd_1p0_measures.jsonl alongside CAST/NKI/Fonov.
#
# Reuses, verbatim, the existing pipeline pieces:
#   - per-subject FS->moving rigid bridge fs2mov_0GenericAffine.mat (CAST sweep)
#   - warp_surface_to_template.py  (subject lh/rh.white -> reference space)
#   - measure_cell_assd.py         (symmetric ASSD vs reference WM mask)
#
# Reference registration is moving -> Sanchez SyN (antsRegistrationSyN.sh -t s),
# IDENTICAL settings to the NKI/Fonov blocks, so CAST-vs-NKI-vs-Fonov-vs-Sanchez
# differ ONLY in the target template, isolating template fit.
#
# Sanchez WM mask = binarize the database's OWN WM segmentation
#   Templates/Sanchez/Segments/AVG<A>-0Years3T_brain_image_seg_wm.nii.gz  (thr >0.5)
# (no FAST: this uses the database's own WM definition, the fair choice; the seg
#  shares the ANTS<A>-0...brain grid/affine -- verified -- so no resampling.)
#
# Args: <EID> <SUBJ_AGE> <TPL_AGE> <SEX> <SANCHEZ_TAG> <NT>
#   SANCHEZ_TAG e.g. Sanchez_age7  (-> ANTS7-0Years3T_brain.nii.gz + AVG7-0..._seg_wm)
set -uo pipefail
EID="${1:?EID}"; SUBJ_AGE="${2:?SUBJ_AGE}"; TPL_AGE="${3:?TPL_AGE}"; SEX="${4:?SEX}"
SANCHEZ_TAG="${5:?SANCHEZ_TAG}"; NT="${6:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"

SANCHEZDIR=/mnt/Templates/Sanchez
SANCHEZSEG=/mnt/Templates/Sanchez/Segments
REFWM=/mnt/Validity/refbench/templates_wm
SCR=/mnt/validity_heatmap_scripts
FS=/mnt/TemplateTestSet/HBN_formatted_all/$EID
SRC=/mnt/Validity/sweep/$EID          # has fs2mov_0GenericAffine.mat (CAST sweep)
OUT=/mnt/Validity/refbench/$EID
mkdir -p "$OUT" "$REFWM"
export TMPDIR=$OUT
cd "$OUT" || { echo "[ERR] no $OUT"; exit 1; }

# SANCHEZ_TAG = Sanchez_age<N>  ->  ANTS<N>-0Years3T... / AVG<N>-0Years3T...
AGE_INT=${SANCHEZ_TAG#Sanchez_age}
SANCHEZ_TPL=$SANCHEZDIR/ANTS${AGE_INT}-0Years3T_brain.nii.gz
SANCHEZ_SEG=$SANCHEZSEG/AVG${AGE_INT}-0Years3T_brain_image_seg_wm.nii.gz
SANCHEZ_WM=$REFWM/${SANCHEZ_TAG}_wm.nii.gz

if [[ ! -f "$SANCHEZ_TPL" ]]; then echo "[ERR] missing Sanchez template $SANCHEZ_TPL"; exit 1; fi

# fs2mov bridge MUST already exist (built by the CAST sweep). Do NOT rebuild.
FS2MOV=$SRC/fs2mov_0GenericAffine.mat
if [[ ! -f "$FS2MOV" ]]; then echo "[ERR] missing fs2mov bridge for $EID -> CAST sweep not done"; exit 1; fi

# moving image (re-extracted host-side before calling us, same as run_refbench.sbatch).
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving.nii.gz for $EID (host must extract)"; exit 1; }

# ---------------------------------------------------------------------------
# 0) Sanchez WM mask (built ONCE per reference, idempotent / guarded).
#    The database ships its OWN WM segmentation (a 0-1 probability map sharing
#    the template grid). Binarize at 0.5 -- NO FAST.
# ---------------------------------------------------------------------------
if [[ ! -f "$SANCHEZ_WM" ]]; then
  if [[ ! -f "$SANCHEZ_SEG" ]]; then echo "[ERR] missing Sanchez WM seg $SANCHEZ_SEG"; exit 1; fi
  echo "[sanchez] binarize WM seg for $SANCHEZ_TAG"
  fslmaths "$SANCHEZ_SEG" -thr 0.5 -bin "$SANCHEZ_WM" \
    || echo "[WARN] Sanchez WM build failed $SANCHEZ_TAG"
fi

# ---------------------------------------------------------------------------
# 1) Sanchez: moving -> Sanchez reference, SyN  (identical to NKI block)
# ---------------------------------------------------------------------------
if [[ ! -f sanchez_1InverseWarp.nii.gz && ! -f surf_sanchez_syn.npz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$SANCHEZ_TPL" -m moving.nii.gz -o sanchez_ -t s -n "$NT" >/dev/null 2>&1 \
    || echo "[WARN] sanchez-syn reg $EID"
fi
if [[ -f sanchez_1InverseWarp.nii.gz && ! -f surf_sanchez_syn.npz ]]; then
  python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
      "$FS2MOV" sanchez_0GenericAffine.mat surf_sanchez_syn.npz sanchez_1InverseWarp.nii.gz \
    || echo "[WARN] warp sanchez_syn $EID"
fi

# ---------------------------------------------------------------------------
# 2) measure: symmetric ASSD vs Sanchez WM (reference:"Sanchez", tagged ASSD JSON)
# ---------------------------------------------------------------------------
if [[ -f surf_sanchez_syn.npz && -f "$SANCHEZ_WM" ]]; then
  python3 "$SCR/assd/measure_cell_assd.py" "$SANCHEZ_WM" surf_sanchez_syn.npz \
      "$SUBJ_AGE" "$TPL_AGE" na "$EID" 6.0 Sanchez 2>/dev/null \
    | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"ref_tpl":"'"$SANCHEZ_TAG"'","kind":"ref_syn"})) for l in sys.stdin if l.strip()]' \
    > meas_sanchez_assd.json || echo "[WARN] measure sanchez $EID"
fi

# ---------------------------------------------------------------------------
# 3) cleanup heavy intermediates; keep npz + measures + affine mat
# ---------------------------------------------------------------------------
rm -f sanchez_1Warp.nii.gz sanchez_1InverseWarp.nii.gz sanchez_Warped.nii.gz sanchez_InverseWarped.nii.gz \
      moving.nii.gz 2>/dev/null || true
echo "[done] $EID subj_age$SUBJ_AGE tpl_age$TPL_AGE $SEX  sanchez=$SANCHEZ_TAG"
