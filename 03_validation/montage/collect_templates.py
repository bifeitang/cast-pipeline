#!/usr/bin/env python3
"""
Collect final cohort templates (per age / sex) into Yang/PediatricMriDB/Templates.

Expected source layout (example):
  Yang/PediatricMriDB/Age5/male/intensity_improved_selected_for_template/template0_template0.nii.gz

This script:
  - scans Age*/{male,female}/** for template0_template0.nii.gz
  - chooses the "best" candidate per age/sex (prefers intensity_improved_selected_for_template,
    avoids intermediateTemplates and *_old* folders; newest mtime wins ties)
  - copies or symlinks into Templates/ as: age{AGE}_{SEX}_template.nii.gz
  - writes Templates/templates_index.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


AGE_DIR_RE = re.compile(r"^Age(?P<age>\d+)$")
SEXES_DEFAULT = ("male", "female")
INTERMEDIATE_ITER_RE = re.compile(r".*/intermediatetemplates/.*_iteration(?P<iter>\d+)_template0_template0\.nii\.gz$", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    path: str
    score: int
    mtime: float


def parse_age_range(s: str) -> List[int]:
    """
    Parse age spec like:
      - "5-18"
      - "5,6,7,10"
    """
    s = s.strip()
    if not s:
        return []
    if "-" in s and "," not in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def iter_age_dirs(root: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for name in sorted(os.listdir(root)):
        m = AGE_DIR_RE.match(name)
        if not m:
            continue
        age = int(m.group("age"))
        out.append((age, os.path.join(root, name)))
    return out


def iter_template_candidates(age_sex_dir: str) -> Iterable[str]:
    """
    Yield candidate files under an AgeX/<sex>/ directory.
    We only consider template0_template0.nii.gz (not warps / intermediate templates).
    """
    for dirpath, dirnames, filenames in os.walk(age_sex_dir):
        # prune very large folders that we never want
        # (keeps scan fast on HPC filesystems)
        pruned = []
        for d in dirnames:
            dl = d.lower()
            if dl in {"intermediatetemplates"}:
                pruned.append(d)
            elif "warp" in dl:
                # avoid walking warp-heavy dirs if they exist
                pruned.append(d)
        if pruned:
            dirnames[:] = [d for d in dirnames if d not in pruned]

        if "template0_template0.nii.gz" in filenames:
            yield os.path.join(dirpath, "template0_template0.nii.gz")


def iter_intermediate_templates(age_sex_dir: str) -> Iterable[str]:
    """
    Yield intermediate template snapshots like:
      .../intermediateTemplates/SyN[0.1]_iteration11_template0_template0.nii.gz
    """
    for dirpath, dirnames, filenames in os.walk(age_sex_dir):
        # Only care about intermediateTemplates directories
        if "intermediateTemplates" not in dirpath and "intermediatetemplates" not in dirpath.lower():
            continue
        for fn in filenames:
            if fn.endswith("_template0_template0.nii.gz") and "iteration" in fn:
                yield os.path.join(dirpath, fn)


def parse_intermediate_iter(path: str) -> int:
    m = INTERMEDIATE_ITER_RE.match(path)
    if not m:
        return -1
    try:
        return int(m.group("iter"))
    except Exception:
        return -1


def score_candidate(path: str) -> int:
    """
    Higher score is better.
    """
    p = path.lower()
    score = 0
    if "/intensity_improved_selected_for_template/" in p:
        score += 50
    if "/selected_for_template/" in p:
        score += 10
    if "/rc/" in p:
        score -= 2
    if "old" in p:
        score -= 100
    if "intermediatetemplates" in p:
        score -= 1000
    return score


def choose_best(candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    scored: List[Candidate] = []
    for p in candidates:
        try:
            st = os.stat(p)
        except FileNotFoundError:
            continue
        scored.append(Candidate(path=p, score=score_candidate(p), mtime=st.st_mtime))
    if not scored:
        return None
    # Best by: score desc, mtime desc, shortest path
    scored.sort(key=lambda c: (-c.score, -c.mtime, len(c.path)))
    return scored[0].path


def choose_latest_intermediate(candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    scored: List[Tuple[int, float, str]] = []
    for p in candidates:
        try:
            st = os.stat(p)
        except FileNotFoundError:
            continue
        it = parse_intermediate_iter(p)
        scored.append((it, st.st_mtime, p))
    if not scored:
        return None
    # prefer highest iteration; then newest mtime
    scored.sort(key=lambda t: (-t[0], -t[1], len(t[2])))
    return scored[0][2]


def safe_link_or_copy(src: str, dst: str, mode: str, overwrite: bool) -> str:
    """
    mode: "copy" or "symlink"
    returns: status string
    """
    if os.path.exists(dst) or os.path.islink(dst):
        if not overwrite:
            return "exists_skip"
        try:
            os.remove(dst)
        except IsADirectoryError:
            shutil.rmtree(dst)

    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if mode == "symlink":
        os.symlink(src, dst)
        return "symlinked"
    shutil.copy2(src, dst)
    return "copied"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect Age*/{male,female} final templates into Templates/")
    p.add_argument(
        "--root",
        default=os.path.abspath(os.path.dirname(__file__)),
        help="Path to Yang/PediatricMriDB (default: this script's directory)",
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: <root>/Templates)",
    )
    p.add_argument(
        "--ages",
        default="5-18",
        help='Age spec: "5-18" or "5,6,7" (default: 5-18)',
    )
    p.add_argument(
        "--sexes",
        default="male,female",
        help='Comma-separated sexes to include (default: "male,female")',
    )
    p.add_argument(
        "--mode",
        choices=("copy", "symlink"),
        default="copy",
        help="How to stage templates into Templates/ (default: copy)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing staged templates (default: false)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would happen; do not write/copy files",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.root)
    out_dir = os.path.abspath(args.out_dir or os.path.join(root, "Templates"))
    ages_filter = set(parse_age_range(args.ages))
    sexes = [s.strip().lower() for s in args.sexes.split(",") if s.strip()]
    if not sexes:
        sexes = list(SEXES_DEFAULT)

    age_dirs = iter_age_dirs(root)
    if ages_filter:
        age_dirs = [(age, p) for (age, p) in age_dirs if age in ages_filter]

    rows: List[Dict[str, str]] = []
    missing: List[Tuple[int, str]] = []

    for age, age_dir in age_dirs:
        for sex in sexes:
            age_sex_dir = os.path.join(age_dir, sex)
            if not os.path.isdir(age_sex_dir):
                missing.append((age, sex))
                rows.append(
                    {
                        "age": str(age),
                        "sex": sex,
                        "src_path": "",
                        "dst_path": os.path.join(out_dir, f"age{age}_{sex}_template.nii.gz"),
                        "status": "missing_sex_dir",
                    }
                )
                continue

            candidates = list(iter_template_candidates(age_sex_dir))
            best = choose_best(candidates)
            dst = os.path.join(out_dir, f"age{age}_{sex}_template.nii.gz")

            if not best:
                # Fallback to latest intermediate template snapshot if final template wasn't written.
                inter = list(iter_intermediate_templates(age_sex_dir))
                best_inter = choose_latest_intermediate(inter)
                if best_inter:
                    if args.dry_run:
                        status = "dry_run_intermediate"
                    else:
                        status = safe_link_or_copy(best_inter, dst, mode=args.mode, overwrite=args.overwrite)
                    rows.append(
                        {
                            "age": str(age),
                            "sex": sex,
                            "src_path": best_inter,
                            "dst_path": dst,
                            "status": status,
                        }
                    )
                    continue

                # Fallback: if destination already exists, treat as satisfied.
                # This handles cases where templates were pre-staged into Templates/
                # even if the corresponding Age*/{sex}/ template build folder is missing.
                if os.path.isfile(dst) and not args.overwrite:
                    rows.append(
                        {
                            "age": str(age),
                            "sex": sex,
                            "src_path": dst,
                            "dst_path": dst,
                            "status": "already_present",
                        }
                    )
                    continue

                missing.append((age, sex))
                rows.append(
                    {
                        "age": str(age),
                        "sex": sex,
                        "src_path": "",
                        "dst_path": dst,
                        "status": "missing_template",
                    }
                )
                continue

            if args.dry_run:
                status = "dry_run"
            else:
                status = safe_link_or_copy(best, dst, mode=args.mode, overwrite=args.overwrite)

            rows.append(
                {
                    "age": str(age),
                    "sex": sex,
                    "src_path": best,
                    "dst_path": dst,
                    "status": status,
                }
            )

    # Write index CSV
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
        index_csv = os.path.join(out_dir, "templates_index.csv")
        with open(index_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["age", "sex", "src_path", "dst_path", "status"])
            writer.writeheader()
            writer.writerows(rows)

    # Summary to stdout
    total = len(rows)
    staged = sum(1 for r in rows if r["status"] in {"copied", "symlinked", "dry_run", "exists_skip"})
    missing_count = sum(1 for r in rows if r["status"].startswith("missing"))
    print(f"Root: {root}")
    print(f"Out:  {out_dir}")
    print(f"Total age/sex pairs: {total}")
    print(f"Staged: {staged}")
    print(f"Missing: {missing_count}")
    if missing:
        miss_str = ", ".join([f"{age}-{sex}" for age, sex in missing[:25]])
        more = "" if len(missing) <= 25 else f" ... (+{len(missing) - 25} more)"
        print(f"Missing pairs: {miss_str}{more}")


if __name__ == "__main__":
    main()

