#!/usr/bin/env python3
"""
Compute subject counts for Age5–Age18 by sex.

Outputs a CSV with:
  - original_subjects: best-effort estimate of "original downloaded cohort size"
    using, in order:
      1) count of `sub-*.tar.gz` directly under AgeX/<sex>/
      2) unique subject IDs in AgeX/<sex>/extracted (top-level only)
      3) unique subject IDs in AgeX/<sex>/intensity_improved_formated (top-level only)
      4) unique subject IDs in AgeX/<sex>/intensity_improved_formated_incomplete (top-level only)

  - selected_subjects: number of `{subject_id}.nii.gz` files directly under
    AgeX/<sex>/intensity_improved_selected_for_template/ (top-level only),
    excluding templates/warps.

This matches the repo layout in Yang/PediatricMriDB (NDAR subject IDs).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple


AGE_DIR_RE = re.compile(r"^Age(?P<age>\d+)$")
SUB_TAR_RE = re.compile(r"^sub-(?P<id>[^.]+)\.tar\.gz$", re.IGNORECASE)
SUB_DIR_RE = re.compile(r"^(?:sub-)?(?P<id>NDAR[A-Za-z0-9]+)$", re.IGNORECASE)
SELECTED_NII_RE = re.compile(r"^(?P<id>NDAR[A-Za-z0-9]+)\.nii\.gz$", re.IGNORECASE)


@dataclass(frozen=True)
class CountRow:
    age: int
    sex: str
    original_subjects: int
    original_source: str
    selected_subjects: int
    selected_dir: str


def parse_age_range(s: str) -> List[int]:
    s = (s or "").strip()
    if not s:
        return []
    if "-" in s and "," not in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def iter_age_dirs(root: str, ages_filter: Optional[Set[int]]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for name in os.listdir(root):
        m = AGE_DIR_RE.match(name)
        if not m:
            continue
        age = int(m.group("age"))
        if ages_filter is not None and age not in ages_filter:
            continue
        out.append((age, os.path.join(root, name)))
    out.sort(key=lambda t: t[0])
    return out


def list_names(path: str) -> List[str]:
    try:
        with os.scandir(path) as it:
            return [e.name for e in it]
    except FileNotFoundError:
        return []
    except NotADirectoryError:
        return []


def extract_subject_ids_from_names(names: Iterable[str]) -> Set[str]:
    ids: Set[str] = set()
    for n in names:
        base = n.rstrip("/")
        m = SUB_DIR_RE.match(base)
        if m:
            ids.add(m.group("id").upper())
    return ids


def count_original_subjects(age_sex_dir: str) -> Tuple[int, str]:
    """
    Returns (count, source_tag)
    """
    names = list_names(age_sex_dir)

    # 1) tar.gz archives in the root
    tar_ids: Set[str] = set()
    for n in names:
        m = SUB_TAR_RE.match(n)
        if m:
            tar_ids.add(m.group("id").upper())
    if tar_ids:
        return (len(tar_ids), "tar_gz")

    # 2) extracted/
    extracted_dir = os.path.join(age_sex_dir, "extracted")
    ex_ids = extract_subject_ids_from_names(list_names(extracted_dir))
    if ex_ids:
        return (len(ex_ids), "extracted")

    # 3) intensity_improved_formated/
    fmt_dir = os.path.join(age_sex_dir, "intensity_improved_formated")
    fmt_ids = extract_subject_ids_from_names(list_names(fmt_dir))
    if fmt_ids:
        return (len(fmt_ids), "intensity_improved_formated")

    # 4) intensity_improved_formated_incomplete/
    fmt_inc_dir = os.path.join(age_sex_dir, "intensity_improved_formated_incomplete")
    fmt_inc_ids = extract_subject_ids_from_names(list_names(fmt_inc_dir))
    if fmt_inc_ids:
        return (len(fmt_inc_ids), "intensity_improved_formated_incomplete")

    return (0, "missing")


def count_selected_subjects(selected_dir: str) -> int:
    """
    Count `{subject_id}.nii.gz` files directly under selected_dir.
    """
    names = list_names(selected_dir)
    ids: Set[str] = set()
    for n in names:
        m = SELECTED_NII_RE.match(n)
        if m:
            ids.add(m.group("id").upper())
    return len(ids)


def write_csv(rows: Sequence[CountRow], out_csv: str) -> None:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "age",
                "sex",
                "original_subjects",
                "original_source",
                "selected_subjects",
                "selected_dir",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "age": r.age,
                    "sex": r.sex,
                    "original_subjects": r.original_subjects,
                    "original_source": r.original_source,
                    "selected_subjects": r.selected_subjects,
                    "selected_dir": r.selected_dir,
                }
            )


def write_pivot_csv(rows: Sequence[CountRow], out_csv: str) -> None:
    """
    Write one row per age with male/female original+selected columns.
    """
    by_age: dict[int, dict[str, CountRow]] = {}
    for r in rows:
        by_age.setdefault(r.age, {})[r.sex] = r

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "age",
                "male_original_subjects",
                "female_original_subjects",
                "male_original_source",
                "female_original_source",
                "male_selected_subjects",
                "female_selected_subjects",
            ],
        )
        w.writeheader()
        for age in sorted(by_age.keys()):
            m = by_age[age].get("male")
            fe = by_age[age].get("female")
            w.writerow(
                {
                    "age": age,
                    "male_original_subjects": (m.original_subjects if m else 0),
                    "female_original_subjects": (fe.original_subjects if fe else 0),
                    "male_original_source": (m.original_source if m else "missing"),
                    "female_original_source": (fe.original_source if fe else "missing"),
                    "male_selected_subjects": (m.selected_subjects if m else 0),
                    "female_selected_subjects": (fe.selected_subjects if fe else 0),
                }
            )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Count original and selected subjects by age/sex.")
    p.add_argument(
        "--root",
        default=os.path.abspath(os.path.dirname(__file__)),
        help="Path to Yang/PediatricMriDB (default: this script's directory)",
    )
    p.add_argument("--ages", default="5-18", help='Age spec: "5-18" or "5,6,7" (default: 5-18)')
    p.add_argument("--sexes", default="male,female", help='Comma-separated sexes (default: "male,female")')
    p.add_argument(
        "--out-csv",
        default=None,
        help="Output CSV path (default: <root>/summary_subject_counts_age5_18_original_vs_selected.csv)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.root)
    ages = set(parse_age_range(args.ages))
    sexes = [s.strip().lower() for s in (args.sexes or "").split(",") if s.strip()]
    if not sexes:
        sexes = ["male", "female"]

    age_dirs = iter_age_dirs(root, ages_filter=ages if ages else None)
    rows: List[CountRow] = []

    for age, age_dir in age_dirs:
        for sex in sexes:
            age_sex_dir = os.path.join(age_dir, sex)
            original_n, original_src = count_original_subjects(age_sex_dir)
            selected_dir = os.path.join(age_sex_dir, "intensity_improved_selected_for_template")
            selected_n = count_selected_subjects(selected_dir)
            rows.append(
                CountRow(
                    age=age,
                    sex=sex,
                    original_subjects=original_n,
                    original_source=original_src,
                    selected_subjects=selected_n,
                    selected_dir=selected_dir,
                )
            )

    out_csv = args.out_csv or os.path.join(
        root, "summary_subject_counts_age5_18_original_vs_selected.csv"
    )
    write_csv(rows, out_csv)

    pivot_csv = out_csv[:-4] + "_pivot.csv" if out_csv.lower().endswith(".csv") else out_csv + "_pivot.csv"
    write_pivot_csv(rows, pivot_csv)

    # stdout summary
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {pivot_csv}")
    total_orig = sum(r.original_subjects for r in rows)
    total_sel = sum(r.selected_subjects for r in rows)
    print(f"Total original_subjects: {total_orig}")
    print(f"Total selected_subjects: {total_sel}")


if __name__ == "__main__":
    main()

