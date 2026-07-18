# Tissue-probability maps + OpenNeuro packaging

- `make_tissue_maps.sbatch` — generates the released GM/WM/CSF tissue-probability
  maps by 3-class FSL FAST segmentation of each native group-average template
  (`_pve_0/1/2` → CSF/GM/WM), and the brain masks via ANTs `ImageMath`
  (ThresholdAtMean → erode → dilate → largest-component → fill-holes). Paths are
  parameterized: set `$DB`, `$WORK`, `$IMG`. Note: inside the container,
  `export TMPDIR` to a bind-mounted writable dir (SLURM's `/scratch/$JOBID` is not
  visible in the container and breaks `mktemp`).
- `package_openneuro_deposit.py` — maps the templates+masks+TPMs into the
  `tpl-BRAINCAST_age-NN_sex-{F,M}_*` BIDS-derivative deposit layout with
  SHA-256 checksums; refuses to build unless all 140 files (28 × 5) are present.
