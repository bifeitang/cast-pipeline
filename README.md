# BRAIN CAST — Children's Age- and Sex-specific Templates: processing pipeline

Reproducible pipeline that builds the **BRAIN CAST** pediatric brain MRI template library
(28 age- and sex-specific T1-weighted templates, ages 5–18) from the Healthy Brain
Network (HBN), together with the validation suite used to evaluate it. Companion to:

- **Data descriptor:** Hu & Contreras-Vidal, *BRAIN CAST: Children's Age- and Sex-specific Templates — pediatric brain MRI templates spanning ages 5 to 18* (Scientific Data, in prep.).
- **Methods paper:** Hu & Contreras-Vidal, *An MRIQC-guided pipeline for age- and sex-specific pediatric brain MRI template construction, validated by downstream structural fidelity* (in prep.).

Developed at the NSF IUCRC [BRAIN Center](https://brain-d10.egr.uh.edu) (Award #2137255),
University of Houston. Templates are distributed with the `tpl-BRAINCAST_*` prefix.

BRAIN CAST is derived from HBN and is **not** a Child Mind Institute product. This repository is
**code only** — no MRI data and no subject identifiers are included (see *Data & ethics*).

## Layout
| directory | contents |
|---|---|
| `container/` | `Dockerfile` (license-free build; SANLM via ANTs `DenoiseImage`) + as-run image notes |
| `01_preprocessing/` | the 10-step constraint-aware preprocessing: SLURM/Apptainer orchestrator (`process_subject_s1.sh`, 2-phase) + schedulers + the in-container stage bodies (`step1…step3`) |
| `02_template_construction/` | ANTs `antsMultivariateTemplateConstruction2.sh` — generalized driver (`mri_template_construction.sh`) + the 30 exact `as_run/` per-stratum scripts |
| `03_validation/` | downstream-fidelity validation: `validity/` (interface error, symmetric ASSD, fractal dimension, sweep, tissue-Jacobian), `deformation/` + `deformation_cost/`, `tissue_volume/`, `morphometry/`, `montage/`; `verify_fd.py` / `verify_assd.py` reproduce the head-to-head numbers |
| `04_figures/` | figure-generation scripts (`make_figure_*.py`) |
| `sample_template/` | one illustrative demo template (age-9 male) — the full 28-template library is in the data DOI |
| `config.sh` | centralizes all paths as overridable variables (`DB`, `IMAGE_DIR`, `C`/`C_REG`/`C_PREPROC`, `PROJECT_ROOT`, `TMPROOT`, `NT`); ships **non-functional placeholders** — edit for your environment |

## Quick start
```bash
# 1. build the license-free container (or pull the as-run image; see container/README.md)
docker build -t cast-pipeline:1.0.0 container/
# 2. set paths for your environment
$EDITOR config.sh && source config.sh
# 3. preprocess -> construct -> validate (SLURM templates included under 03_validation/)
```

## Software (as-run environment)
ANTs 2.5.0 · FreeSurfer 7.4.1 · FSL 6.0.7 · AFNI 23.2.04 · SPM12 + CAT12 12.9 · Python 3.
The as-run denoiser is CAT12 SANLM under MATLAB R2023b; the bundled `container/Dockerfile`
replaces it with ANTs `DenoiseImage` (the same Manjón 2010 adaptive non-local-means), so the
pipeline runs with **no MATLAB license**.

## Data & ethics
HBN data are distributed by the Child Mind Institute through INDI under their data-use terms
and are **not** redistributed here. No subject identifiers appear in this repository: per-subject
references are replaced with `SUBJECT_ID` / `REFERENCE_SUBJECT` placeholders, and the HBN download
lists (subject manifests) are excluded. Released CAST templates are group-level averages
containing no subject-identifiable data; the full library is distributed via the data DOI.

## License
MIT — see [`LICENSE`](LICENSE).
