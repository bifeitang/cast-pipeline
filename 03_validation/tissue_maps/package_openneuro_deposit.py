#!/usr/bin/env python3
"""
Package the BRAIN CAST template library into the OpenNeuro deposit layout
described in the Data Descriptor's Data Records section.

Builds:

    BRAINCAST/
    |-- participants.tsv
    |-- pipeline/
    |-- templates/
    |   |-- tpl-BRAINCAST_age-05_sex-F_T1w.nii.gz
    |   |-- tpl-BRAINCAST_age-05_sex-F_label-{GM,WM,CSF}_probseg.nii.gz
    |   `-- tpl-BRAINCAST_age-05_sex-F_mask.nii.gz
    |-- quality/
    `-- README.md

Source names (as pulled from carya) are `age<N>_<sex>_template.nii.gz`,
`age<N>_<sex>_brain_mask.nii.gz`, and (once available) tissue maps.

Usage
-----
    # see what is present / missing without writing anything
    python3 package_openneuro_deposit.py --check

    # build the deposit tree (hardlinks by default; --copy to duplicate bytes)
    python3 package_openneuro_deposit.py --out ~/braincast_deposit

    # allow building with tissue maps absent (produces an INCOMPLETE tree)
    python3 package_openneuro_deposit.py --out ~/braincast_deposit --allow-partial

The script refuses to build a tree that does not match what the descriptor
promises unless --allow-partial is given, so a short deposit cannot be
uploaded by accident.
"""

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

# --- source of truth: the authentic HPC pull -------------------------------
DEFAULT_SRC = Path(__file__).resolve().parent / (
    "cast-hpc-authentic-2026-06-16/05_templates/CAST_final"
)

AGES = list(range(5, 19))          # 5..18 inclusive
SEXES = {"female": "F", "male": "M"}

# tissue map source basenames -> BIDS label. Extend the candidate lists as the
# carya-side names are confirmed; the first candidate that exists wins.
TISSUE = {
    "GM":  ["age{a}_{s}_gm.nii.gz",  "age{a}_{s}_template_pve_1.nii.gz",
            "age{a}_{s}_GM_probseg.nii.gz"],
    "WM":  ["age{a}_{s}_wm.nii.gz",  "age{a}_{s}_template_pve_2.nii.gz",
            "age{a}_{s}_WM_probseg.nii.gz"],
    "CSF": ["age{a}_{s}_csf.nii.gz", "age{a}_{s}_template_pve_0.nii.gz",
            "age{a}_{s}_CSF_probseg.nii.gz"],
}


def find(src: Path, candidates, age, sex):
    for pat in candidates:
        p = src / pat.format(a=age, s=sex)
        if p.exists():
            return p
    return None


def plan(src: Path):
    """Return (rows, missing). rows = (src_path, dest_name)."""
    rows, missing = [], []
    for age in AGES:
        for sex, tag in SEXES.items():
            stem = f"tpl-BRAINCAST_age-{age:02d}_sex-{tag}"

            t1 = src / f"age{age}_{sex}_template.nii.gz"
            (rows if t1.exists() else missing).append(
                (t1, f"{stem}_T1w.nii.gz") if t1.exists() else f"{stem}_T1w.nii.gz"
            )

            mask = src / f"age{age}_{sex}_brain_mask.nii.gz"
            (rows if mask.exists() else missing).append(
                (mask, f"{stem}_mask.nii.gz") if mask.exists() else f"{stem}_mask.nii.gz"
            )

            for label, cands in TISSUE.items():
                hit = find(src, cands, age, sex)
                if hit:
                    rows.append((hit, f"{stem}_label-{label}_probseg.nii.gz"))
                else:
                    missing.append(f"{stem}_label-{label}_probseg.nii.gz")
    return rows, missing


def sha256(p: Path, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(buf), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--copy", action="store_true",
                    help="copy bytes instead of hardlinking")
    ap.add_argument("--allow-partial", action="store_true")
    a = ap.parse_args()

    if not a.src.exists():
        sys.exit(f"ERROR: source not found: {a.src}")

    rows, missing = plan(a.src)
    expected = len(AGES) * len(SEXES) * 5

    print(f"source   : {a.src}")
    print(f"expected : {expected} files (28 sets x 5)")
    print(f"present  : {len(rows)}")
    print(f"missing  : {len(missing)}")

    if missing:
        print("\nMISSING (must be pulled from carya):")
        by_kind = {}
        for m in missing:
            kind = ("mask" if m.endswith("_mask.nii.gz")
                    else "T1w" if m.endswith("_T1w.nii.gz")
                    else m.split("label-")[1].split("_")[0])
            by_kind.setdefault(kind, []).append(m)
        for k, v in sorted(by_kind.items()):
            print(f"  {k:4s} x{len(v):3d}   e.g. {v[0]}")

    if a.check or not a.out:
        print("\n(--check: nothing written)")
        return 0 if not missing else 1

    if missing and not a.allow_partial:
        sys.exit(
            f"\nREFUSING to build: {len(missing)} of {expected} files are absent.\n"
            "The Data Records section promises 5 files per template; an upload\n"
            "missing tissue maps would not match the manuscript.\n"
            "Pull the missing files from carya, or pass --allow-partial to build\n"
            "an explicitly incomplete staging tree."
        )

    root = a.out / "BRAINCAST"
    tdir = root / "templates"
    tdir.mkdir(parents=True, exist_ok=True)
    (root / "quality").mkdir(exist_ok=True)
    (root / "pipeline").mkdir(exist_ok=True)

    print(f"\nwriting -> {root}")
    manifest = []
    for src_p, dest_name in rows:
        dst = tdir / dest_name
        if dst.exists():
            dst.unlink()
        if a.copy:
            shutil.copy2(src_p, dst)
        else:
            try:
                os.link(src_p, dst)
            except OSError:
                shutil.copy2(src_p, dst)
        manifest.append((dest_name, dst.stat().st_size, sha256(dst)))

    with open(root / "CHECKSUMS.sha256", "w") as fh:
        for name, _, digest in manifest:
            fh.write(f"{digest}  templates/{name}\n")

    total = sum(s for _, s, _ in manifest)
    print(f"wrote {len(manifest)} files, {total/1e6:.1f} MB")
    print(f"checksums -> {root/'CHECKSUMS.sha256'}")
    if missing:
        print(f"\n*** INCOMPLETE: {len(missing)} files still absent. DO NOT UPLOAD. ***")
        return 1
    print("\nComplete. Ready for OpenNeuro upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
