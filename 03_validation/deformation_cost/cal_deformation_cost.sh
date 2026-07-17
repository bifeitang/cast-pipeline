#!/usr/bin/env bash
# cal_deformation_cost.sh
# -------------------------------------------------------------
# Register a subject T1 to a template and compute deformation cost metrics:
#  - Mean/median/95th displacement magnitude (mm) from a COMPOSED displacement field (Affine + Warp)
#  - Jacobian stats (mean logJ, std logJ, % non-diffeomorphic where detJ <= 0) computed on the SAME field
#  - Normalized displacement by a characteristic length L (default: template ICV^(1/3))
#
# Requirements: ANTs (antsRegistrationSyN.sh, antsApplyTransforms, CreateJacobianDeterminantImage, ImageMath, PrintHeader),
#               FSL (fslstats).
#
# Usage:
#   cal_deformation_cost.sh \
#       --moving <subject_T1.nii.gz> \
#       [--moving-mask <subject_brain_mask.nii.gz>] \
#       [--template <template_T1.nii.gz>] \
#       [--template-mask <template_brain_mask.nii.gz>] \
#       --outdir <output_dir> \
#       [--mode syn|bsplinesyn] \
#       [-transform-direction moving2template|template2moving] \
#       [-diagnostics] \
#       [-mask-method provided|mean|otsu] \
#       [-normalize template_icv|subject_icv|geom_mean_icv|diag|none]
#
# If --template is omitted, defaults to Templates/age9_male_template.nii.gz
#
# Notes:
#   * Masking:
#       provided : require --moving-mask and --template-mask
#       mean     : auto mask via ThresholdAtMean + largest component (default)
#       otsu     : try ImageMath OtsuThreshold; if unavailable, fall back to mean with a warning
#   * Normalization length (L):
#       template_icv   : L = (ICV_template_mm3)^(1/3) from template mask (default)
#       subject_icv    : L = (ICV_subject_mm3)^(1/3) from moving mask
#       geom_mean_icv  : L = (sqrt(ICV_template_mm3 * ICV_subject_mm3))^(1/3)
#       diag           : L = template spatial diagonal (mm) from template header
#       none           : L = 1 (no normalization)
#
# Outputs (in --outdir):
#   transform/             - affine + warp from antsRegistrationSyN.sh
#   total_disp.nii.gz      - composed displacement field (vector) in template space (reference grid = template)
#   disp_mag.nii.gz        - displacement magnitude map (mm) from total_disp in template space
#   logJ_total.nii.gz      - log-Jacobian map computed from total_disp
#   detJ_total.nii.gz      - Jacobian determinant map computed from total_disp
#   metrics.txt            - single-line TSV with stable header
#   metrics_diagnostics.txt- (optional) forward+inverse metrics if -diagnostics is enabled

set -euo pipefail
IFS=$'\n\t'

MODE="syn"
NORM="template_icv"
TRANSFORM_DIRECTION="moving2template"
DIAGNOSTICS=0
MASK_METHOD="mean"

MOVING=""
TMPL=""
MMASK=""
TMASK=""
OUTDIR=""

usage() {
  grep -m1 -A250 "^# cal_deformation_cost.sh" "$0" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --moving) MOVING="${2:-}"; shift 2;;
    --moving-mask) MMASK="${2:-}"; shift 2;;
    --template) TMPL="${2:-}"; shift 2;;
    --template-mask) TMASK="${2:-}"; shift 2;;
    --outdir) OUTDIR="${2:-}"; shift 2;;
    --mode) MODE="${2:-}"; shift 2;;

    -transform-direction|--transform-direction) TRANSFORM_DIRECTION="${2:-}"; shift 2;;
    -diagnostics|--diagnostics) DIAGNOSTICS=1; shift 1;;
    -mask-method|--mask-method) MASK_METHOD="${2:-}"; shift 2;;
    -normalize|--normalize) NORM="${2:-}"; shift 2;;

    -h|--help) usage; exit 0;;
    *) echo "ERROR: Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TPL_DIR="${DB_DIR}/Templates"
FSLDIR="${FSLDIR:-/usr/local/fsl}"

cleanup_paths=()
cleanup() {
  for p in "${cleanup_paths[@]:-}"; do
    rm -rf "${p}" 2>/dev/null || true
  done
}
trap cleanup EXIT

need_cmd() {
  local c="$1"
  command -v "${c}" >/dev/null 2>&1 || { echo "ERROR: Required command not found on PATH: ${c}" >&2; exit 1; }
}

need_cmd antsRegistrationSyN.sh
need_cmd antsApplyTransforms
need_cmd CreateJacobianDeterminantImage
need_cmd ImageMath
need_cmd PrintHeader
need_cmd python3

# Ensure FSL is on PATH if available (inside or outside container)
if ! command -v fslstats >/dev/null 2>&1; then
  if [[ -n "${FSLDIR:-}" && -f "${FSLDIR}/etc/fslconf/fsl.sh" ]]; then
    # shellcheck disable=SC1090
    . "${FSLDIR}/etc/fslconf/fsl.sh"
  fi
fi
if ! command -v fslstats >/dev/null 2>&1; then
  for d in \
    /usr/local/fsl/share/fsl/bin \
    /usr/local/fsl/bin \
    /opt/fsl/bin \
    /usr/share/fsl/6.0/bin \
    /usr/lib/fsl; do
    if [[ -d "$d" ]]; then export PATH="$d:$PATH"; fi
  done
fi
need_cmd fslstats

# Default template under Templates/ if not provided
if [[ -z "${TMPL}" ]]; then
  TMPL="${TPL_DIR}/age9_male_template.nii.gz"
fi

if [[ -z "${MOVING}" || -z "${OUTDIR}" ]]; then
  echo "ERROR: --moving and --outdir are required." >&2
  usage
  exit 1
fi

mkdir -p "${OUTDIR}/transform"

# Prefer existing template mask beside the template if not provided
if [[ -z "${TMASK}" ]]; then
  base_tmpl_name="$(basename "${TMPL}")"
  if [[ "${base_tmpl_name}" == *_template.nii.gz ]]; then
    cand_mask="$(dirname "${TMPL}")/${base_tmpl_name/_template.nii.gz/_brain_mask.nii.gz}"
    if [[ -f "${cand_mask}" ]]; then
      TMASK="${cand_mask}"
    fi
  fi
fi

warn_obliquity() {
  local img="$1"
  local dir_mat
  dir_mat="$(PrintHeader "${img}" | awk '
    BEGIN{inside=0; count=0;}
    /Direction/ {inside=1; next;}
    inside==1 {
      gsub(/[\[\],]/," ");
      if ($0 ~ /[0-9]/) { print; count++; }
      if (count>=3) { exit; }
    }')"
  if [[ -z "${dir_mat}" ]]; then
    return 0
  fi
  python3 - <<'PY' "${dir_mat}"
import sys, math, re
txt = sys.argv[1]
nums = [float(x) for x in re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|[-+]?\d+(?:[eE][-+]?\d+)?', txt)]
if len(nums) < 9:
    sys.exit(0)
M = [nums[0:3], nums[3:6], nums[6:9]]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def norm(a): return math.sqrt(dot(a,a))
rows = M
cols = list(zip(*M))
max_off = 0.0
max_diag_err = 0.0
for i in range(3):
    for j in range(3):
        v = dot(rows[i], rows[j])
        if i==j:
            max_diag_err = max(max_diag_err, abs(v-1.0))
        else:
            max_off = max(max_off, abs(v))
row_norm_err = max(abs(norm(r)-1.0) for r in rows)
col_norm_err = max(abs(norm(c)-1.0) for c in cols)
if max_off > 0.01 or max_diag_err > 0.01 or row_norm_err > 0.01 or col_norm_err > 0.01:
    print("WARNING: Template appears oblique; Jacobian determinants may be unreliable. Consider reorienting/resampling to orthogonal grid.", file=sys.stderr)
PY
}

warn_obliquity "${TMPL}"

TMPDIR="$(mktemp -d "${OUTDIR}/tmp.cal_deformation_cost.XXXXXX")"
cleanup_paths+=("${TMPDIR}")

auto_mask_mean() {
  local img="$1"
  local out="$2"
  if [[ -f "${out}" ]]; then
    return 0
  fi
  echo "[mask] mean-thresholding mask: ${img} -> ${out}" >&2
  ImageMath 3 "${TMPDIR}/mask_tmp.nii.gz" ThresholdAtMean "${img}" 0.5
  ImageMath 3 "${TMPDIR}/mask_lc.nii.gz" GetLargestComponent "${TMPDIR}/mask_tmp.nii.gz"
  ImageMath 3 "${out}" MD "${TMPDIR}/mask_lc.nii.gz" 1
}

auto_mask_otsu_or_fallback() {
  local img="$1"
  local out="$2"
  if [[ -f "${out}" ]]; then
    return 0
  fi
  echo "[mask] attempting OtsuThreshold mask: ${img} -> ${out}" >&2
  set +e
  ImageMath 3 "${out}" OtsuThreshold "${img}" 1 >/dev/null 2>&1
  rc=$?
  set -e
  if [[ ${rc} -ne 0 || ! -f "${out}" ]]; then
    echo "WARNING: ImageMath OtsuThreshold unavailable/failed; falling back to mean-thresholding mask." >&2
    auto_mask_mean "${img}" "${out}"
  fi
}

case "${MASK_METHOD}" in
  provided)
    if [[ -z "${MMASK}" || -z "${TMASK}" ]]; then
      echo "ERROR: -mask-method provided requires --moving-mask and --template-mask." >&2
      exit 1
    fi
    if [[ ! -f "${MMASK}" ]]; then echo "ERROR: moving mask not found: ${MMASK}" >&2; exit 1; fi
    if [[ ! -f "${TMASK}" ]]; then echo "ERROR: template mask not found: ${TMASK}" >&2; exit 1; fi
    ;;
  mean|otsu)
    if [[ -z "${MMASK}" ]]; then MMASK="${OUTDIR}/moving_mask.nii.gz"; fi
    if [[ -z "${TMASK}" ]]; then TMASK="${OUTDIR}/template_mask.nii.gz"; fi
    if [[ "${MASK_METHOD}" == "mean" ]]; then
      auto_mask_mean "${MOVING}" "${MMASK}"
      auto_mask_mean "${TMPL}" "${TMASK}"
    else
      auto_mask_otsu_or_fallback "${MOVING}" "${MMASK}"
      auto_mask_otsu_or_fallback "${TMPL}" "${TMASK}"
    fi
    ;;
  *)
    echo "ERROR: -mask-method must be provided|mean|otsu" >&2
    exit 1
    ;;
esac

# ---------- Registration (reused if already present) ----------
echo "[registration] Mode: ${MODE}" >&2
REGOUT="${OUTDIR}/transform/sub2tpl"
AFF="${REGOUT}_0GenericAffine.mat"
WARP="${REGOUT}_1Warp.nii.gz"
INVWARP="${REGOUT}_1InverseWarp.nii.gz"

if [[ -f "${AFF}" && -f "${WARP}" ]]; then
  echo "[registration] Reusing existing transforms: ${AFF}, ${WARP}" >&2
else
  if [[ "${MODE}" == "syn" ]]; then
    antsRegistrationSyN.sh -d 3 -f "${TMPL}" -m "${MOVING}" -o "${REGOUT}_" -n 8 -t s
  elif [[ "${MODE}" == "bsplinesyn" ]]; then
    antsRegistrationSyN.sh -d 3 -f "${TMPL}" -m "${MOVING}" -o "${REGOUT}_" -n 8 -t b
  else
    echo "ERROR: Unsupported --mode ${MODE}. Use syn|bsplinesyn." >&2
    exit 1
  fi
fi

if [[ ! -f "${AFF}" || ! -f "${WARP}" ]]; then
  echo "ERROR: Registration outputs not found: ${AFF} and/or ${WARP}" >&2
  exit 1
fi

make_total_disp() {
  local direction="$1"
  local out="$2"
  case "${direction}" in
    moving2template)
      antsApplyTransforms -d 3 -r "${TMPL}" -o "[${out},1]" -t "${WARP}" -t "${AFF}"
      ;;
    template2moving)
      if [[ ! -f "${INVWARP}" ]]; then
        echo "ERROR: Inverse warp not found for template2moving: ${INVWARP}" >&2
        exit 1
      fi
      antsApplyTransforms -d 3 -r "${TMPL}" -o "[${out},1]" -t "[${AFF},1]" -t "${INVWARP}"
      ;;
    *)
      echo "ERROR: -transform-direction must be moving2template|template2moving" >&2
      exit 1
      ;;
  esac
}

vector_magnitude() {
  local vec="$1"
  local out="$2"
  local dx="${TMPDIR}/dx.nii.gz"
  local dy="${TMPDIR}/dy.nii.gz"
  local dz="${TMPDIR}/dz.nii.gz"
  local dx2="${TMPDIR}/dx2.nii.gz"
  local dy2="${TMPDIR}/dy2.nii.gz"
  local dz2="${TMPDIR}/dz2.nii.gz"
  local sumxy="${TMPDIR}/sumxy.nii.gz"
  local sumsq="${TMPDIR}/sumsq.nii.gz"

  ImageMath 3 "${dx}" ExtractVectorComponent "${vec}" 0
  ImageMath 3 "${dy}" ExtractVectorComponent "${vec}" 1
  ImageMath 3 "${dz}" ExtractVectorComponent "${vec}" 2

  # Squares (op comes last in this ImageMath version)
  ImageMath 3 "${dx2}" m "${dx}" "${dx}"
  ImageMath 3 "${dy2}" m "${dy}" "${dy}"
  ImageMath 3 "${dz2}" m "${dz}" "${dz}"

  ImageMath 3 "${sumxy}" + "${dx2}" "${dy2}"
  ImageMath 3 "${sumsq}" + "${sumxy}" "${dz2}"
  ImageMath 3 "${out}" ^ "${sumsq}" 0.5
}

get_spacing() {
  local img="$1"
  PrintHeader "${img}" | awk -F'[][]' '/Voxel Spacing/ {gsub(/,/," ",$2); print $2; exit}'
}

get_voxvol() {
  local img="$1"
  local s
  s="$(get_spacing "${img}")"
  python3 - <<PY
sx,sy,sz = map(float, "${s:-1 1 1}".split())
print(f"{sx*sy*sz:.6f}")
PY
}

get_dimens() {
  local img="$1"
  PrintHeader "${img}" | awk -F'[][]' '/Dimens/ {gsub(/,/," ",$2); print $2; exit}'
}

template_voxvol="$(get_voxvol "${TMPL}")"
moving_voxvol="$(get_voxvol "${MOVING}")"

template_icv_mm3() {
  local icv_vox
  icv_vox="$(fslstats "${TMASK}" -V | awk '{print $1}')"
  python3 - <<PY
icv=${icv_vox}; vv=${template_voxvol}
print(f"{float(icv)*float(vv):.6f}")
PY
}

moving_icv_mm3() {
  local icv_vox
  icv_vox="$(fslstats "${MMASK}" -V | awk '{print $1}')"
  python3 - <<PY
icv=${icv_vox}; vv=${moving_voxvol}
print(f"{float(icv)*float(vv):.6f}")
PY
}

compute_L_mm() {
  local norm="$1"
  case "${norm}" in
    template_icv)
      local tmm3
      tmm3="$(template_icv_mm3)"
      python3 - <<PY
import math
print(f"{math.pow(float('${tmm3}'), 1/3):.6f}")
PY
      ;;
    subject_icv)
      local smm3
      smm3="$(moving_icv_mm3)"
      python3 - <<PY
import math
print(f"{math.pow(float('${smm3}'), 1/3):.6f}")
PY
      ;;
    geom_mean_icv)
      local tmm3 smm3
      tmm3="$(template_icv_mm3)"
      smm3="$(moving_icv_mm3)"
      python3 - <<PY
import math
t=float('${tmm3}'); s=float('${smm3}')
g=math.sqrt(max(t,0.0)*max(s,0.0))
print(f"{math.pow(g, 1/3):.6f}")
PY
      ;;
    diag)
      local dims sp
      dims="$(get_dimens "${TMPL}")"
      sp="$(get_spacing "${TMPL}")"
      python3 - <<PY
import math
nx,ny,nz = map(float, "${dims}".split())
sx,sy,sz = map(float, "${sp}".split())
Lx=nx*sx; Ly=ny*sy; Lz=nz*sz
print(f"{math.sqrt(Lx*Lx+Ly*Ly+Lz*Lz):.6f}")
PY
      ;;
    none)
      echo "1.000000"
      ;;
    *)
      echo "ERROR: -normalize must be template_icv|subject_icv|geom_mean_icv|diag|none" >&2
      exit 1
      ;;
  esac
}

L_MM="$(compute_L_mm "${NORM}")"

compute_metrics_for_field() {
  local vec_field="$1"
  local disp_mag="$2"
  local logJ="$3"
  local detJ="$4"
  local out_metrics="$5"
  local direction_label="$6"

  vector_magnitude "${vec_field}" "${disp_mag}"

  CreateJacobianDeterminantImage 3 "${vec_field}" "${logJ}" 1
  CreateJacobianDeterminantImage 3 "${vec_field}" "${detJ}" 0

  local mean_disp median_disp p95_disp
  mean_disp="$(fslstats "${disp_mag}" -k "${TMASK}" -M | awk '{print $1}')"
  median_disp="$(fslstats "${disp_mag}" -k "${TMASK}" -P 50 | awk '{print $1}')"
  p95_disp="$(fslstats "${disp_mag}" -k "${TMASK}" -P 95 | awk '{print $1}')"

  local mean_logJ std_logJ
  mean_logJ="$(fslstats "${logJ}" -k "${TMASK}" -M | awk '{print $1}')"
  std_logJ="$(fslstats "${logJ}" -k "${TMASK}" -S | awk '{print $1}')"

  local neg_count mask_count pct_non_diff
  neg_count="$(fslstats "${detJ}" -k "${TMASK}" -l -100000 -u 0 -V | awk '{print $1}')"
  mask_count="$(fslstats "${TMASK}" -V | awk '{print $1}')"
  pct_non_diff="$(python3 - <<PY
neg=float(${neg_count}); tot=float(${mask_count})
print(f"{(0.0 if tot==0.0 else 100.0*neg/tot):.6f}")
PY
)"

  local norm_mean_disp norm_median_disp norm_p95_disp
  norm_mean_disp="$(python3 - <<PY
print(f"{float(${mean_disp})/float(${L_MM}):.6f}")
PY
)"
  norm_median_disp="$(python3 - <<PY
print(f"{float(${median_disp})/float(${L_MM}):.6f}")
PY
)"
  norm_p95_disp="$(python3 - <<PY
print(f"{float(${p95_disp})/float(${L_MM}):.6f}")
PY
)"

  if [[ "${out_metrics}" == "metrics.txt" ]]; then
    {
      printf "moving\ttemplate\tmode\ttransform_direction\tmask_method\tnorm_type\tL_mm\tmean_disp_mm\tmedian_disp_mm\tp95_disp_mm\tnorm_mean_disp\tnorm_median_disp\tnorm_p95_disp\tmean_logJ\tstd_logJ\tpct_non_diffeomorphic\twarp_value_mm\tnormalized_warp_value\n"
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$(basename "${MOVING}")" \
        "$(basename "${TMPL}")" \
        "${MODE}" \
        "${TRANSFORM_DIRECTION}" \
        "${MASK_METHOD}" \
        "${NORM}" \
        "${L_MM}" \
        "${mean_disp}" \
        "${median_disp}" \
        "${p95_disp}" \
        "${norm_mean_disp}" \
        "${norm_median_disp}" \
        "${norm_p95_disp}" \
        "${mean_logJ}" \
        "${std_logJ}" \
        "${pct_non_diff}" \
        "${mean_disp}" \
        "${norm_mean_disp}"
    } > "${OUTDIR}/${out_metrics}"
  else
    # diagnostics: append lines with a direction label
    if [[ ! -f "${OUTDIR}/${out_metrics}" ]]; then
      printf "direction\tmoving\ttemplate\tmode\tmask_method\tnorm_type\tL_mm\tmean_disp_mm\tmedian_disp_mm\tp95_disp_mm\tnorm_mean_disp\tnorm_median_disp\tnorm_p95_disp\tmean_logJ\tstd_logJ\tpct_non_diffeomorphic\n" > "${OUTDIR}/${out_metrics}"
    fi
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${direction_label}" \
      "$(basename "${MOVING}")" \
      "$(basename "${TMPL}")" \
      "${MODE}" \
      "${MASK_METHOD}" \
      "${NORM}" \
      "${L_MM}" \
      "${mean_disp}" \
      "${median_disp}" \
      "${p95_disp}" \
      "${norm_mean_disp}" \
      "${norm_median_disp}" \
      "${norm_p95_disp}" \
      "${mean_logJ}" \
      "${std_logJ}" \
      "${pct_non_diff}" >> "${OUTDIR}/${out_metrics}"
  fi
}

# ---------- Compose total displacement field (Affine + Warp) ----------
TOTAL_DISP="${OUTDIR}/total_disp.nii.gz"
echo "[compose] transform_direction=${TRANSFORM_DIRECTION} -> ${TOTAL_DISP}" >&2
make_total_disp "${TRANSFORM_DIRECTION}" "${TOTAL_DISP}"

# ---------- Primary metrics (computed on total displacement) ----------
DISP_MAG="${OUTDIR}/disp_mag.nii.gz"
LOGJ_TOTAL="${OUTDIR}/logJ_total.nii.gz"
DETJ_TOTAL="${OUTDIR}/detJ_total.nii.gz"

compute_metrics_for_field "${TOTAL_DISP}" "${DISP_MAG}" "${LOGJ_TOTAL}" "${DETJ_TOTAL}" "metrics.txt" "${TRANSFORM_DIRECTION}"

# ---------- Optional diagnostics: compute BOTH directions ----------
if [[ "${DIAGNOSTICS}" -eq 1 ]]; then
  echo "[diagnostics] computing forward+inverse metrics" >&2
  fwd_disp="${OUTDIR}/total_disp_forward.nii.gz"
  inv_disp="${OUTDIR}/total_disp_inverse.nii.gz"
  make_total_disp "moving2template" "${fwd_disp}"
  make_total_disp "template2moving" "${inv_disp}"

  compute_metrics_for_field "${fwd_disp}" "${OUTDIR}/disp_mag_forward.nii.gz" "${OUTDIR}/logJ_forward.nii.gz" "${OUTDIR}/detJ_forward.nii.gz" "metrics_diagnostics.txt" "moving2template"
  compute_metrics_for_field "${inv_disp}" "${OUTDIR}/disp_mag_inverse.nii.gz" "${OUTDIR}/logJ_inverse.nii.gz" "${OUTDIR}/detJ_inverse.nii.gz" "metrics_diagnostics.txt" "template2moving"

  # Also keep legacy Jacobian outputs on the raw warp for comparison
  CreateJacobianDeterminantImage 3 "${WARP}" "${OUTDIR}/logJ_warp_only.nii.gz" 1
  CreateJacobianDeterminantImage 3 "${WARP}" "${OUTDIR}/detJ_warp_only.nii.gz" 0
fi

echo "[done] Metrics written to ${OUTDIR}/metrics.txt" >&2