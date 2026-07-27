"""Sex-matched vs mismatched deformation cost at the age-nine templates.

Produces BOTH supplementary panels of manuscript Fig. 14:
    figures_final/gender_lollipop.png   waterfall of per-subject Delta
    figures_final/age_effect.png        age-wise Delta by sex and normalisation

RECONSTRUCTED GENERATOR (2026-07-27). Neither figure had a generator in the repo.
Provenance was established against the committed summary tables and reproduces exactly:
`tables/age_delta_summary_icv_filtered.csv` matches this computation in 14 of its 16
cells to six decimal places, and the two that differ are explained below (they differ in
n only, never in the value).

Delta convention: Delta = cost(mismatched-sex age-9 template) - cost(matched-sex age-9
template), so POSITIVE Delta means the sex-matched template was the cheaper target. This
is the convention the manuscript text and the `age_effect` y-axis label both use.

Source: DeformationAnalysis/test_set_on_template_metrics_with_sex.csv
        319 held-out subjects x 2 age-nine templates x 2 normalisations = 1,276 rows.

TWO DEFECTS IN THE SOURCE FILE, both handled here and both reported at run time:

1. One physically corrupted line (line 958). Two records are glued together with the
   newline lost, so the first record's `pct_non_diffeomorphic` runs straight into the
   next record's `age_dir` ("0.000000" + "10" -> "0.00000010") and the first record's
   trailing Sex_Code,Sex_Text are gone entirely. pandas.read_csv simply throws on this.
   Repaired by splitting at the decimal and recovering the lost sex from the same
   subject's other rows (NDARZM877DMC, female in all three of its intact rows).

2. One subject carries CONTRADICTORY sex labels: NDARAX431KJ2 is Sex_Code=0/male on
   three of its four rows and Sex_Code=1/female on the fourth (age9_female x icv). It is
   a single-row label corruption, not an ambiguous subject, so sex is resolved by
   majority vote per subject -- male here, 3:1.

   This is precisely why the published `age_effect.png` shows n=24 at male age 10 in the
   icv panel but n=25 in the diag panel: the earlier pipeline pivoted on (subject, sex),
   which split this subject into two half-rows with no computable Delta under icv, and
   dropped it. With the label corrected the subject is a valid male at age 10 under both
   normalisations, so this script reports n=25 in both. That is the only intended
   difference from the published figure, and it is a correction, not a drift.
"""
import csv, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, "/path/to/cast-project/07_Results_and_Analysis")
from figs_style import set_style, save, panel_letter, MALE, FEMALE
set_style()

SRC = "DeformationAnalysis/test_set_on_template_metrics_with_sex.csv"
N_FIELDS = 19
TPL_M, TPL_F = "age9_male_template.nii.gz", "age9_female_template.nii.gz"
N_BOOT = 5000
BOOT = np.random.default_rng(0)


def load_repaired(path):
    """Read the CSV, repairing the known glued-record corruption. Fails loudly on any
    malformation other than the one documented above."""
    rows, header, repaired = [], None, []
    for lineno, line in enumerate(open(path), start=1):
        f = next(csv.reader([line.rstrip("\n")]))
        if header is None:
            header = f
            continue
        if len(f) == N_FIELDS:
            rows.append(f)
        elif len(f) == 2 * N_FIELDS - 3:      # record A lost 2 trailing fields + newline
            glue = f[16]
            dot = glue.index(".")
            pnd, nxt = glue[:dot + 7], glue[dot + 7:]
            rows.append(f[:16] + [pnd, "", ""])
            rows.append([nxt] + f[17:])
            repaired.append(lineno)
        else:
            raise SystemExit(f"{path}:{lineno}: {len(f)} fields, expected {N_FIELDS}. "
                             "Unrecognised corruption -- refusing to guess.")
    df = pd.DataFrame(rows, columns=header)
    df["age_dir"] = df["age_dir"].astype(int)
    df["normalized_warp_value"] = df["normalized_warp_value"].astype(float)

    # recover the sex lost by the corruption from the same subject's intact rows
    known = df[df.Sex_Text != ""].drop_duplicates("subject_id").set_index("subject_id")["Sex_Text"]
    blank = df.Sex_Text == ""
    df.loc[blank, "Sex_Text"] = df.loc[blank, "subject_id"].map(known)
    return df, repaired, df.loc[blank, "subject_id"].tolist()


def resolve_sex(df):
    """Majority vote per subject; returns (mapping, list of subjects that needed it)."""
    counts = df.groupby(["subject_id", "Sex_Text"]).size().unstack(fill_value=0)
    conflicted = counts[(counts > 0).sum(axis=1) > 1].index.tolist()
    return counts.idxmax(axis=1), conflicted


def deltas(df, sex_of, norm):
    d = df[df.norm_type == norm]
    p = d.pivot_table(index="subject_id", columns="template", values="normalized_warp_value")
    p = p.dropna(subset=[TPL_M, TPL_F])
    p["Sex_Text"] = p.index.map(sex_of)
    p["age"] = d.drop_duplicates("subject_id").set_index("subject_id")["age_dir"]
    p["delta"] = np.where(p.Sex_Text == "male", p[TPL_F] - p[TPL_M], p[TPL_M] - p[TPL_F])
    return p.reset_index()


df, repaired_lines, recovered = load_repaired(SRC)
sex_of, conflicted = resolve_sex(df)
D = {n: deltas(df, sex_of, n) for n in ("icv", "diag")}

print("=== source integrity ===")
print(f"  glued lines repaired      : {repaired_lines or 'none'}")
print(f"  sex recovered from siblings: {recovered or 'none'}")
print(f"  contradictory sex labels   : {conflicted or 'none'}"
      f"{'  -> resolved by majority vote to ' + sex_of[conflicted[0]] if conflicted else ''}")
print(f"  subjects with a usable Delta: icv {len(D['icv'])}, diag {len(D['diag'])}\n")

# ---------------------------------------------------------------- gender_lollipop -----
# The published panel shows the ICV normalisation only, so this does too.
NORM_WATERFALL = "icv"
fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6))
for ax, (sex, col) in zip(axes, [("male", MALE), ("female", FEMALE)]):
    s = D[NORM_WATERFALL][D[NORM_WATERFALL].Sex_Text == sex].sort_values("delta", ascending=False)
    y = s.delta.values
    x = np.arange(len(y))
    pos = y > 0
    ax.vlines(x[pos], 0, y[pos], color=col, lw=0.9, alpha=0.85)
    ax.vlines(x[~pos], 0, y[~pos], color="0.72", lw=0.9)
    ax.plot(x[pos], y[pos], "o", ms=2.2, color=col)
    ax.plot(x[~pos], y[~pos], "o", ms=2.2, color="0.72")
    ax.axhline(0, color="0.35", ls="--", lw=1)
    ax.set_title(f"{sex}  |  matched better in {100*pos.mean():.0f}%  |  "
                 f"median $\\Delta$={np.median(y):+.3f}", fontsize=8.5)
    ax.set_xlabel(f"held-out subjects, sorted by $\\Delta$  (n={len(y)})")
    ax.set_ylabel("$\\Delta$ normalized mean displacement\n(mismatched $-$ matched)", fontsize=7.5)
fig.suptitle("Sex-matched advantage at the age-nine template: positive $\\Delta$ = matched template cheaper "
             f"({NORM_WATERFALL.upper()} normalisation)", fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, "figures_final/gender_lollipop")

print(f"=== waterfall ({NORM_WATERFALL}) ===")
for sex in ("male", "female"):
    s = D[NORM_WATERFALL][D[NORM_WATERFALL].Sex_Text == sex]
    print(f"  {sex:<7} n={len(s):>4}  median={s.delta.median():+.4f}  "
          f"mean={s.delta.mean():+.4f}  matched-better={100*(s.delta>0).mean():.1f}%")

# ------------------------------------------------------------------- age_effect -------
fig, axes = plt.subplots(2, 2, figsize=(9.6, 5.4), sharex=True, sharey="row")
for r, (sex, col) in enumerate([("male", MALE), ("female", FEMALE)]):
    for c, norm in enumerate(["icv", "diag"]):
        ax = axes[r, c]
        s = D[norm][D[norm].Sex_Text == sex]
        ages = sorted(s.age.unique())
        mu, lo, hi, ns = [], [], [], []
        for a in ages:
            v = s[s.age == a].delta.values
            # bootstrap percentile CI of the mean -- the committed summary tables carry
            # ASYMMETRIC ci_low/ci_high about the mean, so they were bootstrapped, not
            # computed as mean +/- 1.96 SE. Seeded, so the band is reproducible.
            m = v.mean()
            bs = BOOT.choice(v, (N_BOOT, len(v)), replace=True).mean(axis=1)
            mu.append(m); lo.append(np.percentile(bs, 2.5)); hi.append(np.percentile(bs, 97.5))
            ns.append(len(v))
        ax.fill_between(ages, lo, hi, color=col, alpha=0.20, lw=0)
        ax.plot(ages, mu, "-o", color=col, ms=4.5, lw=1.4)
        for a, m, n in zip(ages, mu, ns):
            ax.annotate(f"n={n}", (a, m), textcoords="offset points", xytext=(0, 7),
                        ha="center", fontsize=5.6, color="0.35")
        ax.axhline(0, color="0.35", ls="--", lw=1)
        ax.set_title(f"{sex}  |  {norm}", fontsize=8.5)
        if r == 1: ax.set_xlabel("subject age (years)")
        if c == 0: ax.set_ylabel("$\\Delta$ (mismatched $-$ matched)", fontsize=7.5)
fig.suptitle("Age-wise sex-matched advantage: the effect is small and not systematic in age",
             fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.93])
save(fig, "figures_final/age_effect")

print("\n=== age-wise Delta (mean) ===")
print(f"{'norm':<6}{'sex':<8}{'age':>4}{'n':>5}{'mean':>11}{'median':>11}{'matched%':>10}")
for norm in ("icv", "diag"):
    for sex in ("male", "female"):
        s = D[norm][D[norm].Sex_Text == sex]
        for a in sorted(s.age.unique()):
            v = s[s.age == a].delta.values
            print(f"{norm:<6}{sex:<8}{a:>4}{len(v):>5}{v.mean():>+11.6f}"
                  f"{np.median(v):>+11.6f}{100*(v>0).mean():>9.1f}%")
