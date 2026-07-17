#!/usr/bin/env python3
"""
Generate an "Age Cohorts" montage figure from templates in Yang/PediatricMriDB/Templates.

Expected filenames (staged by collect_templates.py):
  Templates/age{AGE}_{sex}_template.nii.gz   where sex in {male,female}

Default montage style (requested):
  - 3 orthogonal views per template (Sagittal, Coronal, Axial)
  - Physical scaling is in **millimeters**, consistent across ages:
      *each subplot uses the same axis limits in mm*,
      so a smaller brain appears smaller in the panel.

Outputs:
  - templates_montage.png
  - templates_montage.svg
  - templates_montage_index.csv (what was plotted)

Notes (HPC-friendly):
  - This script only reads NIfTI files and writes images; no heavy compute.
  - Requires python packages: nibabel, numpy, matplotlib
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


TEMPLATE_RE = re.compile(r"^age(?P<age>\d+)_(?P<sex>male|female)_template\.nii\.gz$")


def die_missing_deps() -> None:
    raise SystemExit(
        "Missing dependencies. Please load a python env with nibabel/numpy/matplotlib, e.g.\n"
        "  pip install --user nibabel numpy matplotlib\n"
        "or use your cluster's module/conda environment."
    )


try:
    import numpy as np  # type: ignore
    import nibabel as nib  # type: ignore
    from nibabel.processing import resample_from_to  # type: ignore
    from nibabel.orientations import aff2axcodes  # type: ignore
    import matplotlib

    matplotlib.use("Agg")  # headless / HPC
    import matplotlib.pyplot as plt  # type: ignore
except Exception:
    die_missing_deps()


@dataclass(frozen=True)
class TemplateEntry:
    age: int
    sex: str
    path: str


def parse_age_spec(s: str) -> Optional[List[int]]:
    s = s.strip()
    if not s:
        return None
    if "-" in s and "," not in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def discover_templates(templates_dir: str) -> List[TemplateEntry]:
    out: List[TemplateEntry] = []
    for fn in os.listdir(templates_dir):
        m = TEMPLATE_RE.match(fn)
        if not m:
            continue
        age = int(m.group("age"))
        sex = m.group("sex")
        out.append(TemplateEntry(age=age, sex=sex, path=os.path.join(templates_dir, fn)))
    out.sort(key=lambda e: (e.age, e.sex))
    return out


def _voxel_sizes_mm(affine: np.ndarray) -> Tuple[float, float, float]:
    return tuple(float(np.linalg.norm(affine[:3, i])) for i in range(3))  # type: ignore[return-value]


def _robust_norm(data: np.ndarray) -> np.ndarray:
    flat = data[np.isfinite(data)]
    if flat.size == 0:
        flat = data.ravel()
    nonzero = flat[flat != 0]
    ref = nonzero if nonzero.size > 1000 else flat
    vmin = float(np.percentile(ref, 1))
    vmax = float(np.percentile(ref, 99))
    if vmax <= vmin:
        vmin, vmax = float(np.min(ref)), float(np.max(ref))
    out = np.clip(data, vmin, vmax)
    out = (out - vmin) / (vmax - vmin + 1e-6)
    return out


def _closest_canonical(img: "nib.Nifti1Image") -> "nib.Nifti1Image":
    # Canonicalize orientation so axes correspond to anatomical-ish directions.
    # This helps keep slice directions consistent across templates.
    try:
        return nib.as_closest_canonical(img)
    except Exception:
        return img


def load_orth_views_mm(path: str, fracs_xyz: Tuple[float, float, float]) -> Dict[str, Tuple[np.ndarray, Tuple[float, float, float, float]]]:
    """
    Returns dict:
      view -> (image2d, extent_mm)
    where extent_mm is (xmin, xmax, ymin, ymax) in millimeters.

    Views:
      - sagittal: slice along x, plane is (y,z)
      - coronal:  slice along y, plane is (x,z)
      - axial:    slice along z, plane is (x,y)
    """
    img0 = nib.load(path)
    img = _closest_canonical(img0)
    data = img.get_fdata(dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D NIfTI, got shape {data.shape} for {path}")

    data = _robust_norm(data)

    nx, ny, nz = data.shape
    fx, fy, fz = fracs_xyz
    xi = max(0, min(nx - 1, int(round(fx * (nx - 1)))))
    yi = max(0, min(ny - 1, int(round(fy * (ny - 1)))))
    zi = max(0, min(nz - 1, int(round(fz * (nz - 1)))))

    vx, vy, vz = _voxel_sizes_mm(img.affine)
    fovx, fovy, fovz = nx * vx, ny * vy, nz * vz

    # sagittal (y,z)
    sag = data[xi, :, :]
    # rotate for display consistency
    sag2 = np.rot90(sag)
    sag_extent = (-fovy / 2, fovy / 2, -fovz / 2, fovz / 2)

    # coronal (x,z)
    cor = data[:, yi, :]
    cor2 = np.rot90(cor)
    cor_extent = (-fovx / 2, fovx / 2, -fovz / 2, fovz / 2)

    # axial (x,y)
    ax = data[:, :, zi]
    ax2 = np.rot90(ax)
    ax_extent = (-fovx / 2, fovx / 2, -fovy / 2, fovy / 2)

    return {
        "Sagittal": (sag2, sag_extent),
        "Coronal": (cor2, cor_extent),
        "Axial": (ax2, ax_extent),
    }


def write_index_csv(out_csv: str, rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["age", "sex", "path", "plotted"])
        w.writeheader()
        w.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create age/sex cohort montage from Templates/*.nii.gz")
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
        "--out-prefix",
        default=None,
        help="Output prefix (default: <templates-dir>/templates_montage)",
    )
    p.add_argument(
        "--ages",
        default="",
        help='Optional age filter: "5-18" or "6,7,8" (default: all discovered ages)',
    )
    p.add_argument(
        "--sexes",
        default="male,female",
        help='Comma-separated sexes to plot (default: "male,female")',
    )
    p.add_argument(
        "--slice-fracs",
        default="0.50,0.50,0.50",
        help="Slice positions as fractions of (x,y,z), e.g. '0.5,0.5,0.5' (default: center slices)",
    )
    p.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="PNG dpi (default: 200)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.root)
    templates_dir = os.path.abspath(args.templates_dir or os.path.join(root, "Templates"))
    out_prefix = os.path.abspath(args.out_prefix or os.path.join(templates_dir, "templates_montage"))

    sexes = [s.strip().lower() for s in args.sexes.split(",") if s.strip()]
    frac_parts = [float(x.strip()) for x in args.slice_fracs.split(",") if x.strip()]
    if len(frac_parts) != 3:
        raise SystemExit("--slice-fracs must have 3 comma-separated values for x,y,z (e.g. 0.5,0.5,0.5)")
    fracs_xyz = (frac_parts[0], frac_parts[1], frac_parts[2])

    entries = discover_templates(templates_dir)
    by_key: Dict[Tuple[int, str], TemplateEntry] = {(e.age, e.sex): e for e in entries}

    discovered_ages = sorted({e.age for e in entries})
    age_filter = parse_age_spec(args.ages)
    ages = discovered_ages if age_filter is None else [a for a in age_filter if a in set(discovered_ages)]

    if not ages:
        raise SystemExit(f"No templates found to plot in {templates_dir}.")

    views = ["Sagittal", "Coronal", "Axial"]
    ncols = len(ages)
    nrows = len(sexes) * len(views)

    fig_w = max(10.0, 1.0 * ncols)
    fig_h = max(8.0, 1.0 * nrows)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(fig_w, fig_h), facecolor="black")
    if nrows == 1 and ncols == 1:
        axes = np.array([[axes]])
    elif nrows == 1:
        axes = np.array([axes])
    elif ncols == 1:
        axes = np.array([[a] for a in axes])

    plotted_rows: List[Dict[str, str]] = []

    # Precompute global mm extents per view across all available templates
    # so every panel is comparable in physical size.
    view_max = {"Sagittal": (0.0, 0.0), "Coronal": (0.0, 0.0), "Axial": (0.0, 0.0)}  # view -> (half_x_mm, half_y_mm)
    for age in ages:
        for sex in sexes:
            entry = by_key.get((age, sex))
            if entry is None:
                continue
            views_data = load_orth_views_mm(entry.path, fracs_xyz=fracs_xyz)
            for vname, (_, ext) in views_data.items():
                xmin, xmax, ymin, ymax = ext
                hx = max(abs(xmin), abs(xmax))
                hy = max(abs(ymin), abs(ymax))
                curx, cury = view_max[vname]
                view_max[vname] = (max(curx, hx), max(cury, hy))

    for si, sex in enumerate(sexes):
        for ai, age in enumerate(ages):
            entry = by_key.get((age, sex))
            if entry is None:
                for vi, vname in enumerate(views):
                    axp = axes[si * len(views) + vi, ai]
                    axp.set_facecolor("black")
                    axp.axis("off")
                plotted_rows.append({"age": str(age), "sex": sex, "path": "", "plotted": "false"})
                continue

            vdict = load_orth_views_mm(entry.path, fracs_xyz=fracs_xyz)
            for vi, vname in enumerate(views):
                img2d, _ext = vdict[vname]
                axp = axes[si * len(views) + vi, ai]
                hx, hy = view_max[vname]
                extent = (-hx, hx, -hy, hy)
                axp.imshow(img2d, cmap="gray", interpolation="nearest", extent=extent, aspect="equal")
                axp.set_facecolor("black")
                axp.axis("off")
            plotted_rows.append({"age": str(age), "sex": sex, "path": entry.path, "plotted": "true"})

    # column titles (ages) on first row
    for ai, age in enumerate(ages):
        ax = axes[0, ai]
        ax.set_title(str(age), color="white", fontsize=14, pad=8)

    fig.suptitle("Age Cohorts", color="white", fontsize=18, y=0.995)

    # Add "Male"/"Female" block labels on left
    for si, sex in enumerate(sexes):
        # y position: center of that block in figure coordinates
        block_center_row = si * len(views) + (len(views) - 1) / 2.0
        y = 1.0 - (block_center_row + 0.5) / nrows
        fig.text(0.01, y, sex.capitalize(), color="white", fontsize=18, va="center", ha="left")

    # Add view labels for the first column of each sex block
    for si, _sex in enumerate(sexes):
        for vi, vname in enumerate(views):
            row = si * len(views) + vi
            y = 1.0 - (row + 0.5) / nrows
            fig.text(0.06, y, vname, color="white", fontsize=12, va="center", ha="left")

    plt.subplots_adjust(left=0.08, right=0.995, top=0.95, bottom=0.02, wspace=0.02, hspace=0.02)

    png_path = out_prefix + ".png"
    svg_path = out_prefix + ".svg"
    idx_csv = out_prefix + "_index.csv"
    fig.savefig(png_path, dpi=args.dpi, facecolor=fig.get_facecolor(), bbox_inches="tight")
    fig.savefig(svg_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    write_index_csv(idx_csv, plotted_rows)

    print(f"Wrote: {png_path}")
    print(f"Wrote: {svg_path}")
    print(f"Wrote: {idx_csv}")


if __name__ == "__main__":
    main()

