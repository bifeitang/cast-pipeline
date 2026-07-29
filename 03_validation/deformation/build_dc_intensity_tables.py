#!/usr/bin/env python3
"""Turn the 5,104 intensity-rerun metrics.txt files into the derived tables the figures
and verify_claims.py read.

WHY THIS EXISTS
---------------
Every deformation-cost registration in the published papers registered a BINARY BRAIN MASK
onto a greyscale intensity template (04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_
2026-07-28.md). CC has zero local variance inside a binary mask, so the optimiser matched an
outline while SyN regularisation drove the interior -- under-constrained, not merely harder.
All 5,104 registrations were rerun on the correct CSF-normalised intensity images.

The mask-era derived table (DeformationAnalysis/test_set_on_template_metrics_with_subject_age
.csv) is left untouched as the record of what was published. This script writes the
intensity-era replacements alongside it, and every consumer is repointed explicitly rather
than by overwriting -- so a stale reader fails loudly instead of silently mixing generations.

OUTPUTS
    DeformationAnalysis/test_set_on_template_metrics_INTENSITY.csv
        one row per registration, schema-compatible with the mask-era CSV
    DeformationAnalysis/tables/age9_jacobian_summary_by_age_gender_INTENSITY.csv
        per subject-age x template-sex Jacobian summary for the supplementary age-9 figure

JACOBIAN CONVENTION -- READ THIS
    mean_logJ / std_logJ in these files come from the COMPOSED affine o SyN field, because
    cal_deformation_cost.sh builds a separate composed field for the Jacobian whenever
    -disp-component syn is in force (see its lines 579-587). The displacement columns are
    SyN-only; the Jacobian columns are NOT. They are different quantities, not rescalings --
    the affine carries scale and shear. So these Jacobians remain NON-comparable with the
    SyN-only construction-warp (-0.032) and tissue (-0.03/-0.03/+0.05) figures, and the
    rerun did NOT bring the age-9 supplementary into their convention. It fixed the
    mask->intensity axis only. Do not describe it as like-for-like with Sec. 2.7.

USAGE
    python build_dc_intensity_tables.py
"""
from __future__ import annotations
import csv, glob, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DC = os.path.join(HERE, "dc_intensity")
DA = os.path.join(HERE, "DeformationAnalysis")
# The mask-era CSV is the only local source of per-subject float age and sex. Its
# deformation columns are superseded; its demographics are not.
DEMOG = os.path.join(DA, "test_set_on_template_metrics_with_subject_age.csv")

OUT_CSV = os.path.join(DA, "test_set_on_template_metrics_INTENSITY.csv")
OUT_A9 = os.path.join(DA, "tables", "age9_jacobian_summary_by_age_gender_INTENSITY.csv")

FIELDS = ["arm", "tpl_id", "template_age", "template_sex", "subject_id", "age_dir",
          "Age", "Sex_Text", "age_diff", "d_age", "abs_d_age", "sex_match",
          "mean_disp_mm", "median_disp_mm", "p95_disp_mm", "norm_mean_disp",
          "mean_logJ", "std_logJ", "pct_non_diffeomorphic", "disp_component",
          "display_dataset"]


def demographics() -> dict[str, tuple[float, str]]:
    """subject_id -> (float age, sex). Aborts if the mask-era CSV disagrees with itself."""
    info: dict[str, set] = {}
    with open(DEMOG) as fh:
        for r in csv.DictReader(fh):
            info.setdefault(r["subject_id"], set()).add(
                (float(r["Age"]), r["Sex_Text"].strip().lower()))
    bad = {k: v for k, v in info.items() if len(v) > 1}
    if bad:
        sys.exit(f"FATAL: inconsistent age/sex for {len(bad)} subjects in {DEMOG}")
    return {k: next(iter(v)) for k, v in info.items()}


def load() -> list[dict]:
    demo = demographics()
    rows, missing, mixed = [], set(), set()
    for arm in ("cast", "nki"):
        for p in glob.glob(os.path.join(DC, arm, "**", "metrics.txt"), recursive=True):
            parts = p.split(os.sep)
            tpl_id, age_dir, eid = parts[-4], int(parts[-3]), parts[-2]
            rec = list(csv.DictReader(open(p), delimiter="\t"))
            if len(rec) != 1:
                sys.exit(f"FATAL: {p} has {len(rec)} data rows, expected 1")
            m = rec[0]
            if m.get("disp_component") != "syn":
                mixed.add(m.get("disp_component"))
            if eid not in demo:
                missing.add(eid)
                continue
            age, sex = demo[eid]
            digits = "".join(c for c in tpl_id.replace("NKI_", "") if c.isdigit())
            tpl_age = int(digits)
            tpl_sex = ("female" if tpl_id.endswith("female")
                       else "male" if tpl_id.endswith("male") else "")
            rows.append(dict(
                arm=arm, tpl_id=tpl_id, template_age=tpl_age, template_sex=tpl_sex,
                subject_id=eid, age_dir=age_dir, Age=age, Sex_Text=sex,
                age_diff=age - tpl_age, d_age=tpl_age - age, abs_d_age=abs(tpl_age - age),
                # SexMatch is undefined for the sex-neutral NKI reference; empty, not 0.
                sex_match=("" if not tpl_sex else int(tpl_sex == sex)),
                mean_disp_mm=float(m["mean_disp_mm"]),
                median_disp_mm=float(m["median_disp_mm"]),
                p95_disp_mm=float(m["p95_disp_mm"]),
                norm_mean_disp=float(m["norm_mean_disp"]),
                mean_logJ=float(m["mean_logJ"]), std_logJ=float(m["std_logJ"]),
                pct_non_diffeomorphic=float(m["pct_non_diffeomorphic"]),
                disp_component=m["disp_component"],
                # keep the mask-era vocabulary so figure code needs a path change, not a rewrite
                display_dataset="My Template" if arm == "cast" else "Reference Template"))
    if mixed:
        sys.exit(f"FATAL: mixed disp_component in the run: {mixed} -- refusing to pool")
    if missing:
        sys.exit(f"FATAL: {len(missing)} subjects absent from {DEMOG}: "
                 f"{sorted(missing)[:5]}")
    # The directory age bin must be the floor of the float age, or the join is misaligned.
    off = [r for r in rows if int(np.floor(r["Age"])) != r["age_dir"]]
    if off:
        sys.exit(f"FATAL: {len(off)} rows where floor(Age) != directory age bin, "
                 f"e.g. {off[0]['subject_id']} Age={off[0]['Age']} dir={off[0]['age_dir']}")
    return rows


def age9_summary(rows: list[dict]) -> list[dict]:
    """Per subject-age x age-nine-template-sex Jacobian summary, with bootstrap 95% CIs.

    Mirrors the mask-era table this replaces so make_figure_age9_jacobian.py needs only a
    path change. CIs are percentile bootstrap of the mean, 5,000 resamples, fixed seed.
    """
    a9 = [r for r in rows if r["arm"] == "cast" and r["template_age"] == 9]
    rng = np.random.default_rng(0)
    out = []
    for age in sorted({r["age_dir"] for r in a9}):
        for sex in ("female", "male"):
            g = [r for r in a9 if r["age_dir"] == age and r["template_sex"] == sex]
            if not g:
                continue
            rec = dict(Age=age, template_gender=sex, n=len(g))
            for key, col in (("mean_logJ", "mean_logJ"), ("std_logJ", "std_logJ")):
                v = np.array([r[col] for r in g])
                bs = rng.choice(v, (5000, len(v)), replace=True).mean(axis=1)
                lo, hi = np.percentile(bs, [2.5, 97.5])
                rec[f"mean_{key}"] = float(v.mean())
                rec[f"ci_{key}_low"] = float(lo)
                rec[f"ci_{key}_high"] = float(hi)
            nd = np.array([r["pct_non_diffeomorphic"] for r in g])
            rec["mean_pct_non_diff"] = float(nd.mean())
            rec["rate_any_non_diff"] = float((nd > 0).mean())
            out.append(rec)
    return out


def main() -> int:
    rows = load()
    cast = [r for r in rows if r["arm"] == "cast"]
    nki = [r for r in rows if r["arm"] == "nki"]
    print(f"loaded {len(rows)} registrations: CAST {len(cast)}, NKI {len(nki)}")
    if len(cast) != 3190 or len(nki) != 1914:
        print(f"  WARNING: expected CAST 3190 / NKI 1914 -- the run may be incomplete")

    os.makedirs(os.path.dirname(OUT_A9), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["arm"], r["tpl_id"], r["subject_id"])))
    print(f"wrote {OUT_CSV}  ({len(rows)} rows)")

    a9 = age9_summary(rows)
    with open(OUT_A9, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(a9[0].keys()))
        w.writeheader()
        w.writerows(a9)
    n9 = sum(r["n"] for r in a9)
    print(f"wrote {OUT_A9}  ({len(a9)} strata, {n9} registrations)")

    d = np.array([r["mean_logJ"] for r in rows if r["arm"] == "cast"
                  and r["template_age"] == 9])
    print(f"\nage-9 pooled mean logJ {d.mean():+.4f}  "
          f"(COMPOSED affine o SyN, on intensity images -- not comparable with the "
          f"SyN-only -0.032 of the construction warps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
