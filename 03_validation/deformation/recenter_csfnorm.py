#!/usr/bin/env python3
"""Reproduce the `_csfNorm_rc` recentring exactly, for subjects whose centred image was
lost to the storage cleanup.

WHAT RECENTRING ACTUALLY IS
Derived empirically from a subject that retains BOTH stages (pre: brainmask_csfNorm,
post: csfNorm_rc, plus the ANTs .mat that produced it):

  * the voxel data is BYTE-IDENTICAL between the two -- np.array_equal() is True. This is
    a pure header operation; no resampling, no interpolation, nothing to degrade.
  * the affine translation shifts by exactly the NEGATED INTENSITY-WEIGHTED CENTRE OF MASS
    of the image, so that centre lands on the world origin.

Tested against four candidate definitions on a verified pair:

    intensity-weighted COM     err 0.0001 mm   <-- exact (float rounding)
    binary COM (>0)            err 1.0025 mm
    bbox centre of >0          err 12.8167 mm
    geometric centre of grid   err 29.0842 mm

and the derived shift reproduces the tarball's own .mat parameters
(-9.2656, 6.1119, -35.2769) to four decimals.

WHY NOT ImageMath RecenterImage
That is what recenter_one.sh calls, and it is what I tried first: all 47 jobs failed in 17
seconds because `RecenterImage` does not exist in this project's ANTs build
(mri_template_env_reg.sif offers only CenterImage2inImage1). Implementing the operation
directly is exact, needs no container, and -- because it only rewrites a header -- needs no
cluster time at all, which matters when the queue is thousands deep.

The magnitude is worth noting: |t| = 36.98 mm for the verified subject. That is the same
near-rigid ~35 mm coordinate-origin offset the release notes blame for inflating
mean_disp_mm from ~3-4 mm to ~31-35 mm in the composed metric. Two independent routes to
the same number.

Usage:
    recenter_csfnorm.py validate <pre.nii.gz> <post.nii.gz>   # check one known pair
    recenter_csfnorm.py apply <in.nii.gz> <out.nii.gz> [out.mat]
"""
import sys
import numpy as np
import nibabel as nib


def com_shift(img):
    """Negated intensity-weighted centre of mass, in world mm."""
    v = np.asarray(img.dataobj, dtype=np.float64)
    idx = np.argwhere(v > 0)
    if idx.size == 0:
        raise ValueError("image has no positive voxels")
    w = v[v > 0]
    com_vox = (idx * w[:, None]).sum(0) / w.sum()
    return -nib.affines.apply_affine(img.affine, com_vox)


def recenter(img):
    shift = com_shift(img)
    aff = img.affine.copy()
    aff[:3, 3] += shift
    # dataobj is passed through untouched: recentring must not resample.
    return nib.Nifti1Image(img.dataobj, aff, img.header), shift


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mode = sys.argv[1]

    if mode == "validate":
        pre, post = nib.load(sys.argv[2]), nib.load(sys.argv[3])
        out, shift = recenter(pre)
        got = out.affine[:3, 3]
        want = post.affine[:3, 3]
        err = float(np.linalg.norm(got - want))
        same = np.array_equal(np.asarray(pre.dataobj), np.asarray(post.dataobj))
        print(f"  shift {np.round(shift, 4)}  |t|={np.linalg.norm(shift):.3f} mm")
        print(f"  affine error vs truth: {err:.6f} mm   voxels identical: {same}")
        return 0 if (err < 1e-3 and same) else 1

    if mode == "apply":
        src, dst = sys.argv[2], sys.argv[3]
        img = nib.load(src)
        out, shift = recenter(img)
        nib.save(out, dst)
        if len(sys.argv) > 4:
            # ANTs-readable ITK transform, matching the originals' format
            with open(sys.argv[4], "w") as fh:
                fh.write("#Insight Transform File V1.0\n# Transform 0\n")
                fh.write("Transform: AffineTransform_double_3_3\n")
                fh.write("Parameters: 1 0 0 0 1 0 0 0 1 "
                         f"{shift[0]!r} {shift[1]!r} {shift[2]!r}\n")
                fh.write("FixedParameters: 0 0 0\n")
        print(f"  {src} -> {dst}   shift {np.round(shift, 4)}")
        return 0

    print(f"unknown mode: {mode}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
