#!/bin/bash
# tissue_jacobian_worker.sh (runs INSIDE container)
# Re-run the matched-template SyN (warp fields were not retained by the sweep), compute the
# log-Jacobian of the warp, and reduce it within template GM/WM/CSF masks -> per-tissue
# mean/SD log-Jacobian and % non-diffeomorphic. Args: <EID> <AGE> <SEX> <NT>
set -uo pipefail
EID="${1:?}"; AGE="${2:?}"; SEX="${3:?}"; NT="${4:-8}"
if [[ -f /usr/local/fsl/etc/fslconf/fsl.sh ]]; then . /usr/local/fsl/etc/fslconf/fsl.sh; fi
export PATH="$PATH:/opt/ANTs/install/bin" ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="$NT" OMP_NUM_THREADS="$NT"
TPLDIR=/mnt/Templates/UpdatedTemplates
TISS=/mnt/Validity/templates_tissue
OUT=/mnt/Validity/tissue_jac/$EID
M_TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
export TMPDIR=$OUT
cd "$OUT" || exit 1
[[ -f moving.nii.gz ]] || { echo "[ERR] no moving $EID"; exit 1; }
if [[ ! -f m_1Warp.nii.gz ]]; then
  antsRegistrationSyN.sh -d 3 -f "$M_TPL" -m moving.nii.gz -o m_ -t s -n "$NT" >/dev/null 2>&1 || { echo "[ERR] syn $EID"; exit 1; }
fi
# log-Jacobian (for magnitude stats) and geometric Jacobian (for %<=0)
CreateJacobianDeterminantImage 3 m_1Warp.nii.gz logJ.nii.gz 1 0 >/dev/null 2>&1
CreateJacobianDeterminantImage 3 m_1Warp.nii.gz rawJ.nii.gz 0 0 >/dev/null 2>&1
python3 - "$EID" "$AGE" "$SEX" "$TISS/age${AGE}_${SEX}" <<'PY'
import sys, json
import numpy as np, nibabel as nib
eid,age,sex,tbase=sys.argv[1:5]
logJ=nib.load("logJ.nii.gz").get_fdata(); rawJ=nib.load("rawJ.nii.gz").get_fdata()
out={"subject_id":eid,"age":int(age),"sex":sex}
for t in ["gm","wm","csf"]:
    try:
        m=nib.load(f"{tbase}_{t}.nii.gz").get_fdata()>0.5
        lj=logJ[m]; rj=rawJ[m]
        out[t]={"n_vox":int(m.sum()),"mean_logJ":float(lj.mean()),"std_logJ":float(lj.std()),
                "pct_nondiffeo":float(100.0*np.mean(rj<=0))}
    except Exception as e:
        out[t]={"error":str(e)}
print(json.dumps(out))
PY
# the above prints JSON to stdout (captured by sbatch redirect); clean heavy fields
rm -f m_1Warp.nii.gz m_1InverseWarp.nii.gz m_Warped.nii.gz m_InverseWarped.nii.gz logJ.nii.gz rawJ.nii.gz moving.nii.gz 2>/dev/null || true
