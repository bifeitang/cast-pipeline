# The deformation-cost analysis was run on brain masks — finding, mechanism, and rerun

**Written 2026-07-28.** Supersedes the deformation-cost portions of
`METHODS_FIGURE_AUDIT_HANDOFF_2026-07-27.md` and `RELEASE_UPDATE_NOTES_2026-07-26.md`.
Read `METHODS_AUDIT_LEDGER_2026-07-23.md` alongside this — it remains valid and this does
not repeat it.

---

## 0. TL;DR

Every deformation-cost registration in the methods paper registered a **binary brain mask**
onto a **greyscale intensity template**. Author confirmed this was an input-selection error,
not a design choice. 5,104 registrations are rerunning on the correct CSF-normalised
intensity images. The numbers change by ~70% and the section's central argument may need
rewriting — see §4.

Nothing else in either paper is affected: validity, head-to-head, morphometry and the
construction-warp Jacobians all come from different pipelines with different inputs.

---

## 1. The finding

`TemplateTestSet/hbn_grouped_by_age/<age>/processed_centered/*_processed_centered.nii.gz`
— the moving images for all 3,175 CAST and 1,877 NKI deformation-cost registrations — are
**binary masks**:

| | unique values | range |
|---|---:|---|
| fixed (template) | 1,322,260 | 0 – 8.247 (intensity) |
| moving (subject) | **2** | 0 – 1 (**binary**) |

Verified on four subjects at four separate ages. Corroborated by file size: all 353 are
under 500 KB (median 162 KB), which is what binary data compresses to; the correct
intensity images are ~4.5 MB.

**How it was missed.** The methods say the cost is "the normalized energy or displacement
required to warp subject *i* to template *j*" — true as written, and a reader assumes
T1-to-T1. `run_deformation_cost_batch.sh` globs the `processed_centered/` directory, and
nothing downstream inspects what it loaded.

**The correct images existed the whole time**, as `subj_<EID>_csfNorm_rc.nii.gz` inside the
per-subject tarballs. The tissue-Jacobian pipeline used them all along. Only the
deformation-cost path pointed at the wrong directory.

---

## 2. Why the numbers move the way they do — read this before interpreting results

The intuitive prediction is that a mask carries less information, so registering real
intensity should give a **larger** displacement. Measured on 8 identical subject-template
pairs, the opposite happens:

| | mask (published) | intensity | |
|---|---:|---:|---|
| mean displacement | 8.400 mm | **2.362 mm** | −72% |
| between-subject SD | 3.409 | **0.127** | 27× tighter |
| mean log J | −0.1372 | **+0.0650** | sign flips |
| correlation between metrics | | **r = 0.46** | |

**The mechanism.** CC compares local intensity patterns in a moving window. Inside a binary
mask every voxel is 1.0, so the local variance is **zero** and CC's denominator degenerates.
Across the whole brain interior the metric returns no usable gradient. The only place with
signal is the mask **edge**, where 1 meets 0 and the template has a brain boundary.

So the optimiser matched an outline and nothing else, and SyN's regularisation — not the
data — drove the interior. That is not an easier problem, it is an **under-constrained** one,
and under-constrained optimisers wander. The 8.4 mm is optimiser drift, not anatomy.

With intensity on both sides CC has texture to lock onto everywhere, the problem is
well-posed, and the answer is what it should be: after affine alignment a subject differs
from an age-matched template by ~2 mm locally.

The naive intuition is right for **mask→mask vs intensity→intensity**. The trap here was a
*mismatched pair*.

**Empirical signature of the ill-posedness**, if anyone wants to re-check: a 27× variance
collapse, r = 0.46 between the two metrics, and erratic per-subject behaviour (changes of
−58% to −82% with one subject at +7%).

---

## 3. What is rerunning

| arm | jobs | core-hours | output |
|---|---:|---:|---|
| CAST — 319 subjects × 10 templates (ages 7–11 × M/F) | 3,190 | 5,965 | `DC_INTENSITY_2026-07-27/` |
| NKI — 319 subjects × 6 templates (ages 7–12) | 1,914 | 3,579 | `DC_NKI_INTENSITY_2026-07-28/` |
| **total** | **5,104** | **9,544** (4.4% of balance) | |

Measured cost **1.87 core-hours/job** (n=8 intensity pilot; mask jobs were 1.92, so input
type does not change runtime). The release notes' 3.96 figure is from an older
configuration and overstates by ~2×.

Both arms use identical inputs, settings (`-disp-component syn`, `-n 8`, same container) and
guards, so the CAST-vs-NKI comparison is finally like-for-like.

Consumers of these results: `F2_agexage_clean`, the deformation-cost mixed model, the age-9
supplementary Jacobian figure (a subset — ages 9 M/F are inside the CAST run), and
`tab:validity-reliability`'s "≈3.8 vs 3.6 mm" row.

### Safeguards

- `sbatch_dc_intensity.sh` / `sbatch_dc_nki.sh` **refuse to run** if the moving image's max
  is 1, so the original bug cannot be silently reproduced.
- Output goes to new roots. `test_set_dc/` holds the **only surviving record** of the
  2025-11 generation (its transforms were deleted by the storage cleanup) and is never
  written to.
- Backed up first: `BACKUP_PRE_INTENSITY_RERUN_2026-07-28/` — 6,046 `metrics.txt` +
  8 derived CSVs, `tar tzf` integrity-verified.
- `metrics.txt` now carries a `disp_component` column, so a row records its own convention.

---

## 4. Expected impact on the conclusions — one is uncomfortable

**(a) The age effect may become detectable.** F2 reports 3.08 → 3.63 mm across |Δage|.
Against SD 3.4 that 0.55 mm was buried, which is exactly why the paper calls it "real but
gentle" and "not statistically robust". Against SD 0.13 it would be large. The rerun may
convert a hedged null into a clear finding.

**(b) CAST vs NKI becomes informative.** "≈3.8 vs 3.6 mm" was a 0.2 mm gap against SD 3.4 —
uninterpretable. On intensity data the same gap is over a standard deviation.

**(c) The section's central argument may not survive.** The paper de-emphasises deformation
cost because the metric is *"SyN-saturated"* — a flexible warp absorbs age and shape
mismatch, so it cannot discriminate. **That conclusion was drawn from the mask data.** If the
metric was insensitive because it was ill-posed rather than because SyN saturates it, the
intensity rerun may show it discriminating well, and the stated justification for setting it
aside would need rewriting.

That would not weaken the paper. Structural fidelity remains the primary evidence, and a
deformation-cost metric that *does* discriminate is an additional argument for age- and
sex-specific templates. But the reasoning in §"Deformation cost and regularity" would change.

All three are extrapolations from 8 subjects and one template. The 5,104 jobs settle them.

---

## 5. Recentring, for the 47 subjects whose centred images were lost

47 of the 319 have no tarball and no centred image. All 47 retain
`subj_<EID>_brainmask_csfNorm.nii.gz`, the pre-recentring stage.

**Recentring is a pure header rewrite** — voxel data byte-identical — that shifts the affine
by the **negated intensity-weighted centre of mass**. Established by testing four candidate
definitions against a verified pre/post pair:

| definition | error |
|---|---:|
| **intensity-weighted COM** | **0.0001 mm** ← exact |
| binary COM (>0) | 1.0025 mm |
| bbox centre of >0 | 12.8167 mm |
| geometric centre of grid | 29.0842 mm |

It reproduces the original ANTs `.mat` parameters to four decimals, and validates **6/6** on
independent pairs at ages 6, 8 and 11. Implemented in
`03_validation/deformation/recenter_csfnorm.py`.

`ImageMath RecenterImage` — what `recenter_one.sh` calls — **does not exist in this project's
ANTs build**; an attempt using it failed all 47 jobs in 17 seconds. Being header-only, the
direct implementation needs no cluster time at all.

The shift magnitudes (15–37 mm) are the same near-rigid coordinate-origin offset the release
notes blame for inflating `mean_disp_mm` to ~31–35 mm — now confirmed three independent ways.

Distribution check: the 47's `brainmask_csfNorm` match the 272's on median intensity
(p=0.774), p99 (p=0.342) and brain volume (p=0.880), so they are the same processing stage.
Comparison group is only 6 — reassurance, not proof.

---

## 6. Jacobian conventions — three populations, now mapped

Not all Jacobians in these papers mean the same thing. The affine carries **scale and shear**,
so a SyN-only Jacobian and a composed affine∘SyN Jacobian are different quantities, not
rescalings. Measured: they differ by a median of 84% and correlate at only r = 0.77.

| population | value | Jacobian field | moving image |
|---|---:|---|---|
| §2.7 construction warps | −0.032 | **SyN only** | construction warps |
| Tissue Jacobian GM/WM/CSF | −0.03 / −0.03 / +0.05 | **SyN only** | intensity (`csfNorm_rc`) |
| Supp. age-9 test set | −0.108 | **composed** | **binary mask** |

Two independent pipelines on SyN-only intensity land at −0.032 and −0.03 — mutually
corroborating. The age-9 supplementary was the sole outlier on **both** axes; the rerun fixes
both at once.

⚠️ The published comparison of −0.108 against −0.032 attributes the whole gap to age
mismatch. Those are different measurements. Like-for-like the test-set value is ≈ −0.135, so
the gap is **larger** than stated — the paper understates its own effect.

`cal_deformation_cost.sh` now always takes the Jacobian from the composed field regardless of
`-disp-component`, so Jacobian columns stay comparable with everything published. An earlier
version shared one field between both metrics and silently redefined the Jacobian; that was
caught by validation (mean_logJ moved 84%, r fell to 0.77) before any large run.

---

## 7. Still open

- **NKI templates** live at `PediatricMriDB/Templates/NKI_age<N>_brain_template.nii.gz`
  (1.0 mm), not under `Templates/*/`. `NKI_age6a7` is a deliberate age-6&7 composite — NKI
  lacks the subjects to separate them; ages 8–12 are individually tagged.
- Text edits deferred until the numbers land: state the SyN-only convention in §2.7 and the
  tissue-Jacobian paragraph; update §"Deformation cost and regularity" per §4 above.
- `Fonov` does **not** appear in the deformation-cost table at all. It reaches the paper via
  `refbench/assd_0p8_measures.jsonl`, a separate pipeline that used intensity images
  correctly and reproduces exactly. No action.
- A methods sentence is needed saying the cost is computed on CSF-normalised intensity
  images, whatever the rerun shows.

---

## 8. Verification

`07_Results_and_Analysis/verify_claims.py` re-derives 41 values from source and fails on
drift; run it before any submission. It currently reports 41 verified / 0 mismatch /
4 uncheckable. It will need new assertions once the rerun lands.
