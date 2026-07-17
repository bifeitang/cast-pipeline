#!/usr/bin/env bash

# Compute brain masks for one or more template NIfTI files.
# Usage: compute_template_masks.sh TEMPLATE1.nii.gz [TEMPLATE2.nii.gz ...]

need() { command -v "$1" >/dev/null 2>&1; }

for t in ImageMath; do
  need "$t" || { echo "[ERROR] Missing $t in PATH" >&2; exit 1; }
done

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 TEMPLATE1.nii.gz [TEMPLATE2.nii.gz ...]" >&2
  exit 2
fi

mk_mask() {
  local tpl="$1"; local out="$2"; local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  # 1) Threshold above mean to get a rough brain region
  ImageMath 3 "$tmpdir/m0.nii.gz" ThresholdAtMean "$tpl" 1
  # 2) Morphological clean-up: small erosion then dilation to smooth edges
  ImageMath 3 "$tmpdir/m1.nii.gz" ME "$tmpdir/m0.nii.gz" 1
  ImageMath 3 "$tmpdir/m2.nii.gz" MD "$tmpdir/m1.nii.gz" 2
  # 3) Keep largest component and fill holes
  ImageMath 3 "$tmpdir/m3.nii.gz" GetLargestComponent "$tmpdir/m2.nii.gz"
  ImageMath 3 "$tmpdir/m4.nii.gz" FillHoles "$tmpdir/m3.nii.gz" 2
  mv "$tmpdir/m4.nii.gz" "$out"
}

for tpl in "$@"; do
  if [[ ! -f "$tpl" ]]; then
    echo "[ERROR] Not found: $tpl" >&2
    continue
  fi
  dir="$(dirname "$tpl")"
  file="$(basename "$tpl")"
  base="${file%.nii.gz}"
  if [[ "$base" == *_template ]]; then
    out="$dir/${base%_template}_brain_mask.nii.gz"
  else
    out="$dir/${base}_brain_mask.nii.gz"
  fi

  if [[ -f "$out" ]]; then
    echo "[INFO] Mask exists, skipping: $out"
    continue
  fi

  echo "[INFO] Creating mask for $tpl → $out"
  mk_mask "$tpl" "$out"
  echo "[OK]   Wrote $out"
done

echo "[DONE] Finished computing masks"


