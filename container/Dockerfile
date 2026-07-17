# =============================================================================
# CAST pediatric MRI template pipeline — reproducible, license-FREE build
# =============================================================================
# Reconstructs the processing environment used to build the CAST template
# library, with ONE deliberate substitution for reproducibility:
#   * the as-run pipeline denoised with CAT12 v12.9 SANLM under MATLAB R2023b;
#   * this image instead performs SANLM with ANTs `DenoiseImage`, which
#     implements the same Manjon (2010) spatially-adaptive non-local-means
#     algorithm and needs NO MATLAB license.
# The exact as-run (MATLAB) environment is published separately as
#   docker pull bifeitangmac/mri_template_env_matlab:<immutable-tag>
# See container/README.md for the as-run path and the SANLM equivalence note.
#
# NOTE: lines marked [VERIFY] reproduce versions/URLs from the build log
# (terminal_log/step2_docker.txt); test-build before depositing and pin the
# exact upstream URLs/SHAs your network resolves.
# =============================================================================
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# ---- system dependencies --------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        bc ca-certificates curl wget git unzip tar xz-utils \
        build-essential cmake g++ make \
        tcsh perl python3 python3-pip python3-dev \
        libgomp1 libglu1-mesa libxmu6 libxt6 libgl1-mesa-glx libjpeg62 \
    && rm -rf /var/lib/apt/lists/*

# ---- FSL 6.0.7 ------------------------------------------------------------
# [VERIFY] fslinstaller pins the release; FSLDIR fixed at /opt/fsl
RUN wget -q https://fsl.fmrib.ox.ac.uk/fsldownloads/fslconda/releases/fslinstaller.py -O /tmp/fslinstaller.py \
 && python3 /tmp/fslinstaller.py -d /opt/fsl -V 6.0.7 -q \
 && rm -f /tmp/fslinstaller.py
ENV FSLDIR=/opt/fsl FSLOUTPUTTYPE=NIFTI_GZ
ENV PATH=$FSLDIR/bin:$PATH

# ---- AFNI 23.2.04 ---------------------------------------------------------
# [VERIFY] pin the exact dated build that reports 23.2.04
RUN mkdir -p /opt/afni \
 && curl -fsSL https://afni.nimh.nih.gov/pub/dist/tgz/linux_ubuntu_22_64.tgz \
    | tar -xz -C /opt/afni --strip-components=1
ENV PATH=/opt/afni:$PATH

# ---- ANTs 2.5.0 (built from source, as in the original /opt/ants-build) ---
RUN git clone https://github.com/ANTsX/ANTs.git /tmp/ANTs \
 && cd /tmp/ANTs && git checkout v2.5.0 \
 && mkdir -p /tmp/ants-build && cd /tmp/ants-build \
 && cmake -DCMAKE_INSTALL_PREFIX=/opt/ants -DBUILD_TESTING=OFF /tmp/ANTs \
 && make -j"$(nproc)" \
 && cd ANTS-build && make install \
 && rm -rf /tmp/ANTs /tmp/ants-build
ENV ANTSPATH=/opt/ants/bin
ENV PATH=$ANTSPATH:$PATH

# ---- FreeSurfer 7.4.1 -----------------------------------------------------
# [VERIFY] build log shows /usr/local/freesurfer/7.4.1; a valid license.txt
# must be bind-mounted at runtime: -v license.txt:/opt/freesurfer/license.txt
RUN curl -fsSL https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/freesurfer-linux-ubuntu22_amd64-7.4.1.tar.gz \
    | tar -xz -C /opt
ENV FREESURFER_HOME=/opt/freesurfer
ENV PATH=$FREESURFER_HOME/bin:$PATH

# ---- Python: QC, orchestration, skull-stripping ---------------------------
# [VERIFY] mriqc 0.16.1 (IQM extraction) may need an isolated venv; pin deps
RUN pip3 install --no-cache-dir \
        "nibabel>=5,<6" numpy scipy pandas scikit-image \
 && pip3 install --no-cache-dir deepbet     # DeepBET: wwu-mmll/DeepBET (LinkNet+U-Net)

# SANLM is provided by ANTs DenoiseImage (no MATLAB/CAT12 in this image).
WORKDIR /work
LABEL org.opencontainers.image.title="cast-pipeline" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="CAST pediatric MRI template pipeline (license-free build; SANLM via ANTs DenoiseImage)" \
      org.opencontainers.image.licenses="MIT"
