#!/usr/bin/env python3
"""
Measure "brain size" (brain volume) per subject across ages.

This crawls subject NIfTI images under:
  <db-root>/AgeN/<sex>/intensity_improved_selected_for_template/*.nii.gz

and writes:
  - per-subject CSV (one row per image)
  - per-age summary CSV (mean/std/n per age, per sex)
  - optional PNG plot (mean brain volume vs age)

Masking strategy:
  - If a corresponding mask file exists next to the image, use it.
  - Otherwise, compute an automatic mask using an Otsu threshold on non-background voxels,
    then keep the largest connected component (scipy optional) and fill holes (scipy optional).

Dependencies: numpy, nibabel, matplotlib (optional; only if --out-plot is used)
Optional: scipy (for largest component + hole filling cleanup)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


AGE_DIR_RE = re.compile(r"^Age(?P<age>\d+)$")


def die_missing_deps() -> None:
    raise SystemExit(
        "Missing dependencies. Please load a python env with nibabel/numpy, e.g.\n"
        "  pip install --user nibabel numpy\n"
        "Optional: matplotlib (for plotting), scipy (for mask cleanup)\n"
    )


try:
    import numpy as np  # type: ignore
    import nibabel as nib  # type: ignore
    from nibabel.processing import resample_from_to  # type: ignore
except Exception:
    die_missing_deps()


try:
    import scipy.ndimage as ndi  # type: ignore

    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


@dataclass(frozen=True)
class SubjectEntry:
    age: int
    sex: str
    subject_id: str
    image_path: str
    mask_path: Optional[str]


def _as_canonical(img: "nib.Nifti1Image") -> "nib.Nifti1Image":
    try:
        return nib.as_closest_canonical(img)
    except Exception:
        return img


def _voxel_volume_mm3(img: "nib.Nifti1Image") -> float:
    zooms = img.header.get_zooms()[:3]
    return float(zooms[0] * zooms[1] * zooms[2])


def _otsu_threshold_1d(x: np.ndarray, bins: int = 256) -> float:
    """
    Otsu threshold for a 1D distribution.
    """
    x = x[np.isfinite(x)].astype(np.float64, copy=False)
    if x.size == 0:
        return 0.0
    xmin = float(np.min(x))
    xmax = float(np.max(x))
    if not np.isfinite(xmin) or not np.isfinite(xmax) or xmax <= xmin:
        return xmin

    hist, edges = np.histogram(x, bins=bins, range=(xmin, xmax))
    hist = hist.astype(np.float64, copy=False)
    p = hist / (hist.sum() + 1e-12)
    omega = np.cumsum(p)
    centers = (edges[:-1] + edges[1:]) / 2.0
    mu = np.cumsum(p * centers)
    mu_t = mu[-1]

    denom = omega * (1.0 - omega) + 1e-12
    sigma_b2 = (mu_t * omega - mu) ** 2 / denom
    idx = int(np.nanargmax(sigma_b2))
    return float(centers[idx])


def _keep_largest_component(mask: np.ndarray) -> np.ndarray:
    if not _HAVE_SCIPY:
        return mask
    lab, n = ndi.label(mask)
    if n <= 1:
        return mask
    counts = np.bincount(lab.ravel())
    counts[0] = 0
    keep = int(np.argmax(counts))
    return lab == keep


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    if not _HAVE_SCIPY:
        return mask
    return ndi.binary_fill_holes(mask)


def _auto_mask_from_image(img: "nib.Nifti1Image") -> Tuple[np.ndarray, float, str]:
    """
    Returns (mask_bool, threshold, method).
    """
    data = img.get_fdata(dtype=np.float32)

    # Heuristic "background" removal: ignore near-zero voxels to make Otsu stable on skull-stripped-ish images.
    finite = np.isfinite(data)
    if not np.any(finite):
        return np.zeros(data.shape, dtype=bool), 0.0, "otsu_nonzero"

    abs_data = np.abs(data[finite])
    # Adaptive epsilon: robust small value from distribution (handles scaled images)
    eps = float(np.percentile(abs_data, 1)) * 0.1
    if not np.isfinite(eps) or eps <= 0:
        eps = 0.0

    fg = finite & (np.abs(data) > eps)
    x = data[fg]
    thr = _otsu_threshold_1d(x)

    mask = finite & (data > thr)
    mask = _keep_largest_component(mask)
    mask = _fill_holes(mask)
    return mask, thr, "otsu_nonzero"


def _maybe_load_mask(mask_path: str, ref_img: "nib.Nifti1Image") -> np.ndarray:
    m_img0 = nib.load(mask_path)
    m_img = _as_canonical(m_img0)
    ref = _as_canonical(ref_img)

    # If geometry differs, resample mask to image space
    if m_img.shape != ref.shape or not np.allclose(m_img.affine, ref.affine, atol=1e-4):
        m_img = resample_from_to(m_img, ref, order=0)

    m = m_img.get_fdata(dtype=np.float32)
    return np.isfinite(m) & (m > 0.5)


def _candidate_mask_paths(img_path: str) -> List[str]:
    """
    Common mask naming conventions next to the subject image.
    """
    d = os.path.dirname(img_path)
    base = os.path.basename(img_path)
    stem = base[:-7] if base.endswith(".nii.gz") else os.path.splitext(base)[0]
    cands = [
        os.path.join(d, f"{stem}_brain_mask.nii.gz"),
        os.path.join(d, f"{stem}_brainmask.nii.gz"),
        os.path.join(d, f"{stem}_mask.nii.gz"),
        os.path.join(d, f"{stem}_BrainExtractionMask.nii.gz"),
    ]
    # also allow generic directory-level masks (rare, but harmless to check)
    cands += [
        os.path.join(d, "brain_mask.nii.gz"),
        os.path.join(d, "mask.nii.gz"),
    ]
    # Unique while preserving order
    out: List[str] = []
    seen = set()
    for p in cands:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _discover_age_dirs(db_root: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for name in os.listdir(db_root):
        m = AGE_DIR_RE.match(name)
        if not m:
            continue
        age = int(m.group("age"))
        out.append((age, os.path.join(db_root, name)))
    out.sort(key=lambda t: t[0])
    return out


def _iter_subject_images(
    db_root: str,
    sex: str,
    subdir: str,
    ages: Optional[Sequence[int]] = None,
) -> Iterable[SubjectEntry]:
    ages_set = set(ages) if ages is not None else None

    for age, age_dir in _discover_age_dirs(db_root):
        if ages_set is not None and age not in ages_set:
            continue

        sex_dir = os.path.join(age_dir, sex, subdir)
        if not os.path.isdir(sex_dir):
            continue

        for fn in sorted(os.listdir(sex_dir)):
            if not fn.endswith(".nii.gz"):
                continue
            if fn.endswith("_brain_mask.nii.gz") or fn.endswith("_mask.nii.gz"):
                continue
            # Subject ID is the filename stem
            subject_id = fn[:-7]
            img_path = os.path.join(sex_dir, fn)
            mask_path = next((p for p in _candidate_mask_paths(img_path) if os.path.exists(p)), None)
            yield SubjectEntry(
                age=age,
                sex=sex,
                subject_id=subject_id,
                image_path=img_path,
                mask_path=mask_path,
            )


def write_csv(path: str, rows: List[Dict[str, str]], fieldnames: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames))
        w.writeheader()
        w.writerows(rows)


def _mean_std(x: Sequence[float]) -> Tuple[float, float]:
    if len(x) == 0:
        return 0.0, 0.0
    arr = np.asarray(x, dtype=np.float64)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if arr.size >= 2 else 0.0
    return mean, std


def parse_age_list(s: str) -> List[int]:
    """
    Accepts:
      - "5-18"
      - "5,6,7,9"
      - "5-10,12,15-18"
    """
    out: List[int] = []
    for part in (p.strip() for p in s.split(",") if p.strip()):
        if "-" in part:
            a, b = part.split("-", 1)
            lo = int(a)
            hi = int(b)
            if hi < lo:
                lo, hi = hi, lo
            out.extend(list(range(lo, hi + 1)))
        else:
            out.append(int(part))
    # unique sorted
    return sorted(set(out))


def maybe_plot(out_plot: str, summary_rows: List[Dict[str, str]]) -> None:
    if not out_plot:
        return
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        raise SystemExit("matplotlib is required for --out-plot (pip install --user matplotlib)")

    by_sex: Dict[str, List[Tuple[int, float, float]]] = {}
    for r in summary_rows:
        age = int(r["age"])
        sex = r["sex"]
        mean_ml = float(r["mean_brain_volume_ml"])
        std_ml = float(r["std_brain_volume_ml"])
        by_sex.setdefault(sex, []).append((age, mean_ml, std_ml))
    for sex in by_sex:
        by_sex[sex].sort(key=lambda t: t[0])

    os.makedirs(os.path.dirname(os.path.abspath(out_plot)) or ".", exist_ok=True)
    plt.figure(figsize=(7.5, 4.5))
    for sex, pts in by_sex.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        es = [p[2] for p in pts]
        plt.errorbar(xs, ys, yerr=es, marker="o", linewidth=2, capsize=3, label=sex)
    plt.xlabel("Age")
    plt.ylabel("Brain volume (mL)")
    plt.title("Mean subject brain volume vs age")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_plot, dpi=200)


def main() -> None:
    p = argparse.ArgumentParser(description="Measure per-subject brain volume across ages.")
    p.add_argument(
        "--db-root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        help="Path to PediatricMriDB folder (default: this script's directory).",
    )
    p.add_argument("--sex", default="female", choices=["female", "male"], help="Sex folder to analyze.")
    p.add_argument(
        "--subdir",
        default="intensity_improved_selected_for_template",
        help="Subdirectory under AgeN/<sex>/ containing subject NIfTI images.",
    )
    p.add_argument(
        "--ages",
        default="",
        help="Ages to include, e.g. '5-18' or '7,8,9' (default: all Age* found).",
    )
    p.add_argument(
        "--mask-mode",
        default="auto",
        choices=["auto", "mask_file_only"],
        help="auto: use mask file if present else auto-mask; mask_file_only: skip subjects without masks.",
    )
    p.add_argument(
        "--out-csv",
        default="",
        help="Per-subject output CSV (default: <db-root>/brain_size_subjects_<sex>.csv).",
    )
    p.add_argument(
        "--out-summary-csv",
        default="",
        help="Per-age summary CSV (default: <db-root>/brain_size_by_age_<sex>.csv).",
    )
    p.add_argument(
        "--out-plot",
        default="",
        help="Optional PNG plot path (default: <db-root>/brain_size_by_age_<sex>.png).",
    )
    p.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable plot generation (CSV outputs only).",
    )
    args = p.parse_args()

    db_root = os.path.abspath(args.db_root)
    ages = parse_age_list(args.ages) if args.ages.strip() else None

    out_csv = os.path.abspath(args.out_csv or os.path.join(db_root, f"brain_size_subjects_{args.sex}.csv"))
    out_summary = os.path.abspath(
        args.out_summary_csv or os.path.join(db_root, f"brain_size_by_age_{args.sex}.csv")
    )
    plot_requested = bool(args.out_plot.strip())
    out_plot = ""
    if not args.no_plot:
        out_plot = os.path.abspath(args.out_plot or os.path.join(db_root, f"brain_size_by_age_{args.sex}.png"))

    subj_rows: List[Dict[str, str]] = []
    vols_by_age: Dict[int, List[float]] = {}

    entries = list(_iter_subject_images(db_root=db_root, sex=args.sex, subdir=args.subdir, ages=ages))
    if not entries:
        raise SystemExit(
            f"No subject images found under {db_root}/Age*/{args.sex}/{args.subdir}/\n"
            f"Tip: verify the path exists and contains *.nii.gz files."
        )

    for e in entries:
        img0 = nib.load(e.image_path)
        img = _as_canonical(img0)
        vox_vol = _voxel_volume_mm3(img)

        method = ""
        thr = float("nan")
        if e.mask_path and os.path.exists(e.mask_path):
            mask = _maybe_load_mask(e.mask_path, img)
            method = "mask_file"
        else:
            if args.mask_mode == "mask_file_only":
                continue
            mask, thr, method = _auto_mask_from_image(img)

        brain_vox = int(mask.sum())
        brain_ml = float(brain_vox * vox_vol / 1000.0)
        vols_by_age.setdefault(e.age, []).append(brain_ml)

        subj_rows.append(
            {
                "age": str(e.age),
                "sex": e.sex,
                "subject_id": e.subject_id,
                "image_path": e.image_path,
                "mask_path": e.mask_path or "",
                "method": method,
                "threshold": "" if method == "mask_file" else f"{thr:.6g}",
                "voxel_volume_mm3": f"{vox_vol:.6g}",
                "brain_voxels": str(brain_vox),
                "brain_volume_ml": f"{brain_ml:.6g}",
            }
        )

    subj_fieldnames = [
        "age",
        "sex",
        "subject_id",
        "image_path",
        "mask_path",
        "method",
        "threshold",
        "voxel_volume_mm3",
        "brain_voxels",
        "brain_volume_ml",
    ]
    write_csv(out_csv, subj_rows, subj_fieldnames)

    summary_rows: List[Dict[str, str]] = []
    for age in sorted(vols_by_age.keys()):
        vols = vols_by_age[age]
        mean_ml, std_ml = _mean_std(vols)
        summary_rows.append(
            {
                "age": str(age),
                "sex": args.sex,
                "n_subjects": str(len(vols)),
                "mean_brain_volume_ml": f"{mean_ml:.6g}",
                "std_brain_volume_ml": f"{std_ml:.6g}",
            }
        )

    summary_fieldnames = ["age", "sex", "n_subjects", "mean_brain_volume_ml", "std_brain_volume_ml"]
    write_csv(out_summary, summary_rows, summary_fieldnames)

    # Plot:
    # - If user explicitly requested a plot path, require matplotlib.
    # - Otherwise, best-effort plot (skip if matplotlib is unavailable).
    if out_plot:
        if plot_requested:
            maybe_plot(out_plot, summary_rows)
        else:
            try:
                maybe_plot(out_plot, summary_rows)
            except SystemExit:
                pass

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_summary}")
    if out_plot and os.path.exists(out_plot):
        print(f"Wrote: {out_plot}")
    if not _HAVE_SCIPY:
        print("Note: scipy not available; auto masks are not largest-component cleaned / hole-filled.")


if __name__ == "__main__":
    main()

