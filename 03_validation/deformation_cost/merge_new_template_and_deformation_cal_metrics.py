#!/usr/bin/env python3
"""
Merge all per-subject deformation cost metrics under:
  Yang/PediatricMriDB/DeformationCost/new_template_and_deformation_cal/**/metrics.txt

Each metrics.txt is expected to have:
  - 1 header line (tab-delimited)
  - 1 data line (tab-delimited)

Output: a single CSV under Yang/PediatricMriDB/DeformationCost/
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class ParsedPath:
    group_dir: str
    subject_age: str
    subject_id: str


AGE_SEX_RE = re.compile(r"^age(?P<template_age>\d+)_(?P<template_sex>male|female)$")


def parse_metrics_file(path: str) -> Tuple[List[str], List[str]]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() != ""]
    if len(lines) != 2:
        raise ValueError(f"Expected exactly 2 non-empty lines (header + 1 row), got {len(lines)} in {path}")
    header = lines[0].split("\t")
    row = lines[1].split("\t")
    return header, row


def parse_path_components(metrics_path: str, base_dir: str) -> ParsedPath:
    rel = os.path.relpath(metrics_path, base_dir)
    parts = rel.split(os.sep)
    # Expected: group_dir/subject_age/subject_id/metrics.txt
    if len(parts) < 4:
        raise ValueError(f"Unexpected path (too few components) relative to base: {metrics_path}")
    group_dir, subject_age, subject_id = parts[0], parts[1], parts[2]
    return ParsedPath(group_dir=group_dir, subject_age=subject_age, subject_id=subject_id)


def enrich_row(parsed: ParsedPath) -> Dict[str, str]:
    template_age = ""
    template_sex = ""
    m = AGE_SEX_RE.match(parsed.group_dir)
    if m:
        template_age = m.group("template_age")
        template_sex = m.group("template_sex")
    return {
        "group_dir": parsed.group_dir,
        "template_age": template_age,
        "template_sex": template_sex,
        "subject_age": parsed.subject_age,
        "subject_id": parsed.subject_id,
    }


def iter_metrics_files(base_dir: str) -> Iterable[str]:
    for root, _, files in os.walk(base_dir):
        if "metrics.txt" in files:
            yield os.path.join(root, "metrics.txt")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-dir",
        default=os.path.join(
            os.path.dirname(__file__),
            "new_template_and_deformation_cal",
        ),
        help="Base directory to scan for metrics.txt files",
    )
    ap.add_argument(
        "--out-csv",
        default=os.path.join(
            os.path.dirname(__file__),
            "new_template_and_deformation_cal_metrics_merged.csv",
        ),
        help="Output CSV path",
    )
    args = ap.parse_args()

    base_dir = os.path.abspath(args.base_dir)
    out_csv = os.path.abspath(args.out_csv)

    metrics_files = sorted(iter_metrics_files(base_dir))
    if not metrics_files:
        raise SystemExit(f"No metrics.txt found under {base_dir}")

    # Validate consistent header and build rows
    common_header: List[str] | None = None
    out_rows: List[Dict[str, str]] = []

    for p in metrics_files:
        header, row = parse_metrics_file(p)
        if common_header is None:
            common_header = header
        elif header != common_header:
            raise ValueError(f"Header mismatch in {p}")

        parsed = parse_path_components(p, base_dir)
        extra = enrich_row(parsed)
        row_dict = dict(zip(header, row))
        out_rows.append({**extra, **row_dict})

    assert common_header is not None
    fieldnames = ["group_dir", "template_age", "template_sex", "subject_age", "subject_id"] + common_header

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote {len(out_rows)} rows -> {out_csv}")


if __name__ == "__main__":
    main()

