#!/usr/bin/env python3
"""
Measure "brain size" per age/sex template and summarize the trend.

Primary metric:
  - Brain volume (mL) from a brain mask when available, otherwise an automatic
    intensity-based mask (Otsu threshold).

Secondary metrics:
  - Axis-aligned bounding-box extents (mm) of the brain mask in canonical space.

Outputs:
  - CSV with per-template measurements
  - PNG trend plot (brain volume vs age, separated by sex)

Dependencies: numpy, nibabel, matplotlib (scipy optional; used only to keep largest component)
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


TEMPLATE_RE = re.compile(r"^age(?P<age>\d+)_(?P<sex>male|female)_template\.nii\.gz$")


def die_missing_deps() -> None:
    raise SystemExit(
        "Missing dependencies. Please load a python env with nibabel/numpy/matplotlib, e.g.\n"
        "  pip install --user nibabel numpy matplotlib\n"
        "Optional: scipy (for largest connected-component cleanup)\n"
    )


try:
    import numpy as np  # type: ignore
    import nibabel as nib  # type: ignore
    from nibabel.processing import resample_from_to  # type: ignore
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
except Exception:
    die_missing_deps()


try:
    import scipy.ndimage as ndi  # type: ignore

    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


@dataclass(frozen=True)
class TemplateEntry:
    age: int
    sex: str
    template_path: str
    mask_path: Optional[str]


def _as_canonical(img: "nib.Nifti1Image") -> "nib.Nifti1Image":
    try:
        return nib.as_closest_canonical(img)
    except Exception:
        return img


def _voxel_volume_mm3(img: "nib.Nifti1Image") -> float:
    zooms = img.header.get_zooms()[:3]
    return float(zooms[0] * zooms[1] * zooms[2])


def _otsu_threshold(data: np.ndarray, bins: int = 256) -> float:
    """
    Otsu threshold for a 1D distribution (expects background+foreground mix).
    Works well for templates with near-zero background (even if not exactly 0).
    """
    x = data[np.isfinite(data)].astype(np.float64, copy=False)
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
    mu = np.cumsum(p * (edges[:-1] + edges[1:]) / 2.0)
    mu_t = mu[-1]

    # Between-class variance
    denom = omega * (1.0 - omega) + 1e-12
    sigma_b2 = (mu_t * omega - mu) ** 2 / denom
    idx = int(np.nanargmax(sigma_b2))
    # threshold at bin center
    return float((edges[idx] + edges[idx + 1]) / 2.0)


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


def _mask_bbox_extents_mm(mask: np.ndarray, img: "nib.Nifti1Image") -> Tuple[float, float, float]:
    """
    Axis-aligned bbox extents in mm in the *canonical voxel axes*.
    """
    idx = np.argwhere(mask)
    if idx.size == 0:
        return (0.0, 0.0, 0.0)
    mins = idx.min(axis=0)
    maxs = idx.max(axis=0)
    # extents in voxels (inclusive)
    spans = (maxs - mins + 1).astype(np.float64)
    zooms = np.array(img.header.get_zooms()[:3], dtype=np.float64)
    ext_mm = spans * zooms
    return (float(ext_mm[0]), float(ext_mm[1]), float(ext_mm[2]))


def discover_entries(templates_dir: str) -> List[TemplateEntry]:
    out: List[TemplateEntry] = []
    for fn in os.listdir(templates_dir):
        m = TEMPLATE_RE.match(fn)
        if not m:
            continue
        age = int(m.group("age"))
        sex = m.group("sex")
        template_path = os.path.join(templates_dir, fn)
        mask_fn = f"age{age}_{sex}_brain_mask.nii.gz"
        mask_path = os.path.join(templates_dir, mask_fn)
        out.append(
            TemplateEntry(
                age=age,
                sex=sex,
                template_path=template_path,
                mask_path=mask_path if os.path.exists(mask_path) else None,
            )
        )
    out.sort(key=lambda e: (e.age, e.sex))
    return out


def load_mask_for_template(entry: TemplateEntry) -> Tuple[np.ndarray, str, float]:
    """
    Returns (mask_bool, method, threshold_used)
    method in {"mask_file", "otsu"}.
    """
    t_img0 = nib.load(entry.template_path)
    t_img = _as_canonical(t_img0)

    if entry.mask_path is not None:
        m_img0 = nib.load(entry.mask_path)
        m_img = _as_canonical(m_img0)

        # If geometry differs, resample mask to template space
        if m_img.shape != t_img.shape or not np.allclose(m_img.affine, t_img.affine, atol=1e-4):
            m_img = resample_from_to(m_img, t_img, order=0)

        m = m_img.get_fdata(dtype=np.float32)
        mask = np.isfinite(m) & (m > 0.5)
        return mask, "mask_file", float("nan")

    # Auto: Otsu threshold on template intensities
    data = t_img.get_fdata(dtype=np.float32)
    thr = _otsu_threshold(data)
    mask = np.isfinite(data) & (data > thr)
    mask = _keep_largest_component(mask)
    return mask, "otsu", thr


def write_csv(path: str, rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "age",
                "sex",
                "template_path",
                "mask_path",
                "method",
                "threshold",
                "voxel_volume_mm3",
                "brain_voxels",
                "brain_volume_ml",
                "bbox_x_mm",
                "bbox_y_mm",
                "bbox_z_mm",
            ],
        )
        w.writeheader()
        w.writerows(rows)


def plot_trend_png(path: str, rows: List[Dict[str, str]]) -> None:
    # parse to series per sex
    by_sex: Dict[str, List[Tuple[int, float]]] = {}
    for r in rows:
        age = int(r["age"])
        sex = r["sex"]
        vol = float(r["brain_volume_ml"])
        by_sex.setdefault(sex, []).append((age, vol))
    for sex in by_sex:
        by_sex[sex].sort(key=lambda t: t[0])

    os.makedirs(os.path.dirname(path), exist_ok=True)
    plt.figure(figsize=(7.5, 4.5))
    for sex, pts in by_sex.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        plt.plot(xs, ys, marker="o", linewidth=2, label=sex)
    plt.xlabel("Age")
    plt.ylabel("Brain volume (mL)")
    plt.title("Template brain volume vs age")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Measure brain size (volume + extents) per template.")
    p.add_argument(
        "--templates-dir",
        required=True,
        help="Directory containing age{AGE}_{sex}_template.nii.gz (and optional *_brain_mask.nii.gz).",
    )
    p.add_argument("--out-csv", default="", help="Output CSV path (default: <templates-dir>/brain_size_metrics.csv)")
    p.add_argument("--out-plot", default="", help="Output PNG plot path (default: <templates-dir>/brain_size_trend.png)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    templates_dir = os.path.abspath(args.templates_dir)
    out_csv = os.path.abspath(args.out_csv or os.path.join(templates_dir, "brain_size_metrics.csv"))
    out_plot = os.path.abspath(args.out_plot or os.path.join(templates_dir, "brain_size_trend.png"))

    entries = discover_entries(templates_dir)
    if not entries:
        raise SystemExit(f"No templates found in {templates_dir}")

    rows: List[Dict[str, str]] = []
    for e in entries:
        t_img = _as_canonical(nib.load(e.template_path))
        mask, method, thr = load_mask_for_template(e)
        vox_vol = _voxel_volume_mm3(t_img)
        brain_vox = int(mask.sum())
        brain_ml = float(brain_vox * vox_vol / 1000.0)
        bx, by, bz = _mask_bbox_extents_mm(mask, t_img)

        rows.append(
            {
                "age": str(e.age),
                "sex": e.sex,
                "template_path": e.template_path,
                "mask_path": e.mask_path or "",
                "method": method,
                "threshold": "" if method == "mask_file" else f"{thr:.6g}",
                "voxel_volume_mm3": f"{vox_vol:.6g}",
                "brain_voxels": str(brain_vox),
                "brain_volume_ml": f"{brain_ml:.6g}",
                "bbox_x_mm": f"{bx:.6g}",
                "bbox_y_mm": f"{by:.6g}",
                "bbox_z_mm": f"{bz:.6g}",
            }
        )

    write_csv(out_csv, rows)
    plot_trend_png(out_plot, rows)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_plot}")
    if not _HAVE_SCIPY:
        print("Note: scipy not available; auto masks are not largest-component cleaned.")


if __name__ == "__main__":
    main()

