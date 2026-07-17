#!/usr/bin/env python3
"""
Merge all per-subject deformation cost metrics under:
  Yang/PediatricMriDB/DeformationCost/test_set_dc/**/metrics.txt

Each metrics.txt is expected to have:
  - 1 header line (tab-delimited)
  - 1 data line (tab-delimited)

Subject ages are looked up from TemplateTestSet/hbn_subject_info_all.txt to get precise decimal ages.

Output: a single CSV under Yang/PediatricMriDB/DeformationCost/
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ParsedPath:
    group_dir: str
    age_dir: str  # integer age from directory structure
    subject_id: str


AGE_SEX_RE = re.compile(r"^age(?P<template_age>\d+)_(?P<template_sex>male|female)$")


def load_subjects_info(subjects_info_path: str) -> Dict[str, float]:
    """Load subjects_info.csv and return EID -> Age mapping."""
    age_lookup: Dict[str, float] = {}
    with open(subjects_info_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get("EID", "").strip()
            age_str = row.get("Age", "").strip()
            if eid and age_str:
                try:
                    age_lookup[eid] = float(age_str)
                except ValueError:
                    pass
    return age_lookup


def parse_metrics_file(path: str) -> Tuple[List[str], List[str]]:
    """Parse a metrics.txt file and return (header, data_row)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() != ""]
    if len(lines) != 2:
        raise ValueError(f"Expected exactly 2 non-empty lines (header + 1 row), got {len(lines)} in {path}")
    header = lines[0].split("\t")
    row = lines[1].split("\t")
    return header, row


def parse_path_components(metrics_path: str, base_dir: str) -> ParsedPath:
    """Extract group_dir, age_dir, subject_id from metrics.txt path."""
    rel = os.path.relpath(metrics_path, base_dir)
    parts = rel.split(os.sep)
    # Expected: group_dir/age_dir/subject_id/metrics.txt
    if len(parts) < 4:
        raise ValueError(f"Unexpected path (too few components) relative to base: {metrics_path}")
    group_dir, age_dir, subject_id = parts[0], parts[1], parts[2]
    return ParsedPath(group_dir=group_dir, age_dir=age_dir, subject_id=subject_id)


def enrich_row(parsed: ParsedPath, age_lookup: Dict[str, float]) -> Dict[str, str]:
    """Build additional columns from parsed path components."""
    template_age = ""
    template_sex = ""
    m = AGE_SEX_RE.match(parsed.group_dir)
    if m:
        template_age = m.group("template_age")
        template_sex = m.group("template_sex")
    
    # Look up precise subject age from subjects_info.csv
    # Fall back to age_dir (integer) if not found
    precise_age = age_lookup.get(parsed.subject_id)
    if precise_age is not None:
        subject_age = f"{precise_age:.6f}"
    else:
        subject_age = parsed.age_dir
    
    return {
        "group_dir": parsed.group_dir,
        "template_age": template_age,
        "template_sex": template_sex,
        "subject_age": subject_age,
        "subject_id": parsed.subject_id,
    }


def iter_metrics_files(base_dir: str) -> Iterable[str]:
    """Iterate over all metrics.txt files under base_dir."""
    for root, _, files in os.walk(base_dir):
        if "metrics.txt" in files:
            yield os.path.join(root, "metrics.txt")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Merge test set deformation cost metrics into a single CSV with precise subject ages."
    )
    ap.add_argument(
        "--base-dir",
        default=os.path.join(
            os.path.dirname(__file__),
            "test_set_dc",
        ),
        help="Base directory to scan for metrics.txt files (default: test_set_dc/)",
    )
    ap.add_argument(
        "--subjects-info",
        default=os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "TemplateTestSet",
            "hbn_subject_info_all.txt",
        ),
        help="Path to hbn_subject_info_all.txt for precise age lookup",
    )
    ap.add_argument(
        "--out-csv",
        default=os.path.join(
            os.path.dirname(__file__),
            "test_set_dc_metrics_merged.csv",
        ),
        help="Output CSV path",
    )
    args = ap.parse_args()

    base_dir = os.path.abspath(args.base_dir)
    subjects_info_path = os.path.abspath(args.subjects_info)
    out_csv = os.path.abspath(args.out_csv)

    # Load subject age lookup
    print(f"Loading subjects info from: {subjects_info_path}")
    if os.path.exists(subjects_info_path):
        age_lookup = load_subjects_info(subjects_info_path)
        print(f"Loaded {len(age_lookup)} subject age entries")
    else:
        print(f"WARNING: subjects_info.csv not found at {subjects_info_path}, using directory ages")
        age_lookup = {}

    # Find all metrics files
    print(f"Scanning for metrics.txt under: {base_dir}")
    metrics_files = sorted(iter_metrics_files(base_dir))
    if not metrics_files:
        raise SystemExit(f"No metrics.txt found under {base_dir}")
    print(f"Found {len(metrics_files)} metrics.txt files")

    # Validate consistent header and build rows
    common_header: Optional[List[str]] = None
    out_rows: List[Dict[str, str]] = []
    skipped = 0

    for p in metrics_files:
        try:
            header, row = parse_metrics_file(p)
        except ValueError as e:
            print(f"WARNING: Skipping {p}: {e}")
            skipped += 1
            continue

        if common_header is None:
            common_header = header
        elif header != common_header:
            print(f"WARNING: Header mismatch in {p}, skipping")
            skipped += 1
            continue

        try:
            parsed = parse_path_components(p, base_dir)
        except ValueError as e:
            print(f"WARNING: Skipping {p}: {e}")
            skipped += 1
            continue

        extra = enrich_row(parsed, age_lookup)
        row_dict = dict(zip(header, row))
        out_rows.append({**extra, **row_dict})

    if common_header is None:
        raise SystemExit("No valid metrics.txt files found")

    fieldnames = ["group_dir", "template_age", "template_sex", "subject_age", "subject_id"] + common_header

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote {len(out_rows)} rows -> {out_csv}")
    if skipped > 0:
        print(f"Skipped {skipped} files due to errors")


if __name__ == "__main__":
    main()
