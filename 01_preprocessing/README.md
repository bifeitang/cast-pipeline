# Preprocessing

Raw HBN T1w scans → analysis-ready, CSF-anchored, skull-stripped, recentered volumes,
run per subject as SLURM array jobs that execute the pipeline **inside Apptainer/Singularity
containers** (so FreeSurfer / FSL / ANTs / AFNI / CAT12 versions are pinned — see `../container/`).

## How the pieces fit

| Layer | Script | Role |
|---|---|---|
| **Scheduler** | `batch_job_scheduler_s1.sh` (and `_s2`, `_s2.5`) | Walk `Age*/<sex>/intensity_improved_formated/`, submit one job per subject. Subjects are discovered from the directory listing — no identifiers are stored in the code. |
| **Orchestrator** | `process_subject_s1.sh` | Per-subject driver. **Phase 1** runs the MATLAB-dependent steps in the `no_matlab` image; **Phase 2** runs the ANTs steps in the `reg` image, then auto-submits the next phase. Lock/flag files make it idempotent. |
| | `process_subject_s2.sh`, `process_subject_s2.5.sh` | Later-stage drivers (QC pass, recenter). |
| **Pipeline body** | `step1_uh_ped_temp_preprocess.sh` | The 10-step pipeline proper (see below), invoked inside the container with a phase argument. |
| | `step2_uh_ped_temp_preprocess.sh` | QC / second-pass body. |
| | `step2.5_uh_ped_temp_recenter.sh` | Recenter to a common origin. |
| | `step3_uh_ped_temp_preprocess.sh` | Final-stage body. |
| **Masks** | `template_mask_creation.sh` | Build the per-template brain masks used downstream in validation. |

## The 10 steps (in `step1_uh_ped_temp_preprocess.sh`)

reorient → **SANLM denoise** → N4 bias correction → surface reconstruction →
**DeepBET** skull-strip → **CSF-anchored intensity normalization** → MRIQC →
visual QC → recenter.

The CSF-anchored normalization is the contrast convention that the template-construction step
preserves (`-n 0`); see the methods paper and `../02_template_construction/`.

> **Reproducibility note.** The as-run SANLM denoising step used MATLAB (CAT12); the published
> container (`../container/`) ships a **license-free** equivalent via ANTs `DenoiseImage` (SANLM,
> Manjón 2010). Cluster paths and `.sif` image names are non-functional placeholders
> (`${DB}`, `${C_REG}`, `${C_PREPROC}`, …) — set them in `../config.sh` for your environment.
