#!/usr/bin/env bash

# Create age-9 male/female template brain masks once and save under Templates/
# The mask is used to compute deformation cost consistently across subjects.

ROOT_DIR="/mnt"
TPL_DIR="$ROOT_DIR/Templates"

need() { command -v "$1" >/dev/null 2>&1; }

for t in ImageMath; do
  need "$t" || { echo "[ERROR] Missing $t in PATH" >&2; exit 1; }
done

TPL_MALE="$TPL_DIR/age9_male_template.nii.gz"
TPL_FEMALE="$TPL_DIR/age9_female_template.nii.gz"

[[ -f "$TPL_MALE" ]] || { echo "[ERROR] Not found: $TPL_MALE" >&2; exit 1; }
[[ -f "$TPL_FEMALE" ]] || { echo "[ERROR] Not found: $TPL_FEMALE" >&2; exit 1; }

OUT_MASK_MALE="$TPL_DIR/age9_male_brain_mask.nii.gz"
OUT_MASK_FEMALE="$TPL_DIR/age9_female_brain_mask.nii.gz"

mk_mask() {
  local tpl="$1"; local out="$2"; local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  # 1) Threshold above mean to get a rough brain region
  ImageMath 3 "$tmpdir/m0.nii.gz" ThresholdAtMean "$tpl" 1
  # 2) Morphological clean-up: small erosion then dilation to smooth edges
  ImageMath 3 "$tmpdir/m1.nii.gz" ME "$tmpdir/m0.nii.gz" 1
  ImageMath 3 "$tmpdir/m2.nii.gz" MD "$tmpdir/m1.nii.gz" 2
  # 3) Keep largest component and fill holes
  ImageMath 3 "$tmpdir/m3.nii.gz" GetLargestComponent "$tmpdir/m2.nii.gz"
  ImageMath 3 "$tmpdir/m4.nii.gz" FillHoles "$tmpdir/m3.nii.gz" 2
  mv "$tmpdir/m4.nii.gz" "$out"
  rm -rf "$tmpdir"
}

if [[ ! -f "$OUT_MASK_MALE" ]]; then
  echo "[INFO] Creating male template mask → $OUT_MASK_MALE"
  mk_mask "$TPL_MALE" "$OUT_MASK_MALE"
else
  echo "[INFO] Male mask exists: $OUT_MASK_MALE"
fi

if [[ ! -f "$OUT_MASK_FEMALE" ]]; then
  echo "[INFO] Creating female template mask → $OUT_MASK_FEMALE"
  mk_mask "$TPL_FEMALE" "$OUT_MASK_FEMALE"
else
  echo "[INFO] Female mask exists: $OUT_MASK_FEMALE"
fi

echo "[DONE] Masks ready in $TPL_DIR"


