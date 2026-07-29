# HANDOFF — intensity rerun is complete; results and what to do with them

**Written 2026-07-28.** Read `DEFORMATION_COST_MASK_ERROR_2026-07-28.md` first for why the
rerun happened and the mechanism. This document is the results and the work they imply.

---

## 0. Status

**All 5,104 jobs completed, 0 failed.** CAST 3,190/3,190, NKI 1,914/1,914, every row
`disp_component=syn`, coverage perfectly balanced (638 per CAST template age, 319 per NKI).

Reproduce any number here with:

```bash
python 07_Results_and_Analysis/analyze_dc_intensity.py --remote
```

| repo | HEAD | state |
|---|---|---|
| `overleaf/cast-manuscript` | `72b3ba4` | pushed, 48 pp, 0 errors |
| `overleaf/cast-descriptor` | `2c4a42b` | pushed, 23 pp, 0 errors |
| `cast-pipeline` | `8757b0d` | pushed |

Backup of the pre-rerun generation: `BACKUP_PRE_INTENSITY_RERUN_2026-07-28/` on carya,
6,046 `metrics.txt` + 8 CSVs, integrity-verified.

---

## 1. The results

| | mask era (published) | intensity (correct) |
|---|---:|---:|
| between-subject SD | 3.409 mm | **0.427 mm** |
| \|Δage\| < 0.5 median | 3.08 mm | **2.399 mm** |
| \|Δage\| ≥ 2 median | 3.63 mm | **2.425 mm** |
| age effect | +0.55 mm | **+0.026 mm** (p = 0.012) |
| effect / SD | 0.16 | **0.06** |
| CAST vs NKI | ≈3.8 vs 3.6 | **2.415 vs 2.382** |
| CAST − NKI, paired (n=319) | — | **+0.044 mm**, p = 1.8×10⁻⁶ |
| \|Δage\| vs cost | — | r = +0.085, slope **+0.024 mm/yr** |

Per-template-age medians are flat: 2.357–2.496 mm across ages 7–11.

### How to read these — this matters more than the numbers

**Every "significant" p here is a function of n, not of magnitude.** With n = 3,190 a
0.026 mm difference reaches p = 0.012. That is **3% of a 0.8 mm voxel**. The analysis script
originally printed "age effect RESOLVED" for exactly this and the verdict thresholds have
since been rewritten to report effect size in voxels and SD alongside p. Do not let a p-value
back into the manuscript without its effect size.

1. **The age effect is real and negligible.** It shrank ~20× (0.55 → 0.026 mm) and the
   effect-to-noise ratio got *worse* (0.16 → 0.06).
2. **CAST and NKI are equivalent.** 0.044 mm apart, 5.5% of a voxel — a *cleaner* tie than
   the published "≈3.8 vs 3.6". NKI is nominally lower; the direction matches the published
   claim, the magnitude is ~5× smaller.
3. **The SyN-saturation argument SURVIVES.** Four years of age mismatch moves the cost by
   0.098 mm (0.23 SD). On registrations that actually worked, the metric still barely
   responds to age. The paper's reason for de-emphasising deformation cost was right — it was
   just previously supported by an ill-posed measurement.

**This is a good outcome.** §"Deformation cost and regularity" needs renumbering, not
rewriting. Its hedged framing ("real but gentle", "not statistically robust") turns out to
have been correct.

---

## 2. Work to do

### A. Methods manuscript — deformation-cost section

- **§ Deformation cost and regularity** — replace 3.08/3.63 with 2.399/2.425; state the
  effect as +0.026 mm (3% of a voxel) and say plainly it is statistically detectable but
  practically nil at n = 3,190. Do not describe it as an effect.
- **`tab:analysis-cohorts` (~L488)** — "Deformation-cost mixed model & 3,175 regs" → **3,190**
  (the old table was missing 8 age-11-F and 7 age-7-F pairs).
- **`tab:validity-reliability` (~L826)** — "Deformation cost & BRAIN CAST ≈ NKI (≈3.8 vs
  3.6 mm)" → **2.42 vs 2.38 mm**, and note it is now a paired comparison on identical inputs.
- **`F2_agexage_clean`** — regenerate from the new data; its caption quotes 3,175
  registrations and a +0.10 mm/yr slope (now **+0.024**).
- **Methods** — add that the cost is computed on CSF-normalised **intensity** images
  (`subj_<EID>_csfNorm_rc.nii.gz`), brain-masked, on the **SyN warp only**. The paper
  currently says only "warp subject *i* to template *j*", which is what allowed masks to go
  unnoticed.
- **The mixed model** — refit on the new values; the published coefficients are mask-era.

### B. Deferred text edits (unblocked now)

- **§2.7** — state that the Jacobian is computed on the SyN warp field, affine excluded.
- **Tissue-Jacobian paragraph** — same clause. Both are one sentence each.
- **Supplementary age-9 Jacobian** — was the only composite-Jacobian, mask-based figure.
  The rerun covers ages 9 M/F, so rebuild it from the new data and it joins the other two
  conventions. Its published −0.108 vs §2.7's −0.032 was never like-for-like.

### C. Data descriptor

Check whether `DDF4_quality.png` (Fig 8) panel c and any deformation-cost text depend on
the old CSV. If so, regenerate. The descriptor is **in review at Scientific Data**, so
changes land at revision.

### D. Verification

`verify_claims.py` is at 41 verified / 0 mismatch / 4 uncheckable but has **no assertions on
any of these numbers**. Add them once the text is updated — that is what stops the next
drift.

---

## 3. Traps, all of which bit during this work

- **Search too narrowly and you will "prove" absence.** Cost me three times: `Templates/*/`
  missed NKI templates sitting in `Templates/`; a maxdepth-4 find missed the centred images
  at depth 5; `/project/contreras-vidal/Image/*.sh` missed the preprocessing scripts in
  `PediatricMriDB/`.
- **`ImageMath RecenterImage` does not exist in this ANTs build.** `recenter_one.sh` calls
  it; it fails silently-ish. Recentring is a pure header rewrite — negated
  intensity-weighted centre of mass — implemented exactly in `recenter_csfnorm.py`
  (validated 6/6, error 0.0001 mm).
- **Never write into `test_set_dc/`.** It holds the only surviving record of the 2025-11
  generation; its transforms were deleted by the storage cleanup.
- **`IFS=$"\t"` is locale translation, not a tab.** It queued 48 jobs with garbage arguments.
  Use `IFS=$'\t'`, and write submitters as files rather than inline over ssh.
- **Check effect size before believing a p-value.** See §1.

---

## 4. Still open from earlier in the sweep

- Descriptor **Fig 4 vs Fig 7 cohort mismatch** — Fig 4 plots the 1,272-subject construction
  roster, Fig 7 a 1,473-subject screened pool, both captioned as developmental norms. Needs
  an author decision; same shape as the M2 table split.
- **Zenodo re-cut and the pipeline release tag** remain gated on explicit approval. The
  repo is pushed but untagged, so the archived DOI still predates the age-11-female rebuild.
- Container digest for the descriptor's container instructions, pending from before.
