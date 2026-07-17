# CAST pipeline container

Two images document the CAST processing environment. Cite **both** in the data descriptor.

## 1. As-run image (exact environment that built the released templates)
```
docker pull bifeitangmac/mri_template_env_matlab:<IMMUTABLE_TAG>
```
- Bundles: ANTs 2.5.0, FreeSurfer 7.4.1, FSL 6.0.7, AFNI 23.2.04, SPM12 + CAT12 12.9, **MATLAB R2023b**.
- The denoising step (preprocessing Step 2) runs CAT12 SANLM via `matlab -nodesktop -nosplash -r "cat_vol_sanlm,quit"`.
- ⚠️ **Requires a MATLAB license** — a third party cannot run this image without one.
- ⚠️ Built by `docker commit` (tag `:activated`). **Before deposit:** re-tag with an immutable version (not `:latest`/`:activated`) and publish the digest:
  ```
  docker pull bifeitangmac/mri_template_env_matlab:activated
  docker tag  bifeitangmac/mri_template_env_matlab:activated bifeitangmac/mri_template_env_matlab:1.0.0
  docker push bifeitangmac/mri_template_env_matlab:1.0.0
  docker inspect --format='{{index .RepoDigests 0}}' bifeitangmac/mri_template_env_matlab:1.0.0
  # -> cite this sha256 digest verbatim in BOTH papers
  ```

## 2. License-free build (this `Dockerfile`) — for reuse
Identical free-tool stack, with **SANLM performed by ANTs `DenoiseImage`** instead of CAT12/MATLAB.
CAT12 SANLM and ANTs `DenoiseImage` are the **same algorithm** — Manjón et al. (2010) spatially-adaptive
non-local means — so the substitution is principled, not a workaround. The whole pipeline then runs with
**no proprietary dependency**.
```
docker build -t cast-pipeline:1.0.0 container/
```
Per-subject denoise (replaces the CAT12/MATLAB call):
```
DenoiseImage -d 3 -n Rician -i input.nii.gz -o denoised.nii.gz   # adaptive NLM, reduced strength
```

## Convert to Apptainer/Singularity (.sif) for HPC
```
apptainer build mri_template_env.sif docker-daemon://cast-pipeline:1.0.0
# or from Docker Hub:
apptainer build mri_template_env.sif docker://bifeitangmac/mri_template_env_matlab:1.0.0
```

## FreeSurfer license
FreeSurfer needs a free license file at runtime (not redistributable in the image):
```
docker run --rm -v $PWD/license.txt:/opt/freesurfer/license.txt -v $PWD/data:/work cast-pipeline:1.0.0 ...
```

## Canonical naming (resolves the 3-name inconsistency in the drafts)
| role | image |
|---|---|
| as-run (with MATLAB) | `bifeitangmac/mri_template_env_matlab:1.0.0` |
| license-free reuse build | `cast-pipeline:1.0.0` (this Dockerfile) |
| HPC validation (ANTs-only subset) | `mri_template_env_reg.sif` (derived; document as a subset or rebuild from this Dockerfile) |

Do **not** use `mri_template_env` (older, no CAT12) or `pediatrictemplate-pipeline` (never published) in the papers.
