#!/usr/bin/env python3
"""
QA for staged templates in Yang/PediatricMriDB/Templates.

Purpose:
  - Report template voxel sizes and physical FOV (mm) so the montage can be interpreted correctly.
  - Provide rough size proxies (threshold-based mask bbox + volume) to see if global size differences
    were normalized away by registration.

Inputs (expected):
  Templates/age{AGE}_{sex}_template.nii.gz  where sex in {male,female}

Outputs:
  - Templates/templates_geometry.csv
  - Templates/templates_geometry.png (optional; requires matplotlib)

Notes:
  - The bbox/volume proxies are *heuristics* based on intensity thresholding and are not a substitute
    for a real brain mask / segmentation. But they are often enough to detect "everything got scaled
    to the same size" vs "growth is present".
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np  # type: ignore

try:
    import nibabel as nib  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "Missing dependency nibabel. Install with:\n"
        "  python3 -m pip install --user nibabel typing_extensions\n"
        f"Original error: {e}"
    )


TEMPLATE_RE = re.compile(r"^age(?P<age>\d+)_(?P<sex>male|female)_template\.nii\.gz$")
MASK_RE = re.compile(r"^age(?P<age>\d+)_(?P<sex>male|female)_brain_mask\.nii\.gz$")


@dataclass(frozen=True)
class Entry:
    age: int
    sex: str
    path: str


def discover(templates_dir: str) -> List[Entry]:
    out: List[Entry] = []
    for fn in os.listdir(templates_dir):
        m = TEMPLATE_RE.match(fn)
        if not m:
            continue
        out.append(Entry(age=int(m.group("age")), sex=m.group("sex"), path=os.path.join(templates_dir, fn)))
    out.sort(key=lambda e: (e.sex, e.age))
    return out


def find_matching_mask(templates_dir: str, age: int, sex: str) -> Optional[str]:
    # Preferred staged naming (if you later add it)
    p = os.path.join(templates_dir, f"age{age}_{sex}_brain_mask.nii.gz")
    if os.path.isfile(p):
        return p
    # Back-compat with existing files already in Templates/ (age7_female_brain_mask.nii.gz etc)
    p2 = os.path.join(templates_dir, f"age{age}_{sex}_brain_mask.nii.gz".replace("age", "age"))
    if os.path.isfile(p2):
        return p2
    # Try legacy "age7_female_brain_mask.nii.gz" (note underscore after age)
    legacy = os.path.join(templates_dir, f"age{age}_{sex}_brain_mask.nii.gz")
    if os.path.isfile(legacy):
        return legacy
    # If someone used "age7_female_brain_mask.nii.gz" style (already handled above),
    # fall back to scanning directory (cheap; directory is small).
    for fn in os.listdir(templates_dir):
        m = MASK_RE.match(fn)
        if not m:
            continue
        if int(m.group("age")) == age and m.group("sex") == sex:
            return os.path.join(templates_dir, fn)
    return None


def voxel_sizes_mm(affine: np.ndarray) -> Tuple[float, float, float]:
    # Equivalent to nibabel.affines.voxel_sizes but without importing extra module.
    # Column vectors encode voxel axes in world space; their norms are voxel sizes.
    return tuple(float(np.linalg.norm(affine[:3, i])) for i in range(3))  # type: ignore[return-value]


def robust_threshold(data: np.ndarray, q: float) -> float:
    flat = data[np.isfinite(data)]
    if flat.size == 0:
        return 0.0
    nonzero = flat[flat != 0]
    ref = nonzero if nonzero.size > 1000 else flat
    return float(np.percentile(ref, q))


def mask_bbox(mask: np.ndarray) -> Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
    if not np.any(mask):
        return None
    coords = np.argwhere(mask)
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    # inclusive -> exclusive
    return ((int(mins[0]), int(maxs[0]) + 1), (int(mins[1]), int(maxs[1]) + 1), (int(mins[2]), int(maxs[2]) + 1))


def analyze(path: str, thresh_q: float) -> Dict[str, str]:
    img = nib.load(path)
    data = img.get_fdata(dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D image, got {data.shape} for {path}")

    vx, vy, vz = voxel_sizes_mm(img.affine)
    sx, sy, sz = data.shape
    fovx, fovy, fovz = sx * vx, sy * vy, sz * vz

    thr = robust_threshold(data, thresh_q)
    mask = np.isfinite(data) & (data > thr)
    bbox = mask_bbox(mask)
    voxel_vol = vx * vy * vz
    mask_vol_mm3 = float(np.count_nonzero(mask) * voxel_vol)

    if bbox is None:
        bbx = bby = bbz = 0.0
    else:
        (x0, x1), (y0, y1), (z0, z1) = bbox
        bbx = (x1 - x0) * vx
        bby = (y1 - y0) * vy
        bbz = (z1 - z0) * vz

    return {
        "path": path,
        "shape_x": str(sx),
        "shape_y": str(sy),
        "shape_z": str(sz),
        "voxel_x_mm": f"{vx:.6g}",
        "voxel_y_mm": f"{vy:.6g}",
        "voxel_z_mm": f"{vz:.6g}",
        "fov_x_mm": f"{fovx:.3f}",
        "fov_y_mm": f"{fovy:.3f}",
        "fov_z_mm": f"{fovz:.3f}",
        "mask_source": "intensity_threshold",
        "thresh_quantile": f"{thresh_q:.3f}",
        "thresh_value": f"{thr:.6g}",
        "mask_voxels": str(int(np.count_nonzero(mask))),
        "mask_volume_mm3": f"{mask_vol_mm3:.3f}",
        "mask_bbox_x_mm": f"{bbx:.3f}",
        "mask_bbox_y_mm": f"{bby:.3f}",
        "mask_bbox_z_mm": f"{bbz:.3f}",
    }


def write_csv(path: str, rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        # Still write an empty file with a helpful header.
        fieldnames = ["age", "sex", "path", "mask_source"]
    else:
        # Stable column ordering: start with a preferred list, then append any extras.
        preferred = [
            "age",
            "sex",
            "path",
            "mask_path",
            "mask_source",
            "shape_x",
            "shape_y",
            "shape_z",
            "voxel_x_mm",
            "voxel_y_mm",
            "voxel_z_mm",
            "fov_x_mm",
            "fov_y_mm",
            "fov_z_mm",
            "thresh_quantile",
            "thresh_value",
            "mask_voxels",
            "mask_volume_mm3",
            "mask_bbox_x_mm",
            "mask_bbox_y_mm",
            "mask_bbox_z_mm",
        ]
        extras: List[str] = []
        for k in rows[0].keys():
            if k not in preferred:
                extras.append(k)
        fieldnames = [k for k in preferred if k in rows[0]] + extras
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def plot(rows: List[Dict[str, str]], out_png: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        print("matplotlib not available; skipping plot.")
        return

    if not rows:
        print("No rows to plot; skipping plot.")
        return

    # convert rows -> per sex arrays
    by_sex: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        by_sex.setdefault(r["sex"], []).append(r)
    for sex in by_sex:
        by_sex[sex].sort(key=lambda r: int(r["age"]))

    fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(12, 8))
    ax_fov = axes[0, 0]
    ax_vox = axes[0, 1]
    ax_bbox = axes[1, 0]
    ax_vol = axes[1, 1]

    for sex, rs in by_sex.items():
        ages = np.array([int(r["age"]) for r in rs])
        fovx = np.array([float(r["fov_x_mm"]) for r in rs])
        fovy = np.array([float(r["fov_y_mm"]) for r in rs])
        fovz = np.array([float(r["fov_z_mm"]) for r in rs])
        vx = np.array([float(r["voxel_x_mm"]) for r in rs])
        vy = np.array([float(r["voxel_y_mm"]) for r in rs])
        vz = np.array([float(r["voxel_z_mm"]) for r in rs])
        bbx = np.array([float(r["mask_bbox_x_mm"]) for r in rs])
        bby = np.array([float(r["mask_bbox_y_mm"]) for r in rs])
        bbz = np.array([float(r["mask_bbox_z_mm"]) for r in rs])
        vol = np.array([float(r["mask_volume_mm3"]) for r in rs])

        ax_fov.plot(ages, fovx, marker="o", label=f"{sex} FOV-x")
        ax_fov.plot(ages, fovy, marker="o", label=f"{sex} FOV-y")
        ax_fov.plot(ages, fovz, marker="o", label=f"{sex} FOV-z")

        ax_vox.plot(ages, vx, marker="o", label=f"{sex} vox-x")
        ax_vox.plot(ages, vy, marker="o", label=f"{sex} vox-y")
        ax_vox.plot(ages, vz, marker="o", label=f"{sex} vox-z")

        ax_bbox.plot(ages, bbx, marker="o", label=f"{sex} bbox-x")
        ax_bbox.plot(ages, bby, marker="o", label=f"{sex} bbox-y")
        ax_bbox.plot(ages, bbz, marker="o", label=f"{sex} bbox-z")

        ax_vol.plot(ages, vol / 1e6, marker="o", label=f"{sex} mask vol (L)")

    ax_fov.set_title("Physical FOV (mm) vs age")
    ax_fov.set_xlabel("Age")
    ax_fov.set_ylabel("mm")
    ax_fov.grid(True, alpha=0.3)
    ax_fov.legend(fontsize=8, ncol=2)

    ax_vox.set_title("Voxel size (mm) vs age")
    ax_vox.set_xlabel("Age")
    ax_vox.set_ylabel("mm")
    ax_vox.grid(True, alpha=0.3)
    ax_vox.legend(fontsize=8, ncol=2)

    # Title depending on mask source availability
    sources = {r.get("mask_source", "") for r in rows}
    if sources == {"brain_mask_file"}:
        bbox_title = "Brain-mask bbox size (mm) vs age"
    elif "brain_mask_file" in sources:
        bbox_title = "BBox size (mm) vs age (mixed: brain masks + intensity threshold)"
    else:
        bbox_title = f"Threshold-bbox size (mm) vs age (q={rows[0].get('thresh_quantile', '')})"
    ax_bbox.set_title(bbox_title)
    ax_bbox.set_xlabel("Age")
    ax_bbox.set_ylabel("mm")
    ax_bbox.grid(True, alpha=0.3)
    ax_bbox.legend(fontsize=8, ncol=2)

    ax_vol.set_title("Threshold-mask volume proxy vs age")
    ax_vol.set_xlabel("Age")
    ax_vol.set_ylabel("Liters (1e6 mm^3)")
    ax_vol.grid(True, alpha=0.3)
    ax_vol.legend(fontsize=8, ncol=2)

    plt.tight_layout()
    fig.savefig(out_png, dpi=200)
    print(f"Wrote: {out_png}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QA: voxel size/FOV + rough size proxies for Templates/age*_template.nii.gz")
    p.add_argument(
        "--root",
        default=os.path.abspath(os.path.dirname(__file__)),
        help="Path to Yang/PediatricMriDB (default: this script's directory)",
    )
    p.add_argument(
        "--templates-dir",
        default=None,
        help="Templates directory (default: <root>/Templates)",
    )
    p.add_argument(
        "--out-csv",
        default=None,
        help="Output CSV path (default: <templates-dir>/templates_geometry.csv)",
    )
    p.add_argument(
        "--out-png",
        default=None,
        help="Output PNG path (default: <templates-dir>/templates_geometry.png)",
    )
    p.add_argument(
        "--thresh-q",
        type=float,
        default=60.0,
        help="Quantile threshold (0-100) used for rough mask proxy (default: 60)",
    )
    p.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip PNG plot generation",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.root)
    templates_dir = os.path.abspath(args.templates_dir or os.path.join(root, "Templates"))
    out_csv = os.path.abspath(args.out_csv or os.path.join(templates_dir, "templates_geometry.csv"))
    out_png = os.path.abspath(args.out_png or os.path.join(templates_dir, "templates_geometry.png"))

    entries = discover(templates_dir)
    if not entries:
        raise SystemExit(f"No staged templates found in {templates_dir} (expected age*_template.nii.gz).")

    rows: List[Dict[str, str]] = []
    for e in entries:
        # Use a real brain mask if present in Templates/ for this age/sex (much more reliable).
        mask_path = find_matching_mask(templates_dir, age=e.age, sex=e.sex)

        row = analyze(e.path, thresh_q=args.thresh_q)
        row["age"] = str(e.age)
        row["sex"] = e.sex

        if mask_path:
            timg = nib.load(e.path)
            mimg = nib.load(mask_path)
            mdata = mimg.get_fdata(dtype=np.float32)
            if mdata.shape == timg.shape:
                mmask = np.isfinite(mdata) & (mdata > 0.5)
                bbox = mask_bbox(mmask)
                vx, vy, vz = voxel_sizes_mm(timg.affine)
                voxel_vol = vx * vy * vz
                mask_vol_mm3 = float(np.count_nonzero(mmask) * voxel_vol)
                if bbox is None:
                    bbx = bby = bbz = 0.0
                else:
                    (x0, x1), (y0, y1), (z0, z1) = bbox
                    bbx = (x1 - x0) * vx
                    bby = (y1 - y0) * vy
                    bbz = (z1 - z0) * vz

                row["mask_source"] = "brain_mask_file"
                row["mask_path"] = mask_path
                row["thresh_value"] = ""
                row["mask_voxels"] = str(int(np.count_nonzero(mmask)))
                row["mask_volume_mm3"] = f"{mask_vol_mm3:.3f}"
                row["mask_bbox_x_mm"] = f"{bbx:.3f}"
                row["mask_bbox_y_mm"] = f"{bby:.3f}"
                row["mask_bbox_z_mm"] = f"{bbz:.3f}"
            else:
                row["mask_path"] = mask_path
                row["mask_source"] = "brain_mask_file_shape_mismatch"
        else:
            row["mask_path"] = ""

        rows.append(row)

    # stable sort
    rows.sort(key=lambda r: (r["sex"], int(r["age"])))
    write_csv(out_csv, rows)
    print(f"Wrote: {out_csv}")

    if not args.no_plot:
        plot(rows, out_png=out_png)


if __name__ == "__main__":
    main()

