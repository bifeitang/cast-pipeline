# Running the CAST pipeline in its container — detailed setup

This document explains the one thing about the CAST pipeline that is **not obvious
from the code**: the container is only the *environment*. The pipeline scripts and
the data live on the host and are handed to the container through a bind mount. If
you `apptainer exec` the image and expect the pipeline to be inside it, nothing will
run — the image ships ANTs/FSL/FreeSurfer/AFNI, not the CAST scripts.

---

## 1. Mental model — three things, kept separate

| Piece | What it is | Where it lives | How the container sees it |
|---|---|---|---|
| **Environment** | ANTs 2.5.0, FSL 6.0.7, FreeSurfer 7.4.1, AFNI 23.2.04 (+ MATLAB/CAT12 in the as-run image only) | the `.sif` image | the image itself |
| **Scripts** | `setup.sh`, `step1_…sh`, `step2_…sh`, `step2.5_…sh`, `step3_…sh` | **host**, at the root of your data directory | bind-mounted to `/mnt/` |
| **Data** | the age/sex-stratified inputs (`Age5..18/{male,female}/…`) | **host**, same data directory | bind-mounted to `/mnt/` |

The scripts and the data share one host directory (call it `$DB`). That directory is
bind-mounted to `/mnt` inside the container. So inside the container:

* data is at `/mnt/Age9/male/…`
* the pipeline scripts are at `/mnt/step1_uh_ped_temp_preprocess.sh`, `/mnt/setup.sh`, …

**This is the key step people miss: you must copy the pipeline scripts into the root
of `$DB` so they appear at `/mnt/…` next to the data.** The container has the tools;
the scripts ride in through the data bind.

The exact call the orchestrator makes (from `01_preprocessing/process_subject_s1.sh`):

```bash
apptainer exec \
    --bind $UNIQUE_TEMP_DIR:/writabletemp \   # a per-job writable scratch dir
    --bind /share:/share \                    # host software (MATLAB) — as-run path only
    --bind $DB:/mnt \                         # your data+scripts root -> /mnt
    $IMAGE /bin/bash -c "
        source /mnt/setup.sh && \
        export SUBJECTS_DIR=$CCS_DIR && \
        /bin/sh /mnt/step1_uh_ped_temp_preprocess.sh $CCS_DIR $SUBJECTS_DIR $subject 1"
```

Three binds, every time:

* **`$DB:/mnt`** — your data root *and* the scripts (this is the non-obvious one).
* **`<scratch>:/writabletemp`** — a writable temp dir. SLURM's `$TMPDIR=/scratch/$JOBID`
  is **not** visible inside the container, so you must bind an explicit writable dir and
  `export TMPDIR=/writabletemp`, or `mktemp` fails and paths collapse to `/m0.nii.gz`.
* **`/share:/share`** — only for the **as-run (MATLAB)** path; it exposes the host's
  MATLAB install. Not needed for the license-free path (below).

---

## 2. Two ways to reproduce — pick one

### Path A — license-free (recommended)

No MATLAB, no `/share` bind. The CAT12 SANLM denoise step is replaced by ANTs
`DenoiseImage` (same Manjón 2010 algorithm). Build the image from the `Dockerfile`
in this directory:

```bash
# 1. Build the environment image
docker build -t cast-pipeline:1.0.0 container/
apptainer build cast_pipeline.sif docker-daemon://cast-pipeline:1.0.0
#   (or, if you only have Docker: run everything under docker instead of apptainer)

# 2. Lay out your data root ($DB) with BOTH data and scripts at the top level
#      $DB/Age5/male/... , $DB/Age5/female/... , ...          <- your inputs
#      $DB/setup.sh                                            <- from container/setup.sh.example
#      $DB/step1_uh_ped_temp_preprocess.sh                    <- from 01_preprocessing/
#      $DB/step2_uh_ped_temp_preprocess.sh
#      $DB/step2.5_uh_ped_temp_recenter.sh
#      $DB/step3_uh_ped_temp_preprocess.sh
cp 01_preprocessing/step*.sh  "$DB"/
cp container/setup.sh.example "$DB"/setup.sh     # portable; no MATLAB

# 3. Point config.sh at your paths and run one subject
export DB=/your/data/root
export IMAGE_DIR=/dir/holding/the/sif
export C_PREPROC=$IMAGE_DIR/cast_pipeline.sif    # same image for both phases here
export C_REG=$IMAGE_DIR/cast_pipeline.sif
source config.sh
bash 01_preprocessing/process_subject_s1.sh <age> <gender> <subjectID>
```

FreeSurfer needs a (free) licence file at run time — it is **not** redistributable in
the image. Put your `license.txt` where FreeSurfer expects it and bind it in, e.g.
`--bind $PWD/license.txt:/opt/freesurfer/license.txt`.

### Path B — exact as-run reproduction (needs a MATLAB licence)

The templates were built with CAT12 v12.9 SANLM under **MATLAB R2023b**, provided by
the **host** cluster (not bundled), reached through the `/share` bind. Use this path
only if you must reproduce byte-for-byte and you have MATLAB R2023b.

```bash
docker pull bifeitangmac/mri_template_env_matlab:<IMMUTABLE_TAG>   # see note in §4
apptainer build cast_reg.sif docker://bifeitangmac/mri_template_env_matlab:<IMMUTABLE_TAG>
```

Then:

* bind your host MATLAB tree at `/share` (`--bind /share:/share`), and
* provide a `setup.sh` at `$DB/setup.sh` that puts that MATLAB on `PATH`/`LD_LIBRARY_PATH`.
  The as-run `setup.sh` was **specific to the UH _carya_ cluster** (it hard-codes
  `/share/apps/matlab-r2023b`, cluster EasyBuild library paths, and even another user's
  home dir). **It is not portable** — you must rewrite it for your site. That is why it
  is not shipped verbatim; `container/setup.sh.example` is the portable, MATLAB-free
  starting point.

---

## 3. `setup.sh` — what it must do

`step1…step3` all begin with `source /mnt/setup.sh`, so a `setup.sh` **must exist at the
root of `$DB`** or every stage fails with "setup.sh: No such file or directory". Its job
is to make the tools findable *inside the container* and (Path B only) wire up host MATLAB.

For the **license-free** image the tools are already on `PATH` from the Dockerfile, so
`setup.sh` only needs to source FSL and set a couple of variables — see
`container/setup.sh.example` in this directory (added alongside this document).

---

## 4. Base image and known gaps (read before depositing)

* **Base image.** The as-run image and the license-free `Dockerfile` are both
  **Ubuntu 22.04** (confirmed by the `.sif` labels —
  `org.opencontainers.image.ref.name: ubuntu`, `version: 22.04` — and by the build log,
  which shows layers `Mounted from amd64/ubuntu`).
  ⚠️ **I could not find any image or base called "Odoso"** in the `.sif` metadata, the
  `Dockerfile`, or the build log (`terminal_log/step2_docker.txt`). If the as-run image
  was derived from a specific upstream base by that name, please confirm it — it does not
  change the license-free build, which is `FROM ubuntu:22.04` directly.

* **The as-run image tag is mutable.** `container/README.md` already flags this: the
  as-run image was built with `docker commit` and tagged `:activated`/`:reg`. Before you
  cite it in the paper, **re-tag it immutably and publish the digest**:

  ```bash
  docker tag  bifeitangmac/mri_template_env_matlab:reg bifeitangmac/mri_template_env_matlab:1.0.0
  docker push bifeitangmac/mri_template_env_matlab:1.0.0
  docker inspect --format='{{index .RepoDigests 0}}' bifeitangmac/mri_template_env_matlab:1.0.0
  # -> cite this sha256 digest in the paper's Code Availability, not a bare image name
  ```

* **`[VERIFY]` pins in the `Dockerfile`.** The AFNI tarball and a couple of installer
  URLs are marked `[VERIFY]` because they reproduce versions from the build log rather
  than pinned digests. Test-build the image once and pin the exact URLs/SHAs your network
  resolves before depositing.

* **`setup.sh` was missing from the repo.** The step scripts source `/mnt/setup.sh`, but
  no `setup.sh` shipped. A portable, MATLAB-free `setup.sh.example` is added in this
  directory to close that gap; the as-run carya version is intentionally not shipped
  (non-portable, contains site-specific and third-party paths).
