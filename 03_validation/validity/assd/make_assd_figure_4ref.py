#!/usr/bin/env python3
"""make_assd_figure_4ref.py -- 4-reference head-to-head: direction-of-measurement artifact.

Companion to make_assd_figure.py (the published 2-way CAST-vs-NKI figure built on the
0.8 mm grid, n=144).  This version reads the COMBINED 1.0 mm benchmark file that carries all
four references in one place:

    reference in {CAST (n=209), NKI (n=209), Fonov (n=209), Sanchez (n=189)}

and shows the same Forward / Reverse / Symmetric-ASSD structure for each reference against
CAST, so the "direction decides the winner" story can be read off all four comparators at
once.  Paired difference is CAST - reference (mm); negative => CAST better.

Reading of the story (1.0 mm grid):
  * NKI:     forward favors NKI, reverse favors CAST, symmetric ASSD a near-tie / slight CAST.
  * Fonov:   CAST better in every direction (broad-age reference).
  * Sanchez: forward favors Sanchez, BUT reverse and the fair symmetric ASSD favor CAST
             decisively (189/189) -- the one-directional metric flatters Sanchez exactly the
             way it flattered NKI, yet the symmetric distance is no tie here.

n.b. Sanchez covers ages 5-10 (n=189); CAST/NKI/Fonov cover 5-12 (n=209).  Differing n is
annotated per panel.  Numbers are the database's own WM-derived measures from the jsonl.

Usage: make_assd_figure_4ref.py <assd_1p0_sanchez_measures.jsonl> <out.png>
"""
import sys, json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from collections import defaultdict

np.random.seed(20260615)

meas = sys.argv[1]
outp = sys.argv[2]

recs = [json.loads(l) for l in open(meas) if l.strip()]
by = defaultdict(dict)
for r in recs:
    by[r["subject_id"]][r["reference"]] = r

REFS = ["NKI", "Fonov", "Sanchez"]            # each compared against CAST
REF_TITLE = {"NKI": "NKI", "Fonov": "Fonov / NIHPD", "Sanchez": "Sánchez"}
FIELDS = [("fwd_mean_cort_mm", "Forward\n(tpl→subj)"),
          ("rev_mean_mm",       "Reverse\n(subj→tpl)"),
          ("assd_mm",           "Symmetric\nASSD (fair)")]


def paired(ref, field):
    subs = sorted(s for s in by if ref in by[s] and "CAST" in by[s])
    return np.array([by[s]["CAST"][field] - by[s][ref][field] for s in subs]), len(subs)


# clip y to a common, readable window; outliers beyond are drawn at the edge and counted.
YLO, YHI = -1.35, 0.55

fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.8), sharey=True)

for ax, ref in zip(axes, REFS):
    pos = [0, 1, 2]
    n_used = None
    for x, (fld, _) in zip(pos, FIELDS):
        d, n = paired(ref, fld)
        n_used = n
        jit = np.random.RandomState(x).normal(0, 0.05, len(d))
        col = np.where(d > 0, "#d1495b", "#2e86ab")   # red = ref better, blue = CAST better
        dc = np.clip(d, YLO + 0.02, YHI - 0.02)        # clip for display only
        ax.scatter(np.full(len(d), x) + jit, dc, s=7, c=col, alpha=0.40, lw=0)
        n_below = int(np.sum(d < YLO))                 # CAST-better outliers off the bottom
        if n_below:
            ax.annotate(f"+{n_below} off-scale\n(CAST better)", (x, YLO),
                        textcoords="offset points", xytext=(0, 10), ha="center",
                        va="bottom", fontsize=6.8, color="#2e86ab", style="italic")
        md = float(np.median(d))                       # median computed on UNCLIPPED data
        mdc = float(np.clip(md, YLO + 0.02, YHI - 0.02))
        ax.plot([x - 0.30, x + 0.30], [mdc, mdc], color="k", lw=2.4, zorder=5)
        nbetter = int(np.sum(d < 0))                   # CAST better
        ax.annotate(f"{md:+.3f}", (x, mdc), textcoords="offset points",
                    xytext=(0, 9 if md >= 0 else -16), ha="center",
                    fontsize=9, fontweight="bold")
        ax.annotate(f"{nbetter}/{n}", (x, 0.02), xycoords=("data", "axes fraction"),
                    ha="center", va="bottom", fontsize=7.5, color="#444")
    ax.axhline(0, color="gray", lw=1, ls="--")
    ax.set_ylim(YLO, YHI)
    ax.set_xlim(-0.6, 2.6)
    ax.set_xticks(pos)
    ax.set_xticklabels([lbl for _, lbl in FIELDS], fontsize=9)
    ax.set_title(f"CAST vs {REF_TITLE[ref]}", fontsize=11, fontweight="bold")
    age_note = "ages 5–10" if ref == "Sanchez" else "ages 5–12"
    ax.text(0.5, 0.985, f"1.0 mm grid · n={n_used} held-out · {age_note}",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#555")

axes[0].set_ylabel("paired difference  CAST − reference (mm)\n"
                   "← CAST better        reference better →", fontsize=9.5)

# shared legend
handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor="#2e86ab",
                  markersize=7, label="CAST better (Δ<0)"),
           Line2D([0], [0], marker="o", color="w", markerfacecolor="#d1495b",
                  markersize=7, label="reference better (Δ>0)"),
           Line2D([0], [0], color="k", lw=2.4, label="median")]
fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9,
           frameon=False, bbox_to_anchor=(0.5, -0.04))

fig.suptitle("Direction-of-measurement decides the “winner” across all comparators "
             "— the fair symmetric ASSD favors CAST",
             fontsize=12, fontweight="bold", y=1.02)

fig.tight_layout(rect=[0, 0.02, 1, 0.99])
fig.savefig(outp, dpi=170, bbox_inches="tight")
fig.savefig(outp.replace(".png", ".pdf"), bbox_inches="tight")
print(f"[saved] {outp} (+pdf)")
