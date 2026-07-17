#!/bin/bash
# run_weber_mechanism.sbatch -- Step 2 of the CAST contrast-deficit mechanism test.
# HPC-COMPLIANT replacement for the stopped login-node workflow: ALL compute runs
# here, inside the scheduler-allocated job (sbatch), never on the cluster login node.
#
# Measures WM-GM Weber contrast (mask-free 3-class Otsu, + mask-based cross-checks on
# templates) for, per stratum: the averaged CAST 0.8 mm template, the matched NKI
# template, and K individual CSF-normalized construction subjects (the inputs that
# were averaged). If individual subjects are NKI-like (high Weber) while the CAST
# template is markedly lower -> the contrast deficit is created by AVERAGING, and
# full-library re-normalization (a per-subject global scalar) cannot fix it.
#
# Submit from the cluster login node:  sbatch run_weber_mechanism.sbatch
#SBATCH --job-name=cast-weber-mech
#SBATCH --output=cast-weber-mech-%j.out
#SBATCH --error=cast-weber-mech-%j.err
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --mem=16G
#SBATCH --time=00:40:00
set -uo pipefail

DB="${DB:-${DB:-/path/to/cast_data}}"
SIF=${C_REG:-cast_reg.sif}
PY=$DB/validity_heatmap_scripts/weber_mech.py
OUT=$DB/Validity/mechanism_weber
mkdir -p "$OUT"
MAN=$OUT/manifest.txt
RES=$OUT/weber_mechanism.jsonl
K=15                                   # individual subjects sampled per stratum
: > "$MAN"

TPLDIR=$DB/Templates/UpdatedTemplates_0p8
NKIDIR=$DB/Validity/refbench_0p8/templates_nki0p8

# strata with BOTH a CAST 0.8 mm template AND a matched NKI template (NKI is sex-neutral)
#   spec = "<cast_age> <cast_sex> <nki_age>"
STRATA=("7 male 7" "8 male 8" "8 female 8" "9 female 9")

for spec in "${STRATA[@]}"; do
  set -- $spec; AGE=$1; SEX=$2; NK=$3
  TPL=$TPLDIR/age${AGE}_${SEX}_template.nii.gz
  TWM=$TPLDIR/age${AGE}_${SEX}_wm.nii.gz
  TGM=$TPLDIR/age${AGE}_${SEX}_gm.nii.gz
  TBM=$TPLDIR/age${AGE}_${SEX}_brain_mask.nii.gz
  [[ -f "$TPL" ]] && echo "cast_template|age${AGE}_${SEX}|${AGE}|${SEX}|${TPL}|${TBM}|${TWM}|${TGM}" >> "$MAN"

  NTPL=$NKIDIR/NKI_age${NK}_brain_template.nii.gz
  NWM=$NKIDIR/NKI_age${NK}_wm.nii.gz
  [[ -f "$NTPL" ]] && echo "nki_template|NKI_age${NK}|${NK}|na|${NTPL}|NONE|${NWM}|NONE" >> "$MAN"

  # evenly sample K construction subjects (deterministic: sort, stride).
  # IMPORTANT: keep ONLY pure subject intensity images (NDAR<id>.nii.gz); the dir
  # also holds ANTs construction intermediates (template0_*Warp/InverseWarp.nii.gz)
  # which are deformation fields, NOT intensities, and must be excluded.
  SUBDIR=$DB/Age${AGE}/${SEX}/intensity_improved_selected_for_template
  mapfile -t SUBS < <(ls -1 "$SUBDIR"/*.nii.gz 2>/dev/null | grep -E '/NDAR[A-Z0-9]+\.nii\.gz$' | sort)
  ntot=${#SUBS[@]}
  if (( ntot > 0 )); then
    step=$(( ntot > K ? ntot / K : 1 ))
    c=0
    for (( i=0; i<ntot && c<K; i+=step )); do
      img=${SUBS[$i]}; eid=$(basename "$img" .nii.gz)
      echo "subject|${eid}_age${AGE}_${SEX}|${AGE}|${SEX}|${img}|NONE|NONE|NONE" >> "$MAN"
      c=$((c+1))
    done
    echo "[manifest] age${AGE}_${SEX}: ${ntot} subjects available, sampled ${c}"
  else
    echo "[warn] no construction subjects in $SUBDIR"
  fi
done

echo "[manifest] $(wc -l < "$MAN") items -> $MAN"
echo "[run] single container start, processing manifest ..."
apptainer exec --bind "$DB":"$DB" "$SIF" python3 "$PY" "$MAN" "$RES"
echo "[done] results -> $RES"

# inline summary: per-stratum subject median vs template vs NKI (numpy in container)
apptainer exec --bind "$DB":"$DB" "$SIF" python3 - "$RES" <<'PYEOF'
import json, sys
from collections import defaultdict
import numpy as np
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
subj = defaultdict(list); cast = {}; nki = {}
for r in recs:
    if r.get("error"): continue
    key = f"age{r['age']}_{r['sex']}"
    if r["kind"] == "subject": subj[key].append(r["weber_otsu"])
    elif r["kind"] == "cast_template": cast[key] = r
    elif r["kind"] == "nki_template": nki[r["label"]] = r
print("\n=== Weber-contrast locus summary (Otsu mask-free) ===")
print(f"{'stratum':14s} {'subj_med':>9s} {'subj_iqr':>14s} {'CASTtpl':>8s} {'NKItpl':>8s} {'subj-CASTtpl':>13s}")
for key in sorted(cast):
    s = np.array(subj.get(key, []), float)
    ct = cast[key]["weber_otsu"]
    nlabel = [k for k in nki if k.endswith(key.split('_')[0].replace('age','')) or True]
    # nki keyed by NKI_age<NK>; map via cast record's age
    nt = next((v["weber_otsu"] for k,v in nki.items()), float('nan'))
    sm = float(np.median(s)) if s.size else float('nan')
    q1,q3 = (np.percentile(s,[25,75]) if s.size else (float('nan'),)*2)
    print(f"{key:14s} {sm:9.4f} [{q1:6.4f},{q3:6.4f}] {ct:8.4f} {nt:8.4f} {sm-ct:13.4f}")
print("\n(interpretation: subj_med >> CASTtpl  => contrast lost at AVERAGING => re-normalization won't help)")
print("template mask-based cross-checks (should track published CAST~0.277 / NKI~0.393 operative):")
for r in recs:
    if r.get("kind","").endswith("template") and "weber_ring_operative" in r:
        print(f"  {r['label']:14s} otsu={r['weber_otsu']:.4f}  ring_operative={r['weber_ring_operative']:.4f}"
              + (f"  wmgm_mask={r['weber_wmgm_mask']:.4f}" if 'weber_wmgm_mask' in r else ""))
PYEOF
echo "[summary-done]"
