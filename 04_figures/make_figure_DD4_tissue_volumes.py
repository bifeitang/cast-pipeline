#!/usr/bin/env python3
"""Data-descriptor Figure 4 -- developmental tissue-volume norms of the CAST cohorts.

Third of the hand-made descriptor figures with no generator in this repository. This is it.

WHAT THIS FIGURE ACTUALLY PLOTS -- read before editing the caption. It is *not* the
per-template construction rosters of Table 1. It is the quality-screened subject pool
carried through the subject pipeline, binned to the NEAREST year of age:

    tissue_volume_results/summary/tissue_volumes_all.csv

Two independent checks pin this down. Binning by ROUNDED age reproduces the published
legend's per-year counts exactly (male n=16-126, female n=7-88), where binning by
TRUNCATED age does not (it empties ages 11 and 16 and gives a male maximum of 135); and
it reproduces all four published slope annotations exactly -- brain M +9.1 / F +2.8,
GM M +0.5 / F -3.1, WM M +8.1 / F +5.4, CSF M +0.5 / F +0.4 mL per year.

Consequence worth knowing: none of the 52 subjects of the 2026-07 age-11-female template
rebuild appear in this file, and its age-11-female bin is 25 subjects whose own recorded
age rounds to 11. The figure is therefore NOT affected by that rebuild.

Style reproduces the published PNG (1581x1104): 2x2 panels, seaborn-deep blue/red rather
than the project's Okabe palette, mean with a 95% CI band per age-sex bin, per-sex OLS
slope annotated top-left, and a legend carrying the per-year n range.

TWO MODES
  default   plot the screened subject pool described above, binned by each subject's own
            rounded age. This is what the figure showed historically.
  --roster  plot the per-template CONSTRUCTION rosters instead: one row per contributing
            subject, binned by the stratum it actually built. This is the cohort the
            caption originally claimed, it matches Table 1, and unlike the pool it does
            respond to template rebuilds. Input is the TSV from
            morphometry/build_roster_tissue_volumes.py.

Both inputs carry FreeSurfer aseg volumes via mri_segstats. FSL FAST volumes are a
different measurement and must not be substituted into either.

Usage:  make_figure_DD4_tissue_volumes.py <input> <out.png> [--roster]
"""
import csv
import collections
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AGES = list(range(5, 19))
MALE, FEMALE = "#4C72B0", "#C44E52"
PANELS = [("icv_ml", "Brain volume (WM+GM+CSF, segmented)"),
          ("gm_ml", "Gray matter"),
          ("wm_ml", "White matter"),
          ("csf_ml", "CSF (segmented compartment)")]
FIG_W, FIG_H, DPI = 1581, 1104, 150


def load(path, roster=False):
    """bin[(age, sex)] -> list of row dicts.

    pool mode   : bin by the subject's own age, rounded to the nearest year
    roster mode : bin by the stratum the subject contributed to (no rounding involved)
    """
    out = collections.defaultdict(list)
    delim = "\t" if roster else ","
    with open(path) as f:
        for r in csv.DictReader(f, delimiter=delim):
            try:
                a = int(r["age"]) if roster else round(float(r["age"]))
            except (TypeError, ValueError, KeyError):
                continue
            if a in AGES and r.get("sex") in ("male", "female"):
                out[(a, r["sex"])].append(r)
    return out


def series(bins, sex, field):
    """returns age, mean, half-width of the 95% CI, and n per bin"""
    ages, mean, half, ns = [], [], [], []
    for a in AGES:
        rows = bins.get((a, sex), [])
        v = [float(r[field]) for r in rows if r.get(field)]
        if not v:
            continue
        v = np.asarray(v)
        ages.append(a)
        mean.append(v.mean())
        ns.append(v.size)
        half.append(1.96 * v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0)
    return np.array(ages), np.array(mean), np.array(half), ns


def slope(x, y):
    """OLS slope of the per-year means, in mL/year -- what the annotation reports"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    roster = "--roster" in sys.argv
    if len(argv) < 2:
        raise SystemExit(__doc__)
    bins = load(argv[0], roster=roster)
    if not bins:
        raise SystemExit("no usable rows -- check the CSV path and its age/sex columns")

    counts = {s: [len(bins.get((a, s), [])) for a in AGES if bins.get((a, s))]
              for s in ("male", "female")}
    total = sum(len(v) for v in bins.values())
    print("mode: %s" % ("construction rosters" if roster else "screened subject pool"))
    print("subjects plotted: %d in %d age-sex bins" % (total, len(bins)))
    for s in ("male", "female"):
        print("  %-7s n per year %d-%d" % (s, min(counts[s]), max(counts[s])))

    fig, axes = plt.subplots(2, 2, figsize=(FIG_W / DPI, FIG_H / DPI), dpi=DPI)
    for ax, (field, title) in zip(axes.ravel(), PANELS):
        for sex, colour, tag in (("male", MALE, "M"), ("female", FEMALE, "F")):
            a, m, h, _ = series(bins, sex, field)
            ax.fill_between(a, m - h, m + h, color=colour, alpha=0.18, lw=0)
            ax.plot(a, m, "-o", color=colour, ms=5, lw=1.6,
                    label="%s (n=%d–%d/yr)" % (sex, min(counts[sex]), max(counts[sex])))
            # slope annotations carry a translucent backing: on the roster cohorts the
            # series sit high enough in the gray-matter panel that bare text lands on the
            # male band and becomes unreadable.
            ax.text(0.03, 0.955 if tag == "M" else 0.875, "%s: %+.1f mL/yr" % (tag, slope(a, m)),
                    transform=ax.transAxes, color=colour, fontsize=10, fontweight="bold",
                    va="top", ha="left", zorder=5,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.72,
                              boxstyle="round,pad=0.18"))
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("age (years)", fontsize=10)
        ax.set_ylabel("volume (mL)", fontsize=10)
        ax.grid(True, color="0.9", lw=0.7)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.legend(fontsize=8.5, loc="lower right", framealpha=0.9)
    fig.suptitle("Developmental tissue-volume norms of the CAST %s "
                 "(per-subject mean ± 95%% CI)"
                 % ("construction cohorts" if roster else "cohorts"),
                 fontsize=13.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    fig.savefig(argv[1], dpi=DPI, facecolor="white")
    print("wrote", argv[1])


if __name__ == "__main__":
    main()
