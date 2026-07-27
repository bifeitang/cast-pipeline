"""Shared brain-slice helper: canonical orientation, true mm scale, centred crop.

Written 2026-07-27 for the two montage figures (methods Figs 7 and 13), both of which
were previously drawn in voxel space. Two things go wrong when you do that:

  1. Volumes with different voxel sizes render at different physical sizes. The pipeline
     ablation mixes 1.0 mm and 0.8 mm volumes, so its "final" panel appeared ~25% larger
     than the other two for no anatomical reason. This is the same failure that hid
     +8-12% ICV growth in the template montage until it was rebuilt in mm space.
  2. Volumes with different axis orders slice along different anatomical planes. The two
     older pipeline volumes are LIA-ordered and the newer one is LAS, so index-based
     slicing silently produced different views and an inverted superior-inferior
     direction for two of the three panels.

Both are handled here by reorienting to canonical RAS first (nibabel's
as_closest_canonical) and then working exclusively in millimetres.

Every panel is cropped to a fixed physical field of view centred on the brain's own
centroid, so brains are centred, cut to the same box, and directly comparable in size
across panels regardless of matrix or voxel dimensions.
"""
import numpy as np
import nibabel as nib

FOV_MM = 180.0          # square field of view per panel; brains measure 132-170 mm
BRAIN_FRAC = 0.08       # intensity fraction defining "brain" for the centroid/mask


def canonical(img):
    """Reorient to RAS+ so axis 0 = R, axis 1 = A, axis 2 = S for every input."""
    return nib.as_closest_canonical(img)


def brain_centroid_vox(vol, frac=BRAIN_FRAC):
    m = vol > frac * vol.max()
    if not m.any():
        raise ValueError("no voxels above the brain threshold")
    return np.argwhere(m).mean(0)


def brain_extent_mm(vol, zooms, frac=BRAIN_FRAC):
    idx = np.argwhere(vol > frac * vol.max())
    return (idx.max(0) - idx.min(0) + 1) * np.asarray(zooms)


def _crop(plane, xs_mm, ys_mm, cx, cy, fov):
    """Crop a 2-D plane (indexed [y, x]) to exactly `fov` mm centred on (cx, cy).

    Zero-pads where the volume ends before the box does. Without the padding a brain
    sitting near the edge of its matrix yields a short panel, so panels come out at
    slightly different sizes and no longer line up in a grid -- which is what the
    hand-made versions of these figures suffered from.
    """
    dx = xs_mm[1] - xs_mm[0] if len(xs_mm) > 1 else 1.0
    dy = ys_mm[1] - ys_mm[0] if len(ys_mm) > 1 else 1.0
    nx, ny = int(round(fov / abs(dx))), int(round(fov / abs(dy)))
    # index of the box's first sample along each axis (may fall outside the volume)
    ix0 = int(round((cx - fov / 2 - xs_mm[0]) / dx))
    iy0 = int(round((cy - fov / 2 - ys_mm[0]) / dy))

    out = np.zeros((ny, nx), dtype=float)
    sx0, sx1 = max(ix0, 0), min(ix0 + nx, plane.shape[1])
    sy0, sy1 = max(iy0, 0), min(iy0 + ny, plane.shape[0])
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - iy0:sy1 - iy0, sx0 - ix0:sx1 - ix0] = plane[sy0:sy1, sx0:sx1]
    # extent is relative to the brain centroid, so every panel shares one origin
    return out, (-fov / 2, fov / 2, -fov / 2, fov / 2)


def planes_mm(img, fov=FOV_MM, centroid_vox=None, ref_img=None):
    """Return {'sagittal','coronal','axial'} -> (2-D array, extent-in-mm).

    Slices are taken at the brain centroid (or at `centroid_vox`, in the CANONICAL
    frame, when a common slice location is wanted across panels). `ref_img`, if given,
    supplies the centroid instead -- used to hold two strata to the same slice.

    Arrays are oriented for imshow(origin='lower'):
      sagittal  x = anterior to the LEFT, y = superior up
      coronal   x = subject right to the right, y = superior up
      axial     x = subject right to the right, y = anterior up
    The returned extent is in mm relative to the brain centroid, so imshow with
    aspect='equal' renders every panel at true physical size on a shared origin.
    """
    img = canonical(img)
    vol = img.get_fdata()
    zx, zy, zz = img.header.get_zooms()[:3]

    if centroid_vox is None:
        src = canonical(ref_img).get_fdata() if ref_img is not None else vol
        centroid_vox = brain_centroid_vox(src)
    i, j, k = (int(round(v)) for v in centroid_vox)
    i = np.clip(i, 0, vol.shape[0] - 1)
    j = np.clip(j, 0, vol.shape[1] - 1)
    k = np.clip(k, 0, vol.shape[2] - 1)

    # mm coordinates of each voxel index along each canonical axis
    R = np.arange(vol.shape[0]) * zx
    A = np.arange(vol.shape[1]) * zy
    S = np.arange(vol.shape[2]) * zz
    cR, cA, cS = centroid_vox[0] * zx, centroid_vox[1] * zy, centroid_vox[2] * zz

    out = {}
    # sagittal: vol[i] is [A, S] -> transpose to [S, A], then reverse the A axis so the
    # anterior pole is on the left. Reversing the data means the mm coordinate of column
    # c is A[::-1][c], so mirror the coordinate vector the same way.
    out["sagittal"] = _crop(vol[i, :, :].T[:, ::-1], (2 * cA) - A[::-1], S, cA, cS, fov)

    # coronal: vol[:, j] is [R, S] -> [S, R]
    out["coronal"] = _crop(vol[:, j, :].T, R, S, cR, cS, fov)

    # axial: vol[:, :, k] is [R, A] -> [A, R]
    out["axial"] = _crop(vol[:, :, k].T, R, A, cR, cA, fov)
    return out


def window(vol, lo=0.0, hi=99.5):
    """Display window from in-brain intensities; each volume is windowed on its own
    scale because the pipeline variants differ in intensity convention by construction."""
    nz = vol[vol > 0]
    return (np.percentile(nz, lo) if lo else 0.0), np.percentile(nz, hi)
