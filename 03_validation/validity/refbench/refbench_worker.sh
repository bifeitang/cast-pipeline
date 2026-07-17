#!/bin/bash
# refbench_worker.sh  (runs INSIDE the apptainer container)
# HEAD-TO-HEAD VALIDITY BENCHMARK: register ONE held-out test subject to the
# matched EXTERNAL reference atlas (NKI and Fonov/NIHPD) and measure the
# gray-white interface error there, using the SAME surface metric as the CAST
# sweep so the numbers are directly comparable to $DB/Validity/sweep/<EID>/
# meas_matched_syn.json (CAST, matched age+sex, SyN).
#
# Reuses, verbatim, the existing pipeline pieces:
#   - the per-subject FS->moving rigid bridge fs2mov_0GenericAffine.mat
#     (already on disk in $DB/Validity/sweep/<EID>/ from the CAST sweep)
#   - warp_surface_to_template.py  (subject white surface -> reference space)
#   - measure_cell.py              (gray-white distance vs reference WM mask)
#
# Reference registration is moving -> reference SyN (matched to how CAST does
# its matched-template SyN arm), so CAST-vs-NKI-vs-Fonov differ ONLY in the
# target template, isolating template fit.
#
# Args: <EID> <AGE> <SEX> <NKI_TPL_BASENAME> <FONOV_BAND_PREFIX> <NT>
#   NKI_TPL_BASENAME  e.g. NKI_age8_brain_template.nii.gz   (under /mnt/Templates)
#   FONOV_BAND_PREFIX e.g. nihpd_sym_07.0-11.0              (under /mnt/Templates/Fonov)
set -uo pipefail
EID="${1:?EID}"; AGE="${2:?AGE}"; SEX="${3:?SEX}"
NKI_TPL_BN="${4:?NKI template basename}"; FONOV_PFX="${5:?Fonov band prefix}"; NT="${6:-8}"

if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"

TPLDIR=/mnt/Templates
NKIDIR=/mnt/Templates                 # NKI_age*_brain_template.nii.gz live here
FONOVDIR=/mnt/Templates/Fonov         # nihpd_sym_<band>_t1w.nii / _wm.nii / _mask.nii
REFWM=/mnt/Validity/refbench/templates_wm
SCR=/mnt/validity_heatmap_scripts
FS=/mnt/TemplateTestSet/HBN_formatted_all/$EID
SRC=/mnt/Validity/sweep/$EID          # has fs2mov_0GenericAffine.mat (CAST sweep)
OUT=/mnt/Validity/refbench/$EID
mkdir -p "$OUT" "$REFWM"
export TMPDIR=$OUT
cd "$OUT" || { echo "[ERR] no $OUT"; exit 1; }

NKI_TPL=$NKIDIR/$NKI_TPL_BN
NKI_TAG=${NKI_TPL_BN%_brain_template.nii.gz}    # e.g. NKI_age8
NKI_WM=$REFWM/${NKI_TAG}_wm.nii.gz
FONOV_T1=$FONOVDIR/${FONOV_PFX}_t1w.nii
FONOV_WM_PROB=$FONOVDIR/${FONOV_PFX}_wm.nii
FONOV_TAG=$(echo "$FONOV_PFX" | tr '.' 'p' | tr '-' '_')   # nihpd_sym_07p0_11p0
FONOV_WM=$REFWM/${FONOV_TAG}_wm.nii.gz

# fs2mov bridge MUST already exist (built by the CAST sweep). Do NOT rebuild.
FS2MOV=$SRC/fs2mov_0GenericAffine.mat
if [[ ! -f "$FS2MOV" ]]; then echo "[ERR] missing fs2mov bridge for $EID -> CAST sweep not done"; exit 1; fi

# Need the moving image. CAST sweep deletes moving.nii.gz; re-extract from tarball
# was done host-side before calling us (same as run_validity_sweep.sbatch).
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving.nii.gz for $EID (host must extract)"; exit 1; }

# ---------------------------------------------------------------------------
# 0) Reference WM masks (built ONCE per reference, idempotent / guarded).
#    NKI templates are already skull-stripped intensity volumes -> FAST 3-class,
#    pve_2 = WM. Fonov ships a WM probability map -> threshold at 0.5.
# ---------------------------------------------------------------------------
if [[ ! -f "$NKI_WM" ]]; then
  echo "[refbench] FAST WM for $NKI_TAG"
  fast -t 1 -n 3 -g -o "$REFWM/${NKI_TAG}_fast" "$NKI_TPL" \
    && fslmaths "$REFWM/${NKI_TAG}_fast_pve_2.nii.gz" -thr 0.5 -bin "$NKI_WM" \
    && rm -f "$REFWM/${NKI_TAG}_fast_pve_"*.nii.gz "$REFWM/${NKI_TAG}_fast_seg.nii.gz" "$REFWM/${NKI_TAG}_fast_mixeltype.nii.gz" \
    || echo "[WARN] NKI WM build failed $NKI_TAG"
fi
if [[ ! -f "$FONOV_WM" ]]; then
  echo "[refbench] threshold WM prob for $FONOV_TAG"
  # NIHPD tissue prob maps are 0-1 floats (verified: fslstats -R = 0..1), so
  # threshold at 0.5 to take voxels that are majority WM.
  fslmaths "$FONOV_WM_PROB" -thr 0.5 -bin "$FONOV_WM" \
    || echo "[WARN] Fonov WM build failed $FONOV_TAG"
fi

# ---------------------------------------------------------------------------
# 1) NKI: moving -> NKI reference, SyN
# ---------------------------------------------------------------------------
if [[ ! -f nki_1InverseWarp.nii.gz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$NKI_TPL" -m moving.nii.gz -o nki_ -t s -n "$NT" >/dev/null 2>&1 \
    || echo "[WARN] nki-syn reg $EID"
fi
if [[ -f nki_1InverseWarp.nii.gz && ! -f surf_nki_syn.npz ]]; then
  python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
      "$FS2MOV" nki_0GenericAffine.mat surf_nki_syn.npz nki_1InverseWarp.nii.gz \
    || echo "[WARN] warp nki_syn $EID"
fi
if [[ -f surf_nki_syn.npz && -f "$NKI_WM" ]]; then
  python3 "$SCR/measure_cell.py" "$NKI_WM" surf_nki_syn.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 2>/dev/null \
    | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"reference":"NKI","ref_tpl":"'"$NKI_TAG"'","kind":"ref_syn"})) for l in sys.stdin if l.strip()]' \
    > meas_nki_syn.json || echo "[WARN] measure nki $EID"
fi

# ---------------------------------------------------------------------------
# 2) Fonov/NIHPD: moving -> Fonov t1w reference, SyN
# ---------------------------------------------------------------------------
if [[ ! -f fonov_1InverseWarp.nii.gz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$FONOV_T1" -m moving.nii.gz -o fonov_ -t s -n "$NT" >/dev/null 2>&1 \
    || echo "[WARN] fonov-syn reg $EID"
fi
if [[ -f fonov_1InverseWarp.nii.gz && ! -f surf_fonov_syn.npz ]]; then
  python3 "$SCR/warp_surface_to_template.py" "$FS/mri/orig.mgz" "$FS/surf/lh.white" "$FS/surf/rh.white" \
      "$FS2MOV" fonov_0GenericAffine.mat surf_fonov_syn.npz fonov_1InverseWarp.nii.gz \
    || echo "[WARN] warp fonov_syn $EID"
fi
if [[ -f surf_fonov_syn.npz && -f "$FONOV_WM" ]]; then
  python3 "$SCR/measure_cell.py" "$FONOV_WM" surf_fonov_syn.npz "$AGE" "$AGE" "$SEX" "$EID" 6.0 2>/dev/null \
    | python3 -c 'import sys,json;
[print(json.dumps({**json.loads(l),"reference":"Fonov","ref_tpl":"'"$FONOV_TAG"'","kind":"ref_syn"})) for l in sys.stdin if l.strip()]' \
    > meas_fonov_syn.json || echo "[WARN] measure fonov $EID"
fi

# ---------------------------------------------------------------------------
# 3) cleanup heavy intermediates; keep npz + measures + affine mats
# ---------------------------------------------------------------------------
rm -f nki_1Warp.nii.gz nki_1InverseWarp.nii.gz nki_Warped.nii.gz nki_InverseWarped.nii.gz \
      fonov_1Warp.nii.gz fonov_1InverseWarp.nii.gz fonov_Warped.nii.gz fonov_InverseWarped.nii.gz \
      moving.nii.gz 2>/dev/null || true
echo "[done] $EID age$AGE $SEX  nki=$NKI_TAG fonov=$FONOV_TAG"
