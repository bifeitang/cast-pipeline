#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_wm_fractal_dimension.py
================================
Generator for the white-matter--surface fractal dimension (the ``fd`` field) in
``template_morphometry.jsonl`` (CAST) and ``nki_morphometry.jsonl`` (Dong/NKI).

This script closes a reproducibility gap in the CAST Scientific Data descriptor:
the ``fd`` values were committed as artifacts but the routine that computes them
was missing from the repository.  It is also the prerequisite for the
common-grid resampling robustness check (``--resample``) described in
``01_Manuscript/_review_workspace/04_fd_stats_hardening.md`` §3(b).

ALGORITHM (3D box-counting / Minkowski-Bouligand dimension of the WM surface)
----------------------------------------------------------------------------
For each template:

  1. INPUT = a binarized white-matter probability mask at the template's NATIVE
     resolution.
       * NKI (Dong): the deposited FSL-FAST white-matter partial-volume estimate
         ``NKI_age{N}_template_pve_2.nii.gz`` (a WM probability map in [0, 1]).
       * CAST: no WM probability map is deposited alongside the intensity
         templates, so one is derived in-script by a *deterministic* 3-class
         multi-Otsu segmentation of the CSF-anchored intensity template
         (``skimage.filters.threshold_multiotsu``, ``classes=3`` ->
         CSF / GM / WM); the white-matter class is the membership map.
     BINARIZATION THRESHOLD = 0.5 (WM probability >= 0.5; for the CAST multi-Otsu
     map this is equivalently "intensity above the upper Otsu cut").

  2. SURFACE = the 26-connected boundary of the binary WM volume: voxels that
     belong to WM and have at least one background voxel among their 26
     neighbours, i.e. ``WM & ~binary_erosion(WM, 3x3x3 full structuring
     element)``.

  3. BOX-COUNTING = partition the volume into non-overlapping cubic boxes of
     edge ``s`` voxels (corner-anchored grid; the array is zero-padded so each
     dimension is a multiple of ``s``) and count ``N(s)`` = number of boxes that
     contain >= 1 surface voxel, for the dyadic BOX SIZES
         s in {1, 2, 4, 8, 16}   (voxels, on the native grid).

  4. FRACTAL DIMENSION = -slope of an ordinary-least-squares straight-line fit of
     ``log N(s)`` vs ``log s`` over the FULL set of box sizes {1, 2, 4, 8, 16}
     (the LOG-LOG REGRESSION RANGE).  The coefficient of determination R^2 of
     this fit is reported alongside as a goodness-of-scaling diagnostic.

Box sizes are specified in VOXELS (not millimetres); FD is therefore evaluated on
each template's native sampling grid.  This makes the estimate mildly
resolution-dependent (a finer grid resolves more boundary detail), which is the
confound analysed and controlled for in ``04_fd_stats_hardening.md`` §3 -- use
``--resample`` to recompute every mask on a common isotropic grid.

VALIDATION.  On the NKI side, where the WM probability mask (FSL-FAST pve_2) is
deposited and therefore fully determined, this recipe reproduces the committed
``fd`` series to mean-absolute-error ~0.0035 (max ~0.010), i.e. to within
rounding at two decimals -- confirming the box-counting estimator.  The CAST
values are regenerated from the in-script segmentation and may differ from any
earlier (undeposited) FSL-FAST-based computation by ~0.03 on average; this is the
deliberate, documented consequence of making the metric reproducible from the
deposited data alone.  The qualitative result is unchanged: CAST > NKI in every
overlapping age (see ``--check``).

USAGE
-----
    python compute_wm_fractal_dimension.py            # compute + print a table
    python compute_wm_fractal_dimension.py --write    # also update the two .jsonl fd fields (backs up first)
    python compute_wm_fractal_dimension.py --check     # compare to committed fd, no writes
    python compute_wm_fractal_dimension.py --csv out.csv          # write a detailed per-template CSV
    python compute_wm_fractal_dimension.py --resample 1.0          # common-grid (1.0 mm) robustness pass

Dependencies: numpy, scipy, nibabel, scikit-image.  Fully deterministic
(no random seeds); multi-Otsu is histogram-based and version-stable.

Author: regenerated for the CAST descriptor (technical validation), 2026-06.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime

import numpy as np
import nibabel as nib
from scipy.ndimage import binary_erosion, generate_binary_structure
from skimage.filters import threshold_multiotsu

# --------------------------------------------------------------------------- #
# Documented parameters (the technical-validation recipe).                     #
# --------------------------------------------------------------------------- #
BOX_SIZES = (1, 2, 4, 8, 16)        # dyadic box edge lengths, in voxels
FIT_LO, FIT_HI = 1, 16              # log-log regression range (inclusive), in voxels
BINARIZE_THRESHOLD = 0.5           # WM probability >= 0.5
SURFACE_CONNECTIVITY = 3           # scipy generate_binary_structure rank: 3 -> 26-connectivity
N_TISSUE_CLASSES = 3               # CAST in-script segmentation: CSF / GM / WM

# --------------------------------------------------------------------------- #
# Repository layout (resolved relative to this file so the script is portable).#
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))   # .../Qualifier PediatricMRITemplate

CAST_JSONL = os.path.join(HERE, "template_morphometry.jsonl")
NKI_JSONL = os.path.join(HERE, "nki_morphometry.jsonl")

# The 26-template CAST library (intensity templates; ages 5-15,17,18 x M/F).
CAST_TEMPLATE_DIR = os.path.join(
    REPO, "08_Working_Temp", "InspectionTemp", "UpdatedTemplates"
)
CAST_TEMPLATE_FMT = "{name}_template.nii.gz"          # e.g. age8_male_template.nii.gz

# OPTIONAL: if the original CAST white-matter probability maps (warped + averaged
# FSL-FAST tissue maps, see descriptor "Tissue segmentation overlap") are ever
# deposited here as "{name}_wm.nii.gz", they are used directly (binarized at 0.5)
# in preference to the in-script multi-Otsu segmentation -- making the CAST and
# NKI sides fully symmetric.  Until then this directory is absent and CAST falls
# back to multi-Otsu (see wm_mask_from_intensity).
CAST_WM_PROB_DIR = os.path.join(HERE, "cast_wm_prob")
CAST_WM_PROB_FMT = "{name}_wm.nii.gz"

# The Dong/NKI reference WM probability maps (FSL-FAST pve_2).
NKI_TISSUE_DIR = os.path.join(
    REPO, "06_Data", "CCS_Dong", "CCS-master", "H3",
    "GrowthCharts", "Templates", "NKI", "Tissue"
)
NKI_PVE2_FMT = "NKI_age{age}_template_pve_2.nii.gz"   # age7 -> age6a7 (see nki_age_token)


# --------------------------------------------------------------------------- #
# I/O helpers.                                                                 #
# --------------------------------------------------------------------------- #
def load_volume(path):
    """Return (data[float32, 3D], zooms[3]) for a NIfTI file (drops trailing axes)."""
    img = nib.load(path)
    data = np.asarray(img.dataobj, dtype=np.float32)
    while data.ndim > 3:
        data = data[..., 0]
    zooms = tuple(float(z) for z in img.header.get_zooms()[:3])
    return data, zooms


def nki_age_token(name):
    """Map a jsonl NKI name to its Dong file token. 'NKI_age7' -> '6a7'; else the bare age."""
    age = name.split("age")[1]
    return "6a7" if age == "7" else age


# --------------------------------------------------------------------------- #
# WM mask derivation.                                                          #
# --------------------------------------------------------------------------- #
def wm_mask_from_probability(prob, threshold=BINARIZE_THRESHOLD):
    """Binarize a WM probability/partial-volume map (NKI pve_2)."""
    return prob >= threshold


def wm_mask_from_intensity(intensity, n_classes=N_TISSUE_CLASSES):
    """Deterministic in-script WM mask for CAST: top class of a multi-Otsu
    3-class segmentation of the brain (non-zero) voxels of an intensity template."""
    brain = intensity[intensity > 0]
    thresholds = threshold_multiotsu(brain, classes=n_classes)  # n_classes-1 cuts
    return intensity > thresholds[-1]                            # WM = brightest class


# --------------------------------------------------------------------------- #
# Box-counting fractal dimension.                                             #
# --------------------------------------------------------------------------- #
def surface_voxels(binary, connectivity=SURFACE_CONNECTIVITY):
    """Boundary of a binary volume: foreground voxels adjacent to background."""
    struct = generate_binary_structure(3, connectivity)
    return binary & ~binary_erosion(binary, struct)


def occupied_boxes(binary_set, s):
    """Number of non-overlapping s x s x s boxes (corner-anchored, zero-padded)
    that contain at least one True voxel."""
    if s == 1:
        return int(binary_set.sum())
    pad = [(0, (-d) % s) for d in binary_set.shape]
    padded = np.pad(binary_set, pad)
    nx, ny, nz = (d // s for d in padded.shape)
    blocks = padded.reshape(nx, s, ny, s, nz, s)
    return int(blocks.any(axis=(1, 3, 5)).sum())


def fractal_dimension(binary_wm, box_sizes=BOX_SIZES, fit_lo=FIT_LO, fit_hi=FIT_HI,
                      connectivity=SURFACE_CONNECTIVITY):
    """Return (fd, r2, counts) for a binary WM volume via surface box-counting."""
    surf = surface_voxels(binary_wm, connectivity)
    sizes = np.asarray(box_sizes, dtype=float)
    counts = np.array([occupied_boxes(surf, int(s)) for s in sizes], dtype=float)
    mask = (sizes >= fit_lo) & (sizes <= fit_hi) & (counts > 0)
    x, y = np.log(sizes[mask]), np.log(counts[mask])
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1.0 - np.sum(resid ** 2) / ss_tot if ss_tot > 0 else float("nan")
    return float(-slope), float(r2), {int(s): int(c) for s, c in zip(box_sizes, counts)}


# --------------------------------------------------------------------------- #
# Optional resampling to a common isotropic grid (robustness check, §3b).      #
# --------------------------------------------------------------------------- #
def resample_to_isotropic(data, zooms, target_mm, order=0):
    """Nearest-neighbour (order=0) / linear resample to an isotropic target_mm grid.
    Used on the *probability/intensity* map BEFORE binarization so the same fixed
    threshold is applied on every grid (per §3b: identical interpolation + fixed
    threshold + same box sizes)."""
    from scipy.ndimage import zoom as ndi_zoom
    factors = [z / target_mm for z in zooms]
    return ndi_zoom(data, factors, order=order), (target_mm, target_mm, target_mm)


# --------------------------------------------------------------------------- #
# Per-template computation.                                                    #
# --------------------------------------------------------------------------- #
def compute_one(record, family, resample_mm=None):
    """Compute fd for one jsonl record. family in {'CAST','NKI'}.
    Returns a dict of results (or raises FileNotFoundError if the input is missing)."""
    name = record["name"]
    if family == "CAST":
        prob_path = os.path.join(CAST_WM_PROB_DIR, CAST_WM_PROB_FMT.format(name=name))
        if os.path.exists(prob_path):                 # deposited WM probability map -> use it
            path = prob_path
            data, zooms = load_volume(path)
            if resample_mm is not None:
                data, zooms = resample_to_isotropic(data, zooms, resample_mm, order=1)
            wm = wm_mask_from_probability(data)
        else:                                          # fall back to in-script multi-Otsu
            path = os.path.join(CAST_TEMPLATE_DIR, CAST_TEMPLATE_FMT.format(name=name))
            data, zooms = load_volume(path)
            if resample_mm is not None:
                data, zooms = resample_to_isotropic(data, zooms, resample_mm, order=1)
            wm = wm_mask_from_intensity(data)
    elif family == "NKI":
        path = os.path.join(NKI_TISSUE_DIR, NKI_PVE2_FMT.format(age=nki_age_token(name)))
        data, zooms = load_volume(path)
        if resample_mm is not None:
            data, zooms = resample_to_isotropic(data, zooms, resample_mm, order=1)
        wm = wm_mask_from_probability(data)
    else:
        raise ValueError(family)

    fd, r2, counts = fractal_dimension(wm)
    vox_mm = round(float(zooms[0]), 4)
    return {
        "name": name, "family": family, "source": os.path.relpath(path, REPO),
        "vox_mm": vox_mm, "wm_voxels": int(wm.sum()),
        "wm_ml": round(float(wm.sum()) * float(np.prod(zooms)) / 1000.0, 1),
        "surface_voxels": counts[BOX_SIZES[0]],
        "fd": round(fd, 3), "fd_raw": fd, "r2": round(r2, 5),
        "counts": counts,
    }


def load_jsonl(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def compute_all(resample_mm=None):
    cast = [compute_one(r, "CAST", resample_mm) for r in load_jsonl(CAST_JSONL)]
    nki = [compute_one(r, "NKI", resample_mm) for r in load_jsonl(NKI_JSONL)]
    return cast, nki


# --------------------------------------------------------------------------- #
# jsonl updating (preserves field order and every other field).                #
# --------------------------------------------------------------------------- #
def update_jsonl_fd(path, results):
    by_name = {r["name"]: r for r in results}
    records = load_jsonl(path)
    changed = []
    for rec in records:
        if rec["name"] in by_name:
            new = by_name[rec["name"]]["fd"]
            if rec.get("fd") != new:
                changed.append((rec["name"], rec.get("fd"), new))
            rec["fd"] = new
    backup = path + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, backup)
    with open(path, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return changed, backup


# --------------------------------------------------------------------------- #
# Reporting.                                                                    #
# --------------------------------------------------------------------------- #
def _age(name):
    return int(re.search(r"age(\d+)", name).group(1)) if "6a7" not in name else 7


def print_table(cast, nki):
    print(f"{'name':14} {'fam':4} {'vox':>4} {'wm_ml':>7} {'surf_vox':>9} {'fd':>6} {'R2':>7}")
    for r in cast + nki:
        print(f"{r['name']:14} {r['family']:4} {r['vox_mm']:>4} {r['wm_ml']:>7} "
              f"{r['surface_voxels']:>9} {r['fd']:>6.3f} {r['r2']:>7.4f}")
    cm = np.mean([r["fd_raw"] for r in cast]); nm = np.mean([r["fd_raw"] for r in nki])
    print(f"\nCAST mean fd = {cm:.3f} (n={len(cast)});  NKI mean fd = {nm:.3f} (n={len(nki)});  "
          f"gap = {cm - nm:+.3f}")


def print_check(cast, nki):
    """Compare regenerated fd to the committed fd in the jsonl files."""
    committed = {r["name"]: r.get("fd") for r in load_jsonl(CAST_JSONL) + load_jsonl(NKI_JSONL)}
    devs = []
    print(f"{'name':14} {'committed':>9} {'regen':>7} {'Δ':>7}")
    for r in cast + nki:
        old = committed.get(r["name"])
        if old is None:
            continue
        d = r["fd"] - old
        devs.append(abs(d))
        print(f"{r['name']:14} {old:>9.3f} {r['fd']:>7.3f} {d:>+7.3f}")
    cast_dev = [abs(r["fd"] - committed[r["name"]]) for r in cast if r["name"] in committed]
    nki_dev = [abs(r["fd"] - committed[r["name"]]) for r in nki if r["name"] in committed]
    print(f"\nCAST  MAE={np.mean(cast_dev):.4f}  max={np.max(cast_dev):.4f}")
    print(f"NKI   MAE={np.mean(nki_dev):.4f}  max={np.max(nki_dev):.4f}")

    # Paired direction over overlapping ages (sex-averaged CAST vs NKI).
    nki_by_age = {_age(r["name"]): r["fd_raw"] for r in nki}
    overlap = sorted(set(_age(r["name"]) for r in cast) & set(nki_by_age))
    wins = 0
    for a in overlap:
        cvals = [r["fd_raw"] for r in cast if _age(r["name"]) == a]
        if np.mean(cvals) > nki_by_age[a]:
            wins += 1
    print(f"Paired (sex-avg CAST vs NKI): CAST > NKI in {wins}/{len(overlap)} overlapping ages "
          f"({', '.join(map(str, overlap))})")


def write_csv(path, cast, nki):
    fields = ["name", "family", "vox_mm", "wm_voxels", "wm_ml", "surface_voxels",
              "fd", "r2"] + [f"N_s{s}" for s in BOX_SIZES] + ["source"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for r in cast + nki:
            row = [r["name"], r["family"], r["vox_mm"], r["wm_voxels"], r["wm_ml"],
                   r["surface_voxels"], r["fd"], r["r2"]] + \
                  [r["counts"][s] for s in BOX_SIZES] + [r["source"]]
            w.writerow(row)
    print(f"wrote {path}")


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="update the 'fd' field in the two committed jsonl files (backs up first)")
    ap.add_argument("--check", action="store_true",
                    help="compare regenerated fd to committed fd; report deviations and paired direction")
    ap.add_argument("--csv", metavar="PATH", default=None,
                    help="write a detailed per-template CSV (fd, R2, box counts, source)")
    ap.add_argument("--resample", metavar="MM", type=float, default=None,
                    help="resample every mask to a common isotropic grid (mm) before FD (robustness, §3b)")
    args = ap.parse_args(argv)

    print(f"# WM-surface fractal dimension generator")
    print(f"# box sizes (vox) = {list(BOX_SIZES)}; fit range = [{FIT_LO},{FIT_HI}]; "
          f"threshold = {BINARIZE_THRESHOLD}; surface = 26-connectivity")
    if args.resample:
        print(f"# RESAMPLED to common grid: {args.resample} mm isotropic (linear interp, fixed threshold)")
    print()

    cast, nki = compute_all(resample_mm=args.resample)
    print_table(cast, nki)

    if args.csv:
        write_csv(args.csv, cast, nki)
    if args.check:
        print()
        print_check(cast, nki)
    if args.write:
        if args.resample:
            sys.exit("refusing to --write resampled (non-native) fd into the committed jsonl")
        print()
        for path, res in ((CAST_JSONL, cast), (NKI_JSONL, nki)):
            changed, backup = update_jsonl_fd(path, res)
            print(f"updated {os.path.basename(path)}: {len(changed)} fd values changed "
                  f"(backup: {os.path.basename(backup)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
