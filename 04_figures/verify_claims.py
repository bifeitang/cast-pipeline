#!/usr/bin/env python3
"""Re-derive every machine-checkable number in both manuscripts from its source data
and assert the papers actually say it. Exits non-zero on any mismatch.

WHY THIS EXISTS
---------------
Numbers in these papers live in five places at once -- abstract, Results, Discussion,
figure captions, tables -- with no mechanical link back to the data. Manual verification
has failed repeatedly and in ways careful reading does not catch:

  * the abstract carried p=7e-4 through THREE separate passes over the body text and was
    only caught while editing keywords;
  * "r ~ 0" between fractal dimension and interface error was asserted in three places
    and was never true (it was r=+0.54, p=0.033 even pre-rebuild);
  * the cross-sex n was corrected in four places on 2026-07-27 and left stale in a fifth
    (tab:analysis-cohorts), by the same person who had just corrected the other four;
  * the descriptor says 1.12 mm in one place and ~1.10 mm in another for one quantity.

So: not another read-through. Run this before every submission and after every edit that
touches a number.

USAGE
    python verify_claims.py               # check both papers
    python verify_claims.py --verbose     # also print every value that matched

EXIT CODES
    0  every derived value was found in the paper that should carry it
    1  at least one MISMATCH (a paper states something the data does not support)
    2  a source file is missing or unreadable -- cannot verify, treat as failure

WHAT IT DOES NOT COVER
    Values that are editorial (inclusion criteria), external citations, or that come from
    HPC state not mirrored locally (Slurm accounting, as-run resource requests). Those are
    recorded in 04_Reports_and_Planning/PROVENANCE.tsv with a verdict instead, and are
    listed as UNCHECKABLE below so the gap is visible rather than silent.
"""
from __future__ import annotations
import json, glob, os, re, sys, csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OVERLEAF = os.path.join(os.path.dirname(ROOT), "overleaf")
MANUSCRIPT = os.path.join(OVERLEAF, "cast-manuscript", "manuscript.tex")
DESCRIPTOR = os.path.join(OVERLEAF, "cast-descriptor", "data_descriptor.tex")

VERBOSE = "--verbose" in sys.argv
results: list[tuple[str, str, str, str]] = []   # (status, paper, claim, detail)


# ---------------------------------------------------------------- tex handling ------
def load_tex(path: str) -> str:
    """Return the tex with comment-only lines and trailing % comments stripped, so a
    number that survives only inside a commented-out block is NOT treated as claimed."""
    if not os.path.exists(path):
        print(f"FATAL: {path} not found", file=sys.stderr)
        sys.exit(2)
    out = []
    for line in open(path, encoding="utf-8"):
        if line.lstrip().startswith("%"):
            continue
        out.append(re.sub(r"(?<!\\)%.*$", "", line))
    return "\n".join(out)


def norm(text: str) -> str:
    """Collapse LaTeX number formatting so 1{,}272 and 1,272 compare equal."""
    return text.replace("{,}", ",").replace("\\,", " ").replace("$", "")


def states(tex: str, *variants: str) -> bool:
    """True if the paper contains any spelling of the value."""
    n = norm(tex)
    return any(v in n for v in variants)


def check(paper: str, tex: str, claim: str, *variants: str, detail: str = "") -> None:
    ok = states(tex, *variants)
    results.append(("OK" if ok else "MISMATCH", paper, claim,
                    detail or f"expected one of: {', '.join(variants)}"))


def unchecked(paper: str, claim: str, why: str) -> None:
    results.append(("UNCHECKABLE", paper, claim, why))


def src(rel: str) -> str:
    """Absolute path to a required source file; abort if it is not there."""
    p = os.path.join(HERE, rel)
    if not os.path.exists(p):
        print(f"FATAL: source missing: {rel}", file=sys.stderr)
        sys.exit(2)
    return p


def srcs(rel: str, expect: int | None = None) -> list[str]:
    """Expand a required glob; abort if it matches nothing, or the wrong count."""
    hits = sorted(glob.glob(os.path.join(HERE, rel)))
    if not hits:
        print(f"FATAL: source glob matched nothing: {rel}", file=sys.stderr)
        sys.exit(2)
    if expect is not None and len(hits) != expect:
        print(f"FATAL: {rel} matched {len(hits)} files, expected {expect}", file=sys.stderr)
        sys.exit(2)
    return hits


# ---------------------------------------------------------------- derivations -------
def validity():
    """Gray-white interface validity from the per-stratum heatmap summaries."""
    vals, ns, signed = {}, {}, {}
    for f in srcs("sweep_aggregate/heatmaps/*_summary.json", expect=16):
        name = os.path.basename(f).replace("_summary.json", "")
        d = json.load(open(f))
        vals[name] = d["cortical"]["mean_abs_err_mm"]
        ns[name] = d["n_subjects"]
        signed[name] = d["cortical"]["mean_signed_err_mm"]
    v = np.array(list(vals.values()))
    w = np.array([ns[k] for k in vals])
    # The papers say "across all 16 age-sex strata, the mean cortical interface error was
    # 1.12 mm" -- that is the UNWEIGHTED mean of the 16 per-stratum means (1.1157), not the
    # subject-weighted mean (1.1138, which rounds to 1.11). Both are defensible summaries;
    # the papers consistently use the stratum-level one, so that is what is checked. Do not
    # "fix" this to the weighted mean without also changing both papers.
    return dict(
        n_strata=len(v), n_subjects=int(w.sum()),
        pooled=float(v.mean()),
        pooled_weighted=float(np.average(v, weights=w)),
        lo=float(v.min()), hi=float(v.max()),
        hi_excl=float(np.sort(v)[-2]),
        a11f=vals["age11_female"], a11f_n=ns["age11_female"],
        signed_lo=float(min(signed.values())), signed_hi=float(max(signed.values())),
        signed_a7m=signed["age7_male"], signed_a9f=signed["age9_female"],
        n_a7m=ns["age7_male"], n_a9f=ns["age9_female"],
    )


def crosssex():
    """Cross-sex penalty, cortical MEAN, two-sided Wilcoxon (the metric the figure plots)."""
    from scipy import stats
    rows = [json.loads(l) for l in open(src("sweep_aggregate/sweep_measures.jsonl")) if l.strip()]
    ma, xa = {}, {}
    for r in rows:
        (ma if r["kind"] == "matched_affine" else xa if r["kind"] == "cross_affine" else {})[
            r.get("subject_id")] = r
    ids = [e for e in ma if e in xa]
    M = "cort_mean_mm"
    out = {"n_paired": len(ids)}
    for sx in ("female", "male"):
        d = np.array([xa[e][M] - ma[e][M] for e in ids if ma[e]["template_sex"] == sx])
        out[f"{sx}_n"] = len(d)
        out[f"{sx}_mean"] = float(d.mean())
        out[f"{sx}_p"] = float(stats.wilcoxon(d)[1])
        out[f"{sx}_wins"] = int((d > 0).sum())
    ef, em = [], []
    for e in ids:
        if ma[e]["template_sex"] == "female":
            ef.append(ma[e][M]); em.append(xa[e][M])
        else:
            em.append(ma[e][M]); ef.append(xa[e][M])
    out["easier"] = float((np.array(em) - np.array(ef)).mean())
    return out


def assd():
    """BRAIN CAST vs NKI, grid-matched 0.8 mm."""
    rows = [json.loads(l) for l in open(src("refbench/assd_0p8_measures.jsonl")) if l.strip()]
    by: dict = {}
    for r in rows:
        by.setdefault(r["subject_id"], {})[r["reference"]] = r
    P = [v for v in by.values() if "CAST_0.8" in v and "NKI_0.8" in v]
    d = lambda f: np.array([v["CAST_0.8"][f] - v["NKI_0.8"][f] for v in P])
    rev = d("rev_mean_mm")
    return dict(
        n=len(P),
        fwd=float(np.median(d("fwd_mean_cort_mm"))),
        rev=float(np.median(rev)),
        sym=float(np.median(d("assd_mm"))),
        sym_med_based=float(np.median(d("assd_median_mm"))),
        rev_wins=int((rev < 0).sum()),
        full_delta=float(np.median(d("full_median_mm"))),
        cort_delta=float(np.median(d("cort_median_mm"))),
        cast_full=float(np.median([v["CAST_0.8"]["full_median_mm"] for v in P])),
        cast_cort=float(np.median([v["CAST_0.8"]["cort_median_mm"] for v in P])),
        nki_full=float(np.median([v["NKI_0.8"]["full_median_mm"] for v in P])),
        nki_cort=float(np.median([v["NKI_0.8"]["cort_median_mm"] for v in P])),
    )


def tissue_jac():
    rows = [json.load(open(f)) for f in srcs("sweep_aggregate/tissue_jac/*.json", expect=81)]
    out = {"n": len(rows), "nondiffeo": 0, "measurements": 3 * len(rows)}
    for t in ("gm", "wm", "csf"):
        out[f"{t}_mean"] = float(np.mean([r[t]["mean_logJ"] for r in rows]))
        out[f"{t}_sd"] = float(np.mean([r[t]["std_logJ"] for r in rows]))
        out["nondiffeo"] += int(sum(r[t]["pct_nondiffeo"] > 0 for r in rows))
    return out


def morphometry():
    """Age correlations and the FD-vs-validity association."""
    from scipy import stats
    rows = [json.loads(l) for l in open(src("morphometry/template_morphometry.jsonl")) if l.strip()]
    for r in rows:
        m = re.match(r"age(\d+)_(\w+)", r["name"])
        r["age"], r["sex"] = int(m.group(1)), m.group(2)
    out = {"n_strata": len(rows)}
    ages = np.array([r["age"] for r in rows])
    for k in ("fd", "wm_ml", "gm_ml", "icv_ml"):
        v = np.array([r[k] for r in rows], dtype=float)
        ok = np.isfinite(v)
        out[f"r_{k}"] = float(np.corrcoef(ages[ok], v[ok])[0, 1])
    for k in ("wm_ml", "gm_ml", "icv_ml"):
        mm = np.mean([r[k] for r in rows if r["sex"] == "male"])
        ff = np.mean([r[k] for r in rows if r["sex"] == "female"])
        out[f"dimorph_{k}"] = float(100 * (mm - ff) / ff)
    # FD vs interface error, the claim that was wrong for months
    tpl = {r["name"]: r for r in rows}
    fd, err = [], []
    for f in srcs("sweep_aggregate/heatmaps/*_summary.json", expect=16):
        name = os.path.basename(f).replace("_summary.json", "")
        if name in tpl:
            fd.append(tpl[name]["fd"])
            err.append(json.load(open(f))["cortical"]["mean_abs_err_mm"])
    r, p = stats.pearsonr(fd, err)
    rho, prho = stats.spearmanr(fd, err)
    out.update(fd_r=float(r), fd_p=float(p), fd_rho=float(rho), fd_prho=float(prho),
               fd_n=len(fd))
    return out


def cohorts():
    """Row counts that appear in tab:analysis-cohorts."""
    out = {}
    roster = src("morphometry/roster_tissue_volumes.tsv")
    out["construction"] = sum(1 for _ in open(roster)) - 1
    allcsv = src("morphometry/tissue_volumes_all.csv")
    out["growth_norms"] = sum(1 for _ in open(allcsv)) - 1
    return out


VOXEL_MM = 0.8   # acquisition voxel; the yardstick every deformation-cost claim is scaled to


def deform():
    """Deformation cost from the intensity rerun -- the numbers this file previously had
    NO assertions on, which is how a whole section stayed on mask-era values.

    AGE CONVENTION: |dage| uses the subject's CONTINUOUS age, matching both the paper's
    "|dage| < 0.5 y" wording and make_figure_F2_agexage_clean.py. analyze_dc_intensity.py
    bins subject age to its integer directory bin and therefore reports 2.399/2.425 and
    +0.024 mm/yr instead of 2.404/2.432 and +0.025. Neither changes a conclusion, but they
    are different conventions and must not be mixed: on the mask-era data the float
    convention reproduces the published 3.08/3.63/+0.10 exactly, the integer one gives
    3.02/3.50/+0.067. If you switch conventions, switch the figure and the text with it.
    """
    from scipy import stats
    rows = list(csv.DictReader(open(src(
        "DeformationAnalysis/test_set_on_template_metrics_INTENSITY.csv"))))
    cast = [r for r in rows if r["arm"] == "cast"]
    nki = [r for r in rows if r["arm"] == "nki"]
    if any(r["disp_component"] != "syn" for r in rows):
        print("FATAL: intensity table contains non-SyN displacement rows", file=sys.stderr)
        sys.exit(2)
    d = np.array([abs(float(r["template_age"]) - float(r["Age"])) for r in cast])
    v = np.array([float(r["mean_disp_mm"]) for r in cast])
    near, far = v[d < 0.5], v[d >= 2]
    lr = stats.linregress(d, v)
    out = dict(
        n_cast=len(cast), n_nki=len(nki),
        n_subj=len({r["subject_id"] for r in cast}),
        sd=float(v.std()),
        near=float(np.median(near)), far=float(np.median(far)),
        n_near=len(near), n_far=len(far),
        eff=float(np.median(far) - np.median(near)),
        eff_p=float(stats.mannwhitneyu(near, far)[1]),
        slope=float(lr.slope), r=float(lr.rvalue), slope_p=float(lr.pvalue),
        cast_med=float(np.median(v)),
        nki_med=float(np.median([float(r["mean_disp_mm"]) for r in nki])),
    )
    out["eff_vox"] = abs(out["eff"]) / VOXEL_MM * 100
    out["eff_sd"] = abs(out["eff"]) / out["sd"]
    out["four_yr"] = abs(out["slope"]) * 4
    # paired CAST-NKI on the subjects present in both arms
    pc, pn = {}, {}
    for r in cast:
        pc.setdefault(r["subject_id"], []).append(float(r["mean_disp_mm"]))
    for r in nki:
        pn.setdefault(r["subject_id"], []).append(float(r["mean_disp_mm"]))
    both = sorted(set(pc) & set(pn))
    a = np.array([np.mean(pc[e]) for e in both])
    b = np.array([np.mean(pn[e]) for e in both])
    out["paired_n"] = len(both)
    out["paired_diff"] = float((a - b).mean())
    out["paired_vox"] = abs(out["paired_diff"]) / VOXEL_MM * 100
    # signed-curve minimum: the paper used to claim the matched age was cheapest. It is not,
    # and it was not on the mask data either. Assert the claim is ABSENT, not the value.
    sd_ = np.array([float(r["template_age"]) - float(r["Age"]) for r in cast])
    binned = {}
    for lo in np.arange(-6.5, 6.5, 1):
        m = (sd_ >= lo) & (sd_ < lo + 1)
        if m.sum() >= 10:
            binned[lo + 0.5] = float(np.median(v[m]))
    out["argmin_bin"] = min(binned, key=binned.get)
    out["span"] = max(binned.values()) - min(binned.values())
    out["span_vox"] = out["span"] / VOXEL_MM * 100
    return out


def deform_model():
    """Refit coefficients, read from the JSON that fit_dc_mixed_model.py writes.

    Kept as a file rather than refitted here so verify_claims.py does not require
    statsmodels; if the JSON is missing the caller reports it as uncheckable instead of
    silently skipping. Regenerate with:
        python fit_dc_mixed_model.py --json
    """
    p = os.path.join(HERE, "dc_mixed_model_intensity.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))["primary"]


def age9_jac():
    """Composed-Jacobian summary behind the supplementary age-nine figure."""
    rows = list(csv.DictReader(open(src(
        "DeformationAnalysis/tables/age9_jacobian_summary_by_age_gender_INTENSITY.csv"))))
    n = np.array([int(r["n"]) for r in rows])
    mj = np.array([float(r["mean_mean_logJ"]) for r in rows])
    sj = np.array([float(r["mean_std_logJ"]) for r in rows])
    fem = np.mean([float(r["mean_mean_logJ"]) for r in rows
                   if r["template_gender"] == "female"])
    mal = np.mean([float(r["mean_mean_logJ"]) for r in rows
                   if r["template_gender"] == "male"])
    morph = {r["name"]: r for r in
             (json.loads(l) for l in open(src("morphometry/template_morphometry.jsonl"))
              if l.strip())}
    return dict(
        n=int(n.sum()), pooled=float(np.average(mj, weights=n)),
        sd_lo=float(sj.min()), sd_hi=float(sj.max()),
        sd_min_age=min({int(r["Age"]) for r in rows},
                       key=lambda a: np.mean([float(r["mean_std_logJ"]) for r in rows
                                              if int(r["Age"]) == a])),
        gap=float(fem - mal),
        icv_log=float(np.log(morph["age9_male"]["icv_ml"] /
                             morph["age9_female"]["icv_ml"])),
        nondiffeo=float(max(float(r["mean_pct_non_diff"]) for r in rows)),
    )


def affine_component():
    """The affine's contribution, from the dedicated both-components re-registration.

    Replaces the mask-era "translation artifact" panel. Its claim of a CONSTANT ~32 mm
    offset inflating the cost ~11x does not survive: measured, the affine adds a median
    4.23 mm with CV 0.58 over a 0.6-22.9 mm range. Only the "independent of age" half of
    the old claim held. Assertions below cover both the values and the absence of the
    withdrawn constant-offset language.
    """
    from scipy import stats
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "dc_translation", "**", "metrics.txt"),
                              recursive=True)):
        parts = p.split(os.sep)
        r = list(csv.DictReader(open(p), delimiter="\t"))[0]
        if "mean_disp_total_mm" not in r or r.get("disp_component") != "syn":
            continue
        rows.append((int(parts[-3]), float(r["mean_disp_mm"]),
                     float(r["mean_disp_total_mm"])))
    if not rows:
        return None
    sage = np.array([r[0] for r in rows], dtype=float)
    c = np.array([r[1] for r in rows])
    t = np.array([r[2] for r in rows])
    off = t - c
    lr = stats.linregress(sage, off)
    return dict(n=len(rows), clean=float(np.median(c)), total=float(np.median(t)),
                ratio=float(np.median(t) / np.median(c)),
                off_med=float(np.median(off)), off_lo=float(off.min()),
                off_hi=float(off.max()), cv=float(off.std() / off.mean()),
                r=float(np.corrcoef(c, t)[0, 1]), age_p=float(lr.pvalue),
                age_slope=float(lr.slope))


def deform_delta():
    """Sex-matched advantage at the age-nine templates (supplementary waterfall)."""
    rows = [r for r in csv.DictReader(open(src(
        "DeformationAnalysis/test_set_on_template_metrics_INTENSITY.csv")))
        if r["arm"] == "cast" and r["template_age"] == "9"]
    by: dict = {}
    for r in rows:
        by.setdefault((r["subject_id"], r["Sex_Text"]), {})[r["template_sex"]] = \
            float(r["norm_mean_disp"])
    out = {}
    for sex in ("male", "female"):
        dd = [(v["female"] - v["male"]) if sex == "male" else (v["male"] - v["female"])
              for (e, s), v in by.items() if s == sex and len(v) == 2]
        out[f"{sex}_n"] = len(dd)
        out[f"{sex}_pct"] = 100 * float(np.mean(np.array(dd) > 0))
    return out


# ---------------------------------------------------------------- checks ------------
def run() -> None:
    man = load_tex(MANUSCRIPT)
    des = load_tex(DESCRIPTOR)

    V = validity()
    for paper, tex in (("manuscript", man), ("descriptor", des)):
        check(paper, tex, "validity pooled cortical error", f"{V['pooled']:.2f}",
              detail=f"derived {V['pooled']:.4f} mm (stratum-level) over {V['n_strata']} strata / {V['n_subjects']} subjects; subject-weighted {V['pooled_weighted']:.4f}")
        check(paper, tex, "validity max stratum (age-11 F)", f"{V['a11f']:.2f}",
              detail=f"derived {V['a11f']:.4f} mm, n={V['a11f_n']}")
    check("manuscript", man, "validity range low", f"{V['lo']:.2f}",
          detail=f"derived {V['lo']:.4f}")
    check("manuscript", man, "validity 15-of-16 upper bound", f"{V['hi_excl']:.2f}",
          detail=f"derived {V['hi_excl']:.4f}")
    check("manuscript", man, "n held-out validity subjects", str(V["n_subjects"]),
          detail=f"derived {V['n_subjects']}")
    check("manuscript", man, "signed bias, age-7 male", f"{abs(V['signed_a7m']):.2f}",
          detail=f"derived {V['signed_a7m']:+.4f}")
    check("manuscript", man, "signed bias, age-9 female", f"{abs(V['signed_a9f']):.2f}",
          detail=f"derived {V['signed_a9f']:+.4f}")

    X = crosssex()
    check("manuscript", man, "cross-sex n paired", str(X["n_paired"]),
          detail=f"derived {X['n_paired']}")
    check("manuscript", man, "cross-sex female benefit", f"{X['female_mean']:.3f}",
          detail=f"derived {X['female_mean']:+.4f} mm")
    check("manuscript", man, "cross-sex male reversal", f"{abs(X['male_mean']):.3f}",
          detail=f"derived {X['male_mean']:+.4f} mm")
    check("manuscript", man, "female template easier for everyone", f"{X['easier']:.3f}",
          detail=f"derived {X['easier']:+.4f} mm")
    check("manuscript", man, "cross-sex female win count",
          f"{X['female_wins']}/{X['female_n']}",
          detail=f"derived {X['female_wins']}/{X['female_n']}")
    check("manuscript", man, "cross-sex cohort in tab:analysis-cohorts",
          f"{X['n_paired']} ({X['female_n']} F, {X['male_n']} M)",
          detail="the row that was left stale on 2026-07-27")

    A = assd()
    check("manuscript", man, "ASSD n paired", f"{A['n']} paired", str(A["n"]),
          detail=f"derived {A['n']}")
    check("manuscript", man, "ASSD forward median", f"{A['fwd']:.3f}",
          detail=f"derived {A['fwd']:+.4f}")
    check("manuscript", man, "ASSD reverse median", f"{abs(A['rev']):.3f}",
          detail=f"derived {A['rev']:+.4f}")
    check("manuscript", man, "ASSD symmetric median", f"{abs(A['sym']):.3f}",
          detail=f"derived {A['sym']:+.4f}")
    check("manuscript", man, "ASSD median-based", f"{A['sym_med_based']:.3f}",
          detail=f"derived {A['sym_med_based']:+.4f}")
    check("manuscript", man, "ASSD reverse win count", f"{A['rev_wins']}/{A['n']}",
          detail=f"derived {A['rev_wins']}/{A['n']}")
    check("manuscript", man, "head-to-head table: CAST full", f"{A['cast_full']:.3f}",
          detail=f"derived {A['cast_full']:.4f}")
    check("manuscript", man, "head-to-head table: CAST cortical", f"{A['cast_cort']:.3f}",
          detail=f"derived {A['cast_cort']:.4f}")
    check("manuscript", man, "head-to-head table: NKI full", f"{A['nki_full']:.3f}",
          detail=f"derived {A['nki_full']:.4f}")
    check("manuscript", man, "head-to-head table: NKI cortical", f"{A['nki_cort']:.3f}",
          detail=f"derived {A['nki_cort']:.4f}")

    T = tissue_jac()
    check("manuscript", man, "tissue Jacobian n subjects", str(T["n"]),
          detail=f"derived {T['n']}")
    for t in ("gm", "wm", "csf"):
        check("manuscript", man, f"tissue Jacobian {t.upper()} mean logJ",
              f"{abs(T[f'{t}_mean']):.2f}", detail=f"derived {T[f'{t}_mean']:+.4f}")
        check("manuscript", man, f"tissue Jacobian {t.upper()} SD logJ",
              f"{T[f'{t}_sd']:.2f}", detail=f"derived {T[f'{t}_sd']:.4f}")
    check("manuscript", man, "tissue Jacobian non-diffeomorphic",
          f"{T['nondiffeo']}/{T['measurements']}",
          detail=f"derived {T['nondiffeo']}/{T['measurements']}")

    M = morphometry()
    for k, label in (("fd", "fractal dimension"), ("wm_ml", "WM volume"),
                     ("gm_ml", "GM volume"), ("icv_ml", "ICV")):
        r = M[f"r_{k}"]
        check("manuscript", man, f"age correlation, {label}", f"{abs(r):.2f}",
              detail=f"derived r={r:+.4f}")
    check("manuscript", man, "FD vs interface error (the old 'r~0' claim)",
          f"{M['fd_r']:.2f}",
          detail=f"derived r={M['fd_r']:+.4f}, p={M['fd_p']:.3f}, n={M['fd_n']}")
    if states(man, "r\\approx0", "r \\approx 0", "$r\\approx0$"):
        results.append(("MISMATCH", "manuscript", "FD/error decoupling",
                        f"paper still asserts r~0; measured r={M['fd_r']:+.3f} "
                        f"(p={M['fd_p']:.3f})"))

    C = cohorts()
    for paper, tex in (("manuscript", man), ("descriptor", des)):
        check(paper, tex, "construction cohort", f"{C['construction']:,}",
              detail=f"derived {C['construction']} roster rows")
    check("manuscript", man, "growth-norm cohort", f"{C['growth_norms']:,}",
          detail=f"derived {C['growth_norms']} rows")

    # --- deformation cost, intensity rerun --------------------------------------------
    # None of this was covered before 2026-07-28, which is exactly why the whole section
    # sat on mask-era numbers through several careful read-throughs.
    D = deform()
    check("manuscript", man, "deformation-cost registrations", f"{D['n_cast']:,}",
          detail=f"derived {D['n_cast']} CAST rows, {D['n_subj']} subjects")
    check("manuscript", man, "matched-age median cost", f"{D['near']:.3f}",
          detail=f"derived {D['near']:.4f} mm, n={D['n_near']} (mask era 3.08)")
    check("manuscript", man, "mismatched median cost", f"{D['far']:.3f}",
          detail=f"derived {D['far']:.4f} mm, n={D['n_far']} (mask era 3.63)")
    check("manuscript", man, "age effect", f"{abs(D['eff']):.3f}",
          detail=f"derived {D['eff']:+.4f} mm = {D['eff_vox']:.1f}% of a "
                 f"{VOXEL_MM} mm voxel = {D['eff_sd']:.2f} SD, p={D['eff_p']:.3g}")
    check("manuscript", man, "age effect as voxel fraction", f"{D['eff_vox']:.1f}\\%",
          f"{D['eff_vox']:.1f}%",
          detail="the effect size must appear, not just the p-value")
    check("manuscript", man, "slope on |dage|", f"{D['slope']:.3f}",
          detail=f"derived {D['slope']:+.4f} mm/yr, r={D['r']:+.3f}, "
                 f"p={D['slope_p']:.3g} (mask era +0.10)")
    check("manuscript", man, "between-subject SD", f"{D['sd']:.3f}",
          detail=f"derived {D['sd']:.4f} mm (mask era 3.409)")
    check("manuscript", man, "signed-curve span", f"{D['span']:.3f}",
          detail=f"derived {D['span']:.4f} mm = {D['span_vox']:.0f}% of a voxel")
    check("manuscript", man, "CAST vs NKI, CAST median", f"{D['cast_med']:.2f}",
          detail=f"derived {D['cast_med']:.4f} mm")
    check("manuscript", man, "CAST vs NKI, NKI median", f"{D['nki_med']:.2f}",
          detail=f"derived {D['nki_med']:.4f} mm")
    check("manuscript", man, "CAST-NKI paired difference", f"{abs(D['paired_diff']):.3f}",
          detail=f"derived {D['paired_diff']:+.4f} mm over {D['paired_n']} subjects "
                 f"= {D['paired_vox']:.1f}% of a voxel")
    for paper, tex in (("manuscript", man), ("descriptor", des)):
        check(paper, tex, "deformation slope stated with its voxel fraction",
              f"{D['slope']:.3f}",
              detail=f"derived {D['slope']:+.4f} mm/yr; both papers must carry it")

    # The published text claimed the matched-age template was cheapest. The signed-curve
    # minimum is at -3 y and was at +3 y on the mask data, so the claim was never supported
    # by its own evidence. Assert it has not crept back in.
    if D["argmin_bin"] != 0.0 and states(
            man, "the matched-age template gave the lowest cost",
            "matched-age template gave the lowest",
            "the matched age ($\\Delta=0$) is lowest", "matched age is lowest"):
        results.append(("MISMATCH", "manuscript", "'matched age is cheapest'",
                        f"signed-curve minimum is at {D['argmin_bin']:+.0f} y, not 0; "
                        f"the claim is unsupported on both generations of the data"))

    M = deform_model()
    if M is None:
        unchecked("manuscript", "deformation-cost mixed model",
                  "dc_mixed_model_intensity.json absent; regenerate with "
                  "`python fit_dc_mixed_model.py --json` (needs statsmodels)")
    else:
        check("manuscript", man, "mixed model N", f"{M['n_obs']:,}",
              detail=f"derived {M['n_obs']} registrations / {M['n_groups']} subjects")
        for term, label, dp in (("Age", "b1 subject age", 3),
                                ("template_age", "b2 template age", 3),
                                ("abs_d_age", "b3 age gap", 3),
                                ("sex_match", "b4 sex match", 3)):
            b = M["terms"][term]["beta"]
            check("manuscript", man, f"mixed model {label}", f"{abs(b):.{dp}f}",
                  detail=f"derived {b:+.4f} mm "
                         f"({abs(b) / VOXEL_MM * 100:.1f}% of a voxel), "
                         f"p={M['terms'][term]['p']:.3g}")
        check("manuscript", man, "mixed model subject SD", f"{M['subject_sd']:.3f}",
              detail=f"derived {M['subject_sd']:.4f} mm (mask era 3.05)")
        check("manuscript", man, "mixed model residual SD", f"{M['residual_sd']:.3f}",
              detail=f"derived {M['residual_sd']:.4f} mm (mask era 1.39)")
        check("manuscript", man, "mixed model ICC", f"{M['icc']:.2f}",
              detail=f"derived {M['icc']:.4f} (mask era 0.83)")
        # The mask-era fit found b4 non-significant and the paper said so. It is now
        # significant and tiny. Both halves must be stated or the sentence misleads.
        if M["terms"]["sex_match"]["p"] < 0.05 and states(
                man, "sex matching leave no statistically detectable",
                "age matching and sex matching leave no statistically detectable"):
            results.append(("MISMATCH", "manuscript", "'no detectable sex-match effect'",
                            f"b4 = {M['terms']['sex_match']['beta']:+.4f} mm at "
                            f"p={M['terms']['sex_match']['p']:.2g}; it IS detectable, and "
                            f"the honest claim is that it is immaterial "
                            f"({abs(M['terms']['sex_match']['beta']) / VOXEL_MM * 100:.1f}"
                            f"% of a voxel)"))

    J = age9_jac()
    check("manuscript", man, "age-9 Jacobian registrations", str(J["n"]),
          detail=f"derived {J['n']}")
    check("manuscript", man, "age-9 pooled mean logJ", f"{abs(J['pooled']):.3f}",
          detail=f"derived {J['pooled']:+.4f} COMPOSED affine-then-SyN "
                 f"(published -0.108 was composed AND mask-based)")
    check("manuscript", man, "age-9 SD logJ range",
          f"{J['sd_lo']:.3f}", detail=f"derived {J['sd_lo']:.4f}-{J['sd_hi']:.4f}")
    check("manuscript", man, "age-9 template M/F logJ gap", f"{abs(J['gap']):.3f}",
          detail=f"derived {J['gap']:+.4f}, vs log ICV ratio {J['icv_log']:+.4f} "
                 f"(agree to {abs(J['gap'] - J['icv_log']):.4f}) -- the gap is template "
                 f"size, not warp behaviour")
    if abs(J["gap"] - J["icv_log"]) > 0.02:
        results.append(("MISMATCH", "manuscript", "age-9 logJ gap vs template ICV ratio",
                        f"gap {J['gap']:+.4f} no longer matches log ICV ratio "
                        f"{J['icv_log']:+.4f}; the figure's explanation does not hold"))
    # The -0.108 vs -0.032 comparison crossed Jacobian conventions. Assert it is gone.
    if states(man, "-0.108", "$-0.108$", "\\(-0.108\\)"):
        results.append(("MISMATCH", "manuscript", "stale age-9 Jacobian value",
                        f"paper still states -0.108 (composed, mask-based); "
                        f"the intensity value is {J['pooled']:+.4f}"))

    AC = affine_component()
    if AC is None:
        unchecked("manuscript", "affine-component panel",
                  "dc_translation/ absent; pull with rsync from "
                  "carya:/project/contreras-vidal/Yang/DC_TRANSLATION_2026-07-29/")
    else:
        check("manuscript", man, "affine-component registrations", str(AC["n"]),
              detail=f"derived {AC['n']}")
        check("manuscript", man, "composite median cost", f"{AC['total']:.2f}",
              detail=f"derived {AC['total']:.4f} mm (published 35.3)")
        check("manuscript", man, "composite/SyN ratio", f"{AC['ratio']:.1f}",
              detail=f"derived {AC['ratio']:.3f}x (published ~11x)")
        check("manuscript", man, "affine contribution median", f"{AC['off_med']:.2f}",
              detail=f"derived {AC['off_med']:.4f} mm")
        check("manuscript", man, "affine contribution CV", f"{AC['cv']:.2f}",
              detail=f"derived {AC['cv']:.4f} over {AC['off_lo']:.2f}-{AC['off_hi']:.2f} mm "
                     f"-- this is what refutes 'constant offset'")
        check("manuscript", man, "composite vs SyN correlation", f"{AC['r']:.2f}",
              detail=f"derived r={AC['r']:+.4f}")
        # The SyN median from this independent sample must agree with the main analysis, or
        # the two are measuring different things and one of them is wrong.
        if abs(AC["clean"] - D["cast_med"]) > 0.02:
            results.append(("MISMATCH", "manuscript", "affine panel vs main SyN median",
                            f"panel {AC['clean']:.4f} mm vs main analysis "
                            f"{D['cast_med']:.4f} mm -- independent samples of the same "
                            f"quantity should agree"))
        # The withdrawn claim. "Constant" was the load-bearing word and it is false.
        if states(man, "constant coordinate-origin offset", "near-rigid $\\sim$60",
                  "near-rigid ~60", "inflated $\\sim$11", "inflated ~11"):
            results.append(("MISMATCH", "manuscript", "'constant coordinate-origin offset'",
                            f"the affine contribution has CV {AC['cv']:.2f} over "
                            f"{AC['off_lo']:.2f}-{AC['off_hi']:.2f} mm; it is not constant, "
                            f"and the inflation is {AC['ratio']:.1f}x not ~11x"))

    X9 = deform_delta()
    check("manuscript", man, "sex-matched Delta, male share",
          f"{X9['male_pct']:.0f}\\%", f"{X9['male_pct']:.0f}%",
          detail=f"derived {X9['male_pct']:.1f}% of {X9['male_n']} males "
                 f"(mask era 73%)")
    check("manuscript", man, "sex-matched Delta, female share",
          f"{X9['female_pct']:.0f}\\%", f"{X9['female_pct']:.0f}%",
          detail=f"derived {X9['female_pct']:.1f}% of {X9['female_n']} females "
                 f"(mask era 30%)")

    # Any mask-era deformation number still in either paper is a drift. But a bare "1.39"
    # or "3.05" is a number, not a claim -- the descriptor legitimately carries 1.39 as a
    # CNR quartile bound. Flag a stale value ONLY where it sits next to deformation-cost
    # wording, for the same reason the interface-error check above windows its matches:
    # a check that cries wolf is a check people learn to ignore.
    DEFORM_PHRASE = re.compile(
        r"deformation[- ]cost|deformation cost|mean displacement|"
        r"subject-to-template registrations|mixed[- ]effects model|"
        r"registration cost|displacement metric", re.I)
    STALE = {"3.08": "matched-age cost", "3.63": "mismatched cost",
             "3,175": "registration count", "3.409": "between-subject SD",
             "0.158": "mixed-model b2 (template age)", "3.05": "subject SD",
             "1.39": "residual SD", "0.108": "age-9 composed Jacobian"}
    for paper, tex in (("manuscript", man), ("descriptor", des)):
        n = norm(tex)
        windows = [n[max(0, m.start() - 400): m.end() + 400]
                   for m in DEFORM_PHRASE.finditer(n)]
        for val, what in STALE.items():
            if any(val in w for w in windows):
                results.append(("MISMATCH", paper, f"mask-era value {val} still present",
                                f"{what}; stated near deformation-cost wording but "
                                f"superseded by the intensity rerun"))

    # --- cross-paper consistency -----------------------------------------------------
    shared = re.compile(r"\d+\.\d{2,3}")
    mv = set(shared.findall(norm(man)))
    dv = set(shared.findall(norm(des)))
    both = sorted(mv & dv)
    results.append(("INFO", "both", "values appearing in both papers",
                    f"{len(both)} shared: {' '.join(both[:14])}…"))

    # values that MUST match because they are the same quantity
    for label, variants in (("pooled validity error", (f"{V['pooled']:.2f}",)),
                            ("age-11 F validity", (f"{V['a11f']:.2f}",)),
                            ("construction cohort", (f"{C['construction']:,}",))):
        in_m, in_d = states(man, *variants), states(des, *variants)
        if in_m != in_d:
            results.append(("MISMATCH", "cross-paper", label,
                            f"{variants[0]} present in "
                            f"{'manuscript' if in_m else 'descriptor'} only"))

    # --- contradictions -------------------------------------------------------------
    # A value being PRESENT is not enough: the papers have twice carried two different
    # numbers for one quantity (1.12 vs ~1.10 mm for the interface error). So for the
    # headline quantities, assert that no OTHER value is also stated for the same thing.
    # Only look at numbers sitting next to interface-error wording. A bare "1.XX mm"
    # anywhere is not a conflict -- the manuscript legitimately reports 1.10 mm for the
    # REVERSE-direction distance and 1.39 mm for a mixed-model residual SD, and flagging
    # those would train the reader to ignore this check.
    ERR_PHRASE = re.compile(
        r"(?:gray--white|gray-white|grey--white)\s+interface\s+error|"
        r"interface\s+error\s+(?:was|is|of)", re.I)
    OK_VALUES = {f"{V['pooled']:.2f}", f"{V['a11f']:.2f}",
                 f"{V['lo']:.2f}", f"{V['hi_excl']:.2f}"}
    for paper, tex in (("manuscript", man), ("descriptor", des)):
        n = norm(tex)
        wrong = set()
        for m in ERR_PHRASE.finditer(n):
            window = n[max(0, m.start() - 130): m.end() + 130]
            for val in re.findall(r"(?:approx\s*)?(1\.\d{2})\s*mm", window):
                if val not in OK_VALUES:
                    wrong.add(val)
        if wrong:
            results.append(("MISMATCH", paper, "conflicting interface-error values",
                            f"states {sorted(wrong)} mm next to interface-error wording, "
                            f"alongside the derived {V['pooled']:.2f}; only one can be right"))

    # "the tie holds in every age stratum" -- check it against the per-age bootstrap CIs
    rows = [json.loads(l) for l in open(src("refbench/assd_0p8_measures.jsonl")) if l.strip()]
    by: dict = {}
    for r in rows:
        by.setdefault(r["subject_id"], {})[r["reference"]] = r
    P = [v for v in by.values() if "CAST_0.8" in v and "NKI_0.8" in v]
    sym = np.array([v["CAST_0.8"]["assd_mm"] - v["NKI_0.8"]["assd_mm"] for v in P])
    ages = np.array([v["CAST_0.8"]["template_age"] for v in P])
    rng = np.random.default_rng(0)
    excludes_zero = []
    for a in sorted(set(ages)):
        x = sym[ages == a]
        bs = np.median(rng.choice(x, (5000, len(x)), replace=True), axis=1)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        if lo > 0 or hi < 0:
            excludes_zero.append(f"age {a} [{lo:+.4f},{hi:+.4f}]")
    if excludes_zero and states(man, "every age stratum"):
        results.append(("MISMATCH", "manuscript", "'tie holds in every age stratum'",
                        "contradicted by its own CIs at " + "; ".join(excludes_zero) +
                        " -- both favour BRAIN CAST, so the claim understates the result"))

    # --- gaps we are deliberately not pretending to cover ----------------------------
    unchecked("manuscript", "subject-level SLURM resource request",
              "Slurm accounting only; run: sacct -u yhu30 -S 2024-11-09 -X -o JobName,AllocCPUS,ReqMem "
              "| grep mri-process  (measured modal 48 cores / 32 GB)")
    unchecked("manuscript", "cluster service units",
              "Slurm accounting; measured 575,006 CPU-hours / 70,961 jobs on 2026-07-27. "
              "NOTE 'service unit' may not equal CPU-hour in RCDC accounting")
    # Resolved 2026-07-27 against the as-run code, which is in PediatricMriDB/, NOT in
    # /project/contreras-vidal/Image/ where the audit ledger said to look. Identical in all
    # four step2_uh_ped_temp_preprocess*.sh variants, so there is no ambiguity about which
    # was run:
    #     bg_std=$(fslstats T1 -k outside -s)        # SD of the air region
    #     noise_lvl=$(echo "${bg_std} * 0.01" | bc)  # 1% of BACKGROUND SD
    #     fslmaths outside -mul ${noise_lvl}         # binary mask x scalar => CONSTANT
    # So: not Gaussian, not random, not 1% of in-brain signal, and applied BEYOND the
    # buffer shell rather than inside it (the shell keeps its real T1 intensities).
    # The paper's description was wrong on all three counts and is now corrected.
    if states(man, "Gaussian noise"):
        results.append(("MISMATCH", "manuscript", "background fill described as Gaussian noise",
                        "as-run code applies a CONSTANT (binary mask x scalar) at 1% of the "
                        "background SD; no random values are generated"))
    if states(man, "1\\% of typical in-brain signal", "1% of typical in-brain signal"):
        results.append(("MISMATCH", "manuscript", "background fill amplitude",
                        "as-run scale is 1% of the BACKGROUND standard deviation, "
                        "not 1% of in-brain signal"))
    # Two gaps closed rather than carried:
    #   "F2 clean displacement -- derivation script does not exist" (until 2026-07-28)
    #       -> build_dc_intensity_tables.py, asserted above.
    #   "translation-artifact panel -- composite cost unrecoverable" (until 2026-07-29)
    #       -> cal_deformation_cost.sh now emits the composite from the field the Jacobian
    #          already uses; DC_TRANSLATION_2026-07-29 re-registered 647 pairs and the
    #          panel's numbers are asserted above.
    unchecked("descriptor", "MRIQC pre/post tables",
              "source is mriqc_output/mriqc_prepost_eval on carya, not mirrored locally")

    # --- report ----------------------------------------------------------------------
    order = {"MISMATCH": 0, "UNCHECKABLE": 1, "INFO": 2, "OK": 3}
    results.sort(key=lambda r: (order[r[0]], r[1], r[2]))
    bad = [r for r in results if r[0] == "MISMATCH"]
    width = max(len(r[2]) for r in results) + 2

    print("=" * 100)
    print("CLAIM VERIFICATION -- both papers")
    print("=" * 100)
    for status, paper, claim, detail in results:
        if status == "OK" and not VERBOSE:
            continue
        print(f"{status:<13}{paper:<12}{claim:<{width}}{detail}")
    n_ok = sum(1 for r in results if r[0] == "OK")
    n_un = sum(1 for r in results if r[0] == "UNCHECKABLE")
    print("-" * 100)
    print(f"{n_ok} verified   {len(bad)} MISMATCH   {n_un} uncheckable "
          f"(re-run with --verbose to list the verified ones)")
    if bad:
        print("\nFAILED -- the papers state something the data does not support:")
        for _, paper, claim, detail in bad:
            print(f"  [{paper}] {claim}: {detail}")

    # The provenance inventory is GENERATED, not hand-maintained -- a hand-maintained one
    # would drift exactly like the numbers it is supposed to police.
    if "--tsv" in sys.argv:
        out = os.path.join(ROOT, "04_Reports_and_Planning", "PROVENANCE.tsv")
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["status", "paper", "claim", "detail"])
            w.writerows(results)
        print(f"\nwrote {out}  ({len(results)} rows)")

    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    run()
