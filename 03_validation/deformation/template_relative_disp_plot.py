# Converted from notebook: template_relative_disp_plot.ipynb
# Each section below corresponds to a notebook cell.

# %% [Cell 0]
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# Paths
DATA_PATH = Path('/path/to/cast-project/DeformationAnalysis/test_set_on_template_metrics_all.csv')
PLOTS_DIR = Path('/path/to/cast-project/DeformationAnalysis/plots')
TABLES_DIR = Path('/path/to/cast-project/DeformationAnalysis/tables')

PLOTS_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

sns.set(style='whitegrid', context='talk')

# %% [Cell 1]
# Load data, derive ages, and compute template-relative displacement per subject (split by template source)

df = pd.read_csv(DATA_PATH)

# Validate required columns present in CSV
required_cols = {"subject_id", "age_dir", "template", "mean_disp_mm"}
missing = required_cols.difference(df.columns)
if missing:
    raise ValueError(f"Missing required columns in CSV: {missing}")

# Derive subject_age from age_dir (numeric) and template_age from template filename
# Extract numbers after 'age' (e.g., age9 or age8.5)
df["subject_age"] = pd.to_numeric(df["age_dir"], errors="coerce")
df["template_age"] = df["template"].astype(str).str.extract(r"age(\d+(?:\.\d+)?)", expand=False)
df["template_age"] = pd.to_numeric(df["template_age"], errors="coerce")

# Identify template source (NKI vs non-NKI) from template filename
df["template_source"] = np.where(
    df["template"].astype(str).str.contains("NKI", case=False, na=False),
    "NKI",
    "non-NKI",
)

# Enforce numeric dtypes where appropriate
for col in ["subject_age", "template_age", "mean_disp_mm"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Drop rows with missing critical values
df = df.dropna(subset=["subject_id", "subject_age", "template_age", "mean_disp_mm"]).copy()

# Compute per-subject mean within each template source (removes subject bias per source)
subject_means = (
    df.groupby(["subject_id", "template_source"], as_index=False)["mean_disp_mm"].mean()
      .rename(columns={"mean_disp_mm": "subject_mean_disp_mm"})
)

# Merge back and compute template_relative_disp using source-specific subject mean
rel = df.merge(subject_means, on=["subject_id", "template_source"], how="left")
rel["template_relative_disp"] = rel["mean_disp_mm"] - rel["subject_mean_disp_mm"]

# Keep tidy frame for downstream steps
rel_df = rel[[
    "subject_id", "subject_age", "template_age", "template_source",
    "mean_disp_mm", "subject_mean_disp_mm", "template_relative_disp"
]].copy()

# %% [Cell 2]
# Aggregate mean and SEM by template source, subject_age, and template_age

def _sem(x: pd.Series) -> float:
    n = x.count()
    if n <= 1:
        return np.nan
    return x.std(ddof=1) / np.sqrt(n)

stats = (
    rel_df
    .groupby(["template_source", "subject_age", "template_age"])  # subject age on x, template age as hue, split by source
    .agg(
        mean_relative_disp=("template_relative_disp", "mean"),
        sem_relative_disp=("template_relative_disp", _sem),
        n=("template_relative_disp", "count"),
    )
    .reset_index()
    .sort_values(["template_source", "template_age", "subject_age"])  # friendly ordering
)

# Save aggregated stats (by source)
stats_out = TABLES_DIR / "template_relative_disp_stats_by_source.csv"
stats.to_csv(stats_out, index=False)
print(f"Saved stats to {stats_out}")

# %% [Cell 3]
# Plot mean and SEM lines by template age, split by template source (NKI vs non-NKI)

sources = list(stats["template_source"].dropna().unique())
sources = sorted(sources, key=lambda s: (s != "NKI", s))  # NKI first if present
ncols = max(1, len(sources))
fig, axes = plt.subplots(1, ncols, figsize=(8 * ncols, 7), sharey=True, sharex=True)
if ncols == 1:
    axes = [axes]

for ax, src in zip(axes, sources):
    sub_stats = stats.loc[stats["template_source"] == src]
    template_ages = sorted(sub_stats["template_age"].dropna().unique())
    palette = sns.color_palette("tab20", n_colors=max(6, len(template_ages)))
    color_map = {t_age: palette[i % len(palette)] for i, t_age in enumerate(template_ages)}

    for t_age in template_ages:
        sub = sub_stats.loc[sub_stats["template_age"] == t_age].sort_values("subject_age")
        if sub.empty:
            continue
        ax.errorbar(
            sub["subject_age"],
            sub["mean_relative_disp"],
            yerr=sub["sem_relative_disp"],
            label=f"Template age {t_age}",
            color=color_map[t_age],
            marker="o",
            linewidth=2,
            capsize=3,
            alpha=0.9,
        )

    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
    ax.set_title(f"{src} templates")
    ax.set_xlabel("Subject age")
    ax.set_ylabel("Template-relative displacement (mm)")

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, title="Template age", bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0.)
fig.suptitle("Template-relative displacement by subject age (bias removed per subject, split by source)")
fig.tight_layout()

plot_path = PLOTS_DIR / "template_relative_disp_by_subject_age_split_by_source.png"
fig.savefig(plot_path, dpi=220, bbox_inches="tight")
print(f"Saved plot to {plot_path}")
plt.show()

# %% [Cell 4]
# Build plot groups (NKI, female, male) and compute subject-relative displacement within each group

# Derive template gender strictly from filename tokens (female/male)
templ_lower = df["template"].astype(str).str.lower()
df["template_gender"] = templ_lower.str.extract(r'(?:^|[_-])(female|male)(?:[_-]|\b)', expand=False)

# Define plot groups: NKI (any gender), non-NKI female, non-NKI male
df["plot_group"] = np.where(
    df["template"].astype(str).str.contains("NKI", case=False, na=False),
    "NKI",
    np.where(df["template_gender"].eq("female"), "female",
             np.where(df["template_gender"].eq("male"), "male", np.nan))
)

# Keep only the groups of interest
df_plot = df[df["plot_group"].isin(["NKI", "female", "male"])].copy()

# Compute per-subject mean within each plot_group
subject_means_pg = (
    df_plot.groupby(["subject_id", "plot_group"], as_index=False)["mean_disp_mm"].mean()
          .rename(columns={"mean_disp_mm": "subject_mean_disp_mm_pg"})
)

# Merge back and compute template-relative displacement for each plot_group
rel_pg = df_plot.merge(subject_means_pg, on=["subject_id", "plot_group"], how="left")
rel_pg["template_relative_disp_pg"] = rel_pg["mean_disp_mm"] - rel_pg["subject_mean_disp_mm_pg"]

# %% [Cell 5]
# Aggregate mean and SEM by plot_group, subject_age, and template_age (for three-panel figure)

def _sem_pg(x: pd.Series) -> float:
    n = x.count()
    if n <= 1:
        return np.nan
    return x.std(ddof=1) / np.sqrt(n)

stats_pg = (
    rel_pg
    .groupby(["plot_group", "subject_age", "template_age"])  # subject age on x, template age as hue, split by group
    .agg(
        mean_relative_disp=("template_relative_disp_pg", "mean"),
        sem_relative_disp=("template_relative_disp_pg", _sem_pg),
        n=("template_relative_disp_pg", "count"),
    )
    .reset_index()
)

# Order groups for plotting
cat_type = pd.CategoricalDtype(categories=["NKI", "female", "male"], ordered=True)
stats_pg["plot_group"] = stats_pg["plot_group"].astype(cat_type)
stats_pg = stats_pg.sort_values(["plot_group", "template_age", "subject_age"]).reset_index(drop=True)

# Save aggregated stats for the three-panel figure
stats_out_pg = TABLES_DIR / "template_relative_disp_stats_three_panel.csv"
stats_pg.to_csv(stats_out_pg, index=False)
print(f"Saved stats to {stats_out_pg}")

# %% [Cell 6]
# Three-panel plot: NKI, female, male

order = ["NKI", "female", "male"]
plot_groups_present = [g for g in order if g in stats_pg["plot_group"].astype(str).unique().tolist()]
ncols = max(1, len(plot_groups_present))
fig, axes = plt.subplots(1, ncols, figsize=(8 * ncols, 7), sharey=True, sharex=True)
if ncols == 1:
    axes = [axes]

for ax, grp in zip(axes, plot_groups_present):
    sub_stats = stats_pg.loc[stats_pg["plot_group"].astype(str) == grp]
    template_ages = sorted(sub_stats["template_age"].dropna().unique())
    palette = sns.color_palette("tab20", n_colors=max(6, len(template_ages)))
    color_map = {t_age: palette[i % len(palette)] for i, t_age in enumerate(template_ages)}

    for t_age in template_ages:
        sub = sub_stats.loc[sub_stats["template_age"] == t_age].sort_values("subject_age")
        if sub.empty:
            continue
        ax.errorbar(
            sub["subject_age"],
            sub["mean_relative_disp"],
            yerr=sub["sem_relative_disp"],
            label=f"Template age {t_age}",
            color=color_map[t_age],
            marker="o",
            linewidth=2,
            capsize=3,
            alpha=0.9,
        )

    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1)
    ax.set_title(f"{grp} templates")
    ax.set_xlabel("Subject age")
    ax.set_ylabel("Template-relative displacement (mm)")

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, title="Template age", bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0.)
fig.suptitle("Template-relative displacement by subject age (bias removed per subject)\nThree panels: NKI, female, male")
fig.tight_layout()

plot_path = PLOTS_DIR / "template_relative_disp_by_subject_age_three_panels.png"
fig.savefig(plot_path, dpi=220, bbox_inches="tight")
print(f"Saved plot to {plot_path}")
plt.show()

# %% [Cell 7]
# Compute male/female subject counts per age (5-12) using all-metrics CSV + subject info for sex

DATA_ALL = Path('/path/to/cast-project/DeformationAnalysis/test_set_on_template_metrics_all.csv')
SUBJECT_INFO = Path('/path/to/cast-project/DeformationAnalysis/hbn_subject_info_all.txt')

# Load all metrics (for subject ids and ages) and subject info (for sex)
df_all = pd.read_csv(DATA_ALL)
df_info = pd.read_csv(SUBJECT_INFO)

# Validate columns
req_all = {"subject_id", "age_dir"}
req_info = {"EID", "Sex_Text"}
miss_all = req_all.difference(df_all.columns)
miss_info = req_info.difference(df_info.columns)
if miss_all or miss_info:
    raise ValueError(f"Missing columns — all: {miss_all}, info: {miss_info}")

# Normalize
ages_series = pd.to_numeric(df_all["age_dir"], errors="coerce")
sex_map = {"m": "male", "male": "male", "f": "female", "female": "female"}
df_info["subject_sex"] = df_info["Sex_Text"].astype(str).str.strip().str.lower().map(sex_map)

# Join sex onto all-metrics via subject_id ↔ EID
meta = df_all[["subject_id"]].drop_duplicates().merge(
    df_info[["EID", "subject_sex"]], left_on="subject_id", right_on="EID", how="left"
)

# Build base frame with subject age and sex
base = (
    df_all.assign(subject_age=ages_series)
          .merge(meta[["subject_id", "subject_sex"]], on="subject_id", how="left")
)

# Filter ages 5–12 and valid sex
df_counts_base = base.dropna(subset=["subject_id", "subject_age", "subject_sex"]).copy()
df_counts_base = df_counts_base[(df_counts_base["subject_age"] >= 5) & (df_counts_base["subject_age"] <= 12)].copy()

# Count unique subjects per age (int) and sex
counts = (
    df_counts_base.groupby([df_counts_base["subject_age"].astype(int), "subject_sex"])['subject_id']
                  .nunique()
                  .reset_index()
                  .rename(columns={"subject_age": "age", "subject_id": "num_subjects"})
                  .sort_values(["age", "subject_sex"])
)

# Ensure complete 5–12 × {female, male}
ages = pd.Index(range(5, 13), name="age")
sexes = pd.Index(["female", "male"], name="subject_sex")
counts_full = (
    counts.set_index(["age", "subject_sex"]).reindex(
        pd.MultiIndex.from_product([ages, sexes], names=["age", "subject_sex"]),
        fill_value=0
    ).reset_index()
)

# Save
counts_out = TABLES_DIR / 'testset_counts_by_age_gender.csv'
counts_full.to_csv(counts_out, index=False)
print(f"Saved counts to {counts_out}")

# %% [Cell 8]
# Plot male/female counts per age (5-12)

plt.figure(figsize=(10, 6))
ax = sns.barplot(
    data=counts_full,
    x="age",
    y="num_subjects",
    hue="subject_sex",
    palette={"female": sns.color_palette("Set2")[0], "male": sns.color_palette("Set2")[1]},
)
ax.set_xlabel("Age")
ax.set_ylabel("Number of subjects")
ax.set_title("Test set subject counts by age and sex (5–12)")
ax.legend(title="Sex", loc="upper right")

for container in ax.containers:
    ax.bar_label(container, fmt="%d", padding=2)

plt.tight_layout()
plot_counts_path = PLOTS_DIR / 'testset_counts_by_age_gender.png'
plt.savefig(plot_counts_path, dpi=220, bbox_inches='tight')
print(f"Saved plot to {plot_counts_path}")
plt.show()


