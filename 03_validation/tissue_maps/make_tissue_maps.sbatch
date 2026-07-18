#!/usr/bin/env bash
#SBATCH --job-name=bcast-tpm
#SBATCH --output=${WORK}/bcast-gpu-%j.out
#SBATCH --partition=gpu
#SBATCH --qos=standby
#SBATCH --gres=gpu:1
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -uo pipefail
SIF=${IMG}/mri_template_env_reg.sif
TDIR=${DB}/Templates/UpdatedTemplates
WORK=${WORK}; OUT=$WORK/out
mkdir -p $OUT
apptainer exec --bind /project/contreras-vidal:/project/contreras-vidal $SIF /bin/bash -c '
source /usr/local/fsl/etc/fslconf/fsl.sh; export FSLDIR=/usr/local/fsl
export PATH="/usr/local/fsl/share/fsl/bin:/opt/ANTs/install/bin:$PATH"; export FSLOUTPUTTYPE=NIFTI_GZ
TDIR='"$TDIR"'; OUT='"$OUT"'
one() { local A=$1 S=$2 TPL=$TDIR/age${A}_${S}_template.nii.gz MSRC=$TDIR/age${A}_${S}_brain_mask.nii.gz MASK
  [ -f "$TPL" ] || { echo "[MISS] age${A}_${S}"; return; }
  if [ -f "$MSRC" ]; then MASK=$MSRC
  else MASK=$OUT/age${A}_${S}_brain_mask.nii.gz; T=$(mktemp -d)
    ImageMath 3 "$T/m0.nii.gz" ThresholdAtMean "$TPL" 1; ImageMath 3 "$T/m1.nii.gz" ME "$T/m0.nii.gz" 1
    ImageMath 3 "$T/m2.nii.gz" MD "$T/m1.nii.gz" 2; ImageMath 3 "$T/m3.nii.gz" GetLargestComponent "$T/m2.nii.gz"
    ImageMath 3 "$MASK" FillHoles "$T/m3.nii.gz" 2; rm -rf "$T"; echo "[mask-new] age${A}_${S}"; fi
  fslmaths "$TPL" -mas "$MASK" "$OUT/brain_${A}_${S}.nii.gz"
  if fast -t 1 -n 3 -g -o "$OUT/f_${A}_${S}" "$OUT/brain_${A}_${S}.nii.gz" >"$OUT/fast_${A}_${S}.log" 2>&1; then
    mv "$OUT/f_${A}_${S}_pve_0.nii.gz" "$OUT/age${A}_${S}_csf.nii.gz"
    mv "$OUT/f_${A}_${S}_pve_1.nii.gz" "$OUT/age${A}_${S}_gm.nii.gz"
    mv "$OUT/f_${A}_${S}_pve_2.nii.gz" "$OUT/age${A}_${S}_wm.nii.gz"
    rm -f "$OUT/f_${A}_${S}"_seg*.nii.gz "$OUT/f_${A}_${S}_mixeltype.nii.gz" "$OUT/f_${A}_${S}_pveseg.nii.gz" "$OUT/brain_${A}_${S}.nii.gz"
    echo "[ok] age${A}_${S}"; else echo "[ERR-FAST] age${A}_${S}"; fi; }
N=0
for A in 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do for S in female male; do
  one $A $S & N=$((N+1)); [ $((N%8)) -eq 0 ] && wait
done; done; wait
echo "=== DONE outputs: $(ls $OUT/*_gm.nii.gz $OUT/*_wm.nii.gz $OUT/*_csf.nii.gz $OUT/*_brain_mask.nii.gz 2>/dev/null | wc -l) ==="
'
