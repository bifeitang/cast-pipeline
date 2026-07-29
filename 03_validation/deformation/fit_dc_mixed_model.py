#!/usr/bin/env python3
"""Refit the deformation-cost linear mixed-effects model on the intensity rerun.

The coefficients in the manuscript are mask-era: they were fitted on registrations that
put a BINARY BRAIN MASK against a greyscale template, which is an ill-posed problem for a
cross-correlation metric (see 04_Reports_and_Planning/DEFORMATION_COST_MASK_ERROR_2026-07-28
.md). This refits the same model, unchanged in specification, on the 3,190 registrations
that used the correct CSF-normalised intensity images.

MODEL -- exactly Eq. (deformation_cost_mixed_effects) as the paper states it:

    D_ij = b0 + b1*Age_i + b2*Age_j + b3*|Age_i - Age_j|
              + b4*SexMatch_ij + b5*SubjectSex_i + u_i + e_ij

    response      mean_disp_mm, the brain-masked mean displacement of the SyN field (mm)
    random        per-subject intercept u_i
    estimator     REML
    cohort        the sex-specific BRAIN CAST templates only. The sex-neutral NKI
                  reference has no template sex, so SexMatch is undefined for it and
                  pooling it would confound template source with sex matching. The paper
                  reports that pooled fit separately as a robustness check, so this
                  script produces it too, and labels it as confounded.

    SubjectSex_i is coded male=1 so b5 reads "relative to female subjects", matching the
    manuscript's "b5 = ... for male subjects".

VARIANCE COMPONENTS -- the easy thing to get backwards
    statsmodels exposes both `cov_re` (random-effect covariance in the RESPONSE's units)
    and `cov_re_unscaled` (the same thing divided by the residual variance, because the
    optimiser profiles out scale). The subject SD is sqrt(cov_re); multiplying by scale
    first is wrong and collapses the ICC from 0.94 to 0.15. The check that settles it:
    sqrt(cov_re) must land on the raw between-subject SD of the per-subject means, which
    is 0.4131 mm here. This script asserts that agreement rather than trusting the label.

USAGE
    python fit_dc_mixed_model.py            # needs statsmodels
    python fit_dc_mixed_model.py --json     # also write dc_mixed_model_intensity.json
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "DeformationAnalysis",
                   "test_set_on_template_metrics_INTENSITY.csv")
OUT = os.path.join(HERE, "dc_mixed_model_intensity.json")

FORMULA = ("mean_disp_mm ~ Age + template_age + abs_d_age + sex_match + subject_male")
TERMS = {"Intercept": "b0 intercept",
         "Age": "b1 subject age",
         "template_age": "b2 template age",
         "abs_d_age": "b3 |subject - template age|",
         "sex_match": "b4 sex match",
         "subject_male": "b5 subject sex (male)"}


def fit(df: pd.DataFrame, label: str) -> dict:
    m = smf.mixedlm(FORMULA, data=df, groups=df["subject_id"])
    res = m.fit(method="lbfgs", reml=True, maxiter=500)
    ci = res.conf_int()
    resid_var = float(res.scale)
    subj_var = float(np.asarray(res.cov_re).squeeze())   # already in response units
    icc = subj_var / (subj_var + resid_var)
    # Guard the scaling rather than trusting it: the fitted subject SD must agree with the
    # raw SD of the per-subject means. If a statsmodels release changes what cov_re means,
    # this fails loudly instead of silently rewriting the ICC.
    raw_between = float(df.groupby("subject_id")["mean_disp_mm"].mean().std(ddof=0))
    if not np.isclose(np.sqrt(subj_var), raw_between, rtol=0.10):
        sys.exit(f"FATAL: subject SD {np.sqrt(subj_var):.4f} disagrees with the raw "
                 f"between-subject SD {raw_between:.4f} -- check cov_re scaling")
    out = {"label": label, "n_obs": int(res.nobs),
           "n_groups": int(df["subject_id"].nunique()),
           "subject_sd": float(np.sqrt(subj_var)),
           "residual_sd": float(np.sqrt(resid_var)), "icc": float(icc), "terms": {}}
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
    print(f"  N = {out['n_obs']:,} registrations across {out['n_groups']} subjects   (REML)")
    for term, desc in TERMS.items():
        if term not in res.params.index:
            continue
        b, p = float(res.params[term]), float(res.pvalues[term])
        lo, hi = float(ci.loc[term, 0]), float(ci.loc[term, 1])
        out["terms"][term] = dict(beta=b, ci_low=lo, ci_high=hi, p=p, desc=desc)
        print(f"  {desc:<32} {b:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  p = {p:.3g}")
    print(f"  {'subject SD':<32} {out['subject_sd']:.4f} mm")
    print(f"  {'residual SD':<32} {out['residual_sd']:.4f} mm")
    print(f"  {'intraclass correlation':<32} {out['icc']:.4f}")
    return out


def main() -> int:
    df = pd.read_csv(CSV)
    df["subject_male"] = (df["Sex_Text"] == "male").astype(int)

    cast = df[df["arm"] == "cast"].copy()
    cast["sex_match"] = cast["sex_match"].astype(int)
    primary = fit(cast, "PRIMARY -- BRAIN CAST sex-specific templates only")

    # Robustness fit the paper reports and then sets aside: pooling the sex-neutral NKI
    # reference forces it to be coded a sex NON-match, so any apparent SexMatch effect is
    # partly template source. Reported for continuity, not as a result.
    pooled = df.copy()
    pooled["sex_match"] = pooled["sex_match"].fillna(0).astype(int)
    robust = fit(pooled, "ROBUSTNESS -- NKI pooled, coded as sex non-matches (CONFOUNDED "
                         "by template source; not a primary result)")

    print(f"\n{'=' * 78}\nmask-era published values, for comparison\n{'=' * 78}")
    for desc, old in (("b1 subject age", "+0.085 [-0.088, 0.257] p=0.34"),
                      ("b2 template age", "+0.158 [0.123, 0.192] p<0.001"),
                      ("b3 |age gap|", "-0.038 [-0.080, 0.004] p=0.075"),
                      ("b4 sex match", "-0.074 [-0.171, 0.023] p=0.13"),
                      ("b5 subject sex (male)", "-0.034 [-0.741, 0.673] p=0.93"),
                      ("subject SD", "3.05 mm"), ("residual SD", "1.39 mm"),
                      ("ICC", "0.83"), ("N", "3,175"),
                      ("pooled-NKI sex match", "-0.148 mm p<1e-3")):
        print(f"  {desc:<26} {old}")

    if "--json" in sys.argv:
        json.dump({"primary": primary, "robustness_nki_pooled": robust},
                  open(OUT, "w"), indent=2)
        print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
