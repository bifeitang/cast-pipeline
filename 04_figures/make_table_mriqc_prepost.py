#!/usr/bin/env python3
"""Descriptor Tables 2 and 3 -- MRIQC coverage and pre/post image-quality metrics.

WHY THIS EXISTS. Both tables were hand-maintained, and between them they described two
DIFFERENT studies without saying so:

  Study 1  age-9 pre/post assessment of preprocessing effectiveness. This is why age 9
           alone has a `post-brain` report and why its counts (266 pre / 260 post) dwarf
           the others.
  Study 2  an exploratory pilot testing whether MRIQC could drive image inclusion/
           exclusion. Its analysis directory (analysis/out_20260112_162209) is MALE-ONLY
           and covers neither age 8 nor age 9.

The published coverage table's "Post n" column mixed the two: ages 5, 6, 7, 11-17 carried
study 2's paired male-only n (49, 3, 8, 1, 18, 23, 2, 15, 24, 40 -- all reproduced exactly
from that directory), while ages 9, 10 and 18 carried raw group-report counts, and age 8
matched neither. Meanwhile the metrics table was computed on ALL subjects, not males only
(its published CNR-pre range 1.00-1.39 matches the all-subjects computation exactly and
not the male-only one, 0.92-1.33). So the n a reader saw did not describe the population
the metrics came from.

This script emits both tables from ONE population -- every MRIQC group report, both sexes,
as written by the pipeline -- so the coverage counts and the metric medians finally
describe the same thing and both are reproducible.

Source: sweep of mriqc_prepost_eval/Age{5..18}/{pre,post-*}/group_T1w.tsv, pulled from
        carya 2026-07-27. Age 9's post stage is `post-brain`; every other age is
        `post-csfNorm_rc`, which is the pipeline's own convention and is stated in the
        caption rather than silently applied.

The study-2 pilot is deliberately NOT folded in here. It is a different question on a
different population and belongs in its own sentence, not in a column that looks like
coverage.

Usage:  python make_table_mriqc_prepost.py [--latex]
"""
import csv, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "mriqc_prepost")
AGES = list(range(5, 19))
POST_STAGE = {9: "post-brain"}          # every other age uses post-csfNorm_rc
DEFAULT_POST = "post-csfNorm_rc"

# (column key in group_T1w.tsv, printed label, higher-is-better?)
METRICS = [
    ("cnr",       "CNR",       True),
    ("cjv",       "CJV",       False),
    ("inu_range", "INU range", False),
    ("fwhm_avg",  "FWHM avg",  False),
    ("snr_total", "SNR total", True),
    ("wm2max",    "WM2max",    True),
]


def load(age: int, stage: str):
    p = os.path.join(ROOT, f"Age{age}", stage, "group_T1w.tsv")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def post_stage(age: int) -> str:
    return POST_STAGE.get(age, DEFAULT_POST)


def main() -> int:
    coverage, pre_meds, post_meds = [], {k: [] for k, _, _ in METRICS}, {k: [] for k, _, _ in METRICS}
    missing = []
    for age in AGES:
        pre, post = load(age, "pre"), load(age, post_stage(age))
        if pre is None or post is None:
            missing.append(age)
            continue
        coverage.append((age, len(pre), len(post), post_stage(age)))
        for key, _, _ in METRICS:
            for rows, acc in ((pre, pre_meds), (post, post_meds)):
                vals = [float(r[key]) for r in rows
                        if r.get(key) not in (None, "", "n/a")]
                if vals:
                    acc[key].append(float(np.median(vals)))
    if missing:
        print(f"WARNING: no group report for ages {missing}", file=sys.stderr)

    def cell(vals):
        return f"{np.median(vals):.2f} ({min(vals):.2f}--{max(vals):.2f})"

    if "--latex" in sys.argv:
        print("% coverage")
        for age, npre, npost, stage in coverage:
            print(f"{age:<2} & {npre:>3} & {npost:>3} & \\texttt{{{stage.replace('_', chr(92) + '_')}}} \\\\")
        print("% metrics")
        for key, label, up in METRICS:
            arrow = "\\uparrow" if up else "\\downarrow"
            print(f"{label:<9} & ${arrow}$ & {cell(pre_meds[key])} & {cell(post_meds[key])} \\\\")
        return 0

    print(f"MRIQC group-report coverage  (n ages = {len(coverage)}, both sexes)")
    print(f"{'age':>4}{'pre n':>8}{'post n':>8}   post stage")
    tot_pre = tot_post = 0
    for age, npre, npost, stage in coverage:
        tot_pre += npre; tot_post += npost
        print(f"{age:>4}{npre:>8}{npost:>8}   {stage}")
    print(f"{'all':>4}{tot_pre:>8}{tot_post:>8}")
    print()
    print("Median of age-level medians (range across age-level medians)")
    print(f"{'metric':<11}{'dir':<5}{'pre':<22}{'post':<22}{'direction ok?'}")
    for key, label, up in METRICS:
        a, b = pre_meds[key], post_meds[key]
        moved = np.median(b) - np.median(a)
        ok = "yes" if (moved > 0) == up else "NO"
        print(f"{label:<11}{'up' if up else 'down':<5}{cell(a):<22}{cell(b):<22}{ok}")
    print("\nSNR moves against its preferred direction by construction: the pipeline keeps a")
    print("non-zero synthetic background floor, which depresses SNR-type metrics. Stated in")
    print("the descriptor text rather than silently omitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
