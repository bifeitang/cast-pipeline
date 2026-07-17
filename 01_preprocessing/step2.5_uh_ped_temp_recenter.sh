#!/bin/bash
#
# step2.5_uh_ped_temp_recenter.sh — Recenter + apply xfm
#
# USAGE:
#   step2.5_uh_ped_temp_recenter.sh  <CCS_DIR>  <SUBJECTS_DIR>  <subject>  [--mode resample|header]
#
# INPUTS (typical layout):
#   <CCS_DIR>/<subject>/anat/subj_<subject>_brainmask_csfNorm.nii.gz
#   <CCS_DIR>/<subject>/anat/subj_<subject>_T1_crop_sanlm_n4_brain_mask.nii.gz
#   <CCS_DIR>/<subject>/anat/segment/segment_*.nii.gz   (optional)
#
# OUTPUTS:
#   subj_<subject>_csfNorm_rc.nii.gz
#   subj_<subject>_T1_crop_sanlm_n4_brain_mask_rc.nii.gz
#   segment_*_rc.nii.gz
#   recenter_<stem>.mat   (ITK translation)
#
# Notes:
#  * Default mode "resample" mirrors older pipelines that applied a transform to masks.
#  * Mode "header" is faster/lossless (no interpolation): shifts headers for all.
#  * Requires: ImageMath, antsApplyTransforms (ANTs), python3, nibabel, scipy.
# ------------------------------------------------------------------------------

# ---------- args ----------
if [ $# -lt 3 ]; then
  echo "Usage: $0 CCS_DIR SUBJECTS_DIR subject [--mode resample|header]" >&2
  exit 1
fi

CCS_DIR=$1
SUBJECTS_DIR=$2
subject=$3
MODE="resample"
if [ "${4-}" = "--mode" ]; then
  MODE="${5:-resample}"
fi
if [ "${4-}" = "--mode=header" ] || [ "${4-}" = "--mode=resample" ]; then
  MODE="${4#--mode=}"
fi
if [ "${MODE}" != "resample" ] && [ "${MODE}" != "header" ]; then
  echo "Error: --mode must be 'resample' or 'header' (got '${MODE}')" >&2
  exit 1
fi

# ---------- locate anat_dir (support both styles: CCS_DIR/<subj>/anat OR CCS_DIR already == anat) ----------
if [ -d "${CCS_DIR}/${subject}/anat" ]; then
  anat_dir="${CCS_DIR}/${subject}/anat"
else
  anat_dir="${CCS_DIR}"
fi

# ---------- inputs ----------
img_in="${anat_dir}/subj_${subject}_brainmask_csfNorm.nii.gz"
brain_mask="${anat_dir}/subj_${subject}_T1_crop_sanlm_n4_brain_mask.nii.gz"

if [ ! -f "${img_in}" ]; then
  echo "Error: input image not found: ${img_in}" >&2
  exit 2
fi
# Support alternate mask naming (without subj_ prefix) and allow fallback to no-mask
if [ ! -f "${brain_mask}" ]; then
  alt_mask="${anat_dir}/T1_crop_sanlm_n4_brain_mask.nii.gz"
  if [ -f "${alt_mask}" ]; then
    brain_mask="${alt_mask}"
  else
    echo "Warning: brain mask not found with expected names; proceeding without mask" >&2
    brain_mask=""
  fi
fi

# ---------- required commands ----------
for cmd in ImageMath antsApplyTransforms python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command not found on PATH: $cmd" >&2
    exit 4
  fi
done

# ---------- embedded Python: COM->(0,0,0) header shift + ITK .mat ----------
# Writes: recentered image, and (optionally) recenter_<stem>.mat
nib_recenter_py="$(mktemp -t nib_recenter_XXXX.py)"
cat > "${nib_recenter_py}" <<'PYEND'
#!/usr/bin/env python3
import sys, argparse, pathlib, numpy as np
import nibabel as nib
from scipy.ndimage import center_of_mass

p = argparse.ArgumentParser()
p.add_argument("in_nii")
p.add_argument("out_nii")
p.add_argument("--write-mat", action="store_true")
p.add_argument("--mask", help="optional mask: COM over mask>0; else intensity COM")
#
# Apply an existing translation (Insight/ITK transform file) to the header only.
# This is used to keep masks/segmentations aligned with the already-recentered image
# without recomputing a new COM per file (which would misalign them).
p.add_argument("--apply-xfm", help="Insight/ITK transform file (.txt/.mat) containing pure translation")
args = p.parse_args()

img  = nib.load(args.in_nii)
aff  = img.affine.copy()

def read_translation_from_itk_xfm(xfm_path: str) -> np.ndarray:
    """
    Parse an Insight/ITK transform file written like:
      Transform: AffineTransform_double_3_3
      Parameters: 1 0 0 0 1 0 0 0 1 tx ty tz
      FixedParameters: 0 0 0
    Returns translation vector [tx, ty, tz] in mm.
    """
    with open(xfm_path, "r") as f:
        for line in f:
            if line.startswith("Parameters:"):
                parts = line.strip().split()
                vals = [float(x) for x in parts[1:]]
                if len(vals) < 12:
                    raise RuntimeError(f"Unexpected Parameters length in {xfm_path}")
                return np.array(vals[-3:], dtype=np.float64)
    raise RuntimeError(f"Could not find 'Parameters:' line in {xfm_path}")

if args.apply_xfm:
    # Apply the same delta translation to this file's header (no COM recompute).
    T = read_translation_from_itk_xfm(args.apply_xfm)
    aff_new = aff.copy()
    aff_new[:3, 3] += T
else:
    # data for COM (masked if provided)
    if args.mask:
        m = nib.load(args.mask).get_fdata(dtype=np.float32)
        data = img.get_fdata(dtype=np.float32)
        if data.shape != m.shape:
            raise RuntimeError("Mask shape mismatch.")
        # COM of intensities within mask (labels param)
        lbl = (m > 0).astype(np.uint8)
        # scipy center_of_mass(data, labels, index) gives weighted COM in voxel coords
        com_vox = np.array(center_of_mass(data, labels=lbl, index=1))
    else:
        data = img.get_fdata(dtype=np.float32)
        com_vox = np.array(center_of_mass(data))

    # voxel->world
    com_world = nib.affines.apply_affine(aff, com_vox)

    # shift translation so COM maps to (0,0,0)
    aff_new = aff.copy()
    aff_new[:3, 3] -= com_world

# write image with clean qform/sform codes
hdr = img.header.copy()
out = img.__class__(img.get_fdata(dtype=img.get_data_dtype()), aff_new, hdr)
# 1=SCANNER_ANAT; use 1 for both q/s
out.set_qform(aff_new, code=1)
out.set_sform(aff_new, code=1)
nib.save(out, args.out_nii)
print(f"[nib_recenter] wrote {args.out_nii}")

if args.write_mat:
    if args.apply_xfm:
        raise RuntimeError("--write-mat cannot be used together with --apply-xfm")
    T = aff_new[:3, 3] - aff[:3, 3]  # pure translation in mm
    op = pathlib.Path(args.out_nii)
    stem = op.name.replace(".nii.gz","").replace(".nii","")
    # Write both .txt (Insight) and .mat (legacy ANTs style) for compatibility
    txt_path = op.with_name(f"recenter_{stem}.txt")
    mat_path = op.with_name(f"recenter_{stem}.mat")
    for out_path in (txt_path, mat_path):
        with open(out_path, "w") as f:
            f.write("#Insight Transform File V1.0\n")
            f.write("# Transform 0\n")
            f.write("Transform: AffineTransform_double_3_3\n")
            f.write("Parameters: 1 0 0 0 1 0 0 0 1 "
                    f"{T[0]} {T[1]} {T[2]}\n")
            f.write("FixedParameters: 0 0 0\n")
        print(f"[nib_recenter] wrote {out_path}")
PYEND
chmod +x "${nib_recenter_py}"

echo "==> Step 6: recentering (${MODE} mode) …"

# ---------- outputs ----------
img_rc="${anat_dir}/subj_${subject}_csfNorm_rc.nii.gz"

# 6a. Recenter main intensity image (header-only) and emit an ITK .mat
# Add mask argument only if available
mask_args=()
if [ -n "${brain_mask}" ] && [ -f "${brain_mask}" ]; then
  mask_args=(--mask "${brain_mask}")
fi
python3 "${nib_recenter_py}" "${img_in}" "${img_rc}" --write-mat "${mask_args[@]}"

# infer transform name the helper produced (prefer .txt Insight format, fallback to .mat)
xfm="${anat_dir}/recenter_subj_${subject}_csfNorm_rc.txt"
if [ ! -f "${xfm}" ]; then
  xfm_mat="${anat_dir}/recenter_subj_${subject}_csfNorm_rc.mat"
  if [ -f "${xfm_mat}" ]; then
    xfm="${xfm_mat}"
  else
    # POSIX-safe glob search: try .txt first, then .mat
    found_xfm=""
    for f in "${anat_dir}"/recenter_*csfNorm_rc.txt; do
      [ -f "$f" ] || continue
      found_xfm="$f"
      break
    done
    if [ -z "$found_xfm" ]; then
      for f in "${anat_dir}"/recenter_*csfNorm_rc.mat; do
        [ -f "$f" ] || continue
        found_xfm="$f"
        break
      done
    fi
    if [ -n "$found_xfm" ]; then
      xfm="$found_xfm"
    else
      echo "Error: could not locate recenter transform next to ${img_rc}" >&2
      exit 5
    fi
  fi
fi

# 6b. Process masks
if [ "${MODE}" = "header" ]; then
  # Fast/lossless: apply the same header shift to masks (no resampling)
  if [ -n "${brain_mask}" ] && [ -f "${brain_mask}" ]; then
    python3 "${nib_recenter_py}" "${brain_mask}" \
      "${anat_dir}/subj_${subject}_T1_crop_sanlm_n4_brain_mask_rc.nii.gz" \
      --apply-xfm "${xfm}"
  fi
  for m in "${anat_dir}"/segment/segment_*.nii.gz; do
    [ -e "$m" ] || continue
    python3 "${nib_recenter_py}" "${m}" "${m%.*}_rc.nii.gz" --apply-xfm "${xfm}"
  done
else
  # RESAMPLE masks so they align in the new world space of img_rc (NN to keep labels crisp)
  if [ -n "${brain_mask}" ] && [ -f "${brain_mask}" ]; then
    antsApplyTransforms -d 3 \
      -i "${brain_mask}" \
      -o "${anat_dir}/subj_${subject}_T1_crop_sanlm_n4_brain_mask_rc.nii.gz" \
      -r "${img_rc}" -t "${xfm}" -n NearestNeighbor
  fi
  for m in "${anat_dir}"/segment/segment_*.nii.gz; do
    [ -e "$m" ] || continue
    antsApplyTransforms -d 3 \
      -i "${m}" \
      -o "${m%.*}_rc.nii.gz" \
      -r "${img_rc}" -t "${xfm}" -n NearestNeighbor
  done
fi

echo "✓ centered image  -> ${img_rc}"
echo "✓ recenter xfm    -> ${xfm}"
if [ -n "${brain_mask}" ] && [ -f "${brain_mask}" ]; then
  echo "✓ centered mask   -> ${anat_dir}/subj_${subject}_T1_crop_sanlm_n4_brain_mask_rc.nii.gz"
else
  echo "✓ no brain mask provided; skipped mask output"
fi

# ---------- cleanup ----------
rm -f "${nib_recenter_py}"
