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
    unchecked("manuscript", "F2 clean displacement",
              "mean_disp_mm for age-11 female is 2025-11, measured against a superseded "
              "template; derivation script does not exist")
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
