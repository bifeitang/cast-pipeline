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

Every panel is cropped to a fixed physical field of view, so brains are cut to the same
box and directly comparable in size across panels regardless of matrix or voxel dimensions.

CENTRING (revised 2026-07-29). Two different centres are involved and conflating them is
what left uneven margins in the first version:

  * WHICH SLICE to take -- the brain's 3-D centroid. Anatomically meaningful and shared
    across panels, so rows stay comparable. Unchanged.
  * WHERE TO PUT THE BOX in that slice -- now the bounding-box centre of the brain content
    within the slice itself (`center="bbox"`), not the projected 3-D centroid.

The 3-D mask centroid is pulled inferiorly and posteriorly by the brainstem, cerebellum and
neck remnant, so a box centred on it leaves a wide margin above the vertex and clips toward
the bottom. The in-plane bounding-box centre puts equal margin on all four sides by
construction. `center="centroid"` keeps the old behaviour for any caller that wants it.

For an overlay that must stay registered to its underlay, compute the centres ONCE from the
underlay with `crop_centers()` and pass them to both calls via `centers=`. Letting each
volume pick its own box would shift the overlay off the anatomy it annotates.
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


def _plane_data(img, centroid_vox=None, ref_img=None):
    """Return {plane: (2-D array, xs_mm, ys_mm, centroid_centre_xy)} before cropping.

    Arrays are oriented for imshow(origin='lower'):
      sagittal  x = anterior to the LEFT, y = superior up
      coronal   x = subject right to the right, y = superior up
      axial     x = subject right to the right, y = anterior up
    Every coordinate vector is INCREASING -- the sagittal mirror is applied to the
    coordinates as well as the data, so _crop's arithmetic holds for all three planes.
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

    return {
        # sagittal: vol[i] is [A, S] -> [S, A], then reverse A so the anterior pole is on
        # the left; the coordinate vector is mirrored to match, staying increasing.
        "sagittal": (vol[i, :, :].T[:, ::-1], (2 * cA) - A[::-1], S, (cA, cS)),
        "coronal": (vol[:, j, :].T, R, S, (cR, cS)),          # [R, S] -> [S, R]
        "axial": (vol[:, :, k].T, R, A, (cR, cA)),            # [R, A] -> [A, R]
    }


def _bbox_center(arr, xs, ys, thresh):
    """In-plane bounding-box centre of the brain content, in mm.

    Falls back to None when the slice is empty, so the caller can drop to the centroid
    rather than centring on nothing.
    """
    m = arr > thresh
    if not m.any():
        return None
    cols = np.where(m.any(0))[0]
    rows = np.where(m.any(1))[0]
    return (0.5 * (xs[cols[0]] + xs[cols[-1]]),
            0.5 * (ys[rows[0]] + ys[rows[-1]]))


def crop_centers(img, centroid_vox=None, ref_img=None, frac=BRAIN_FRAC, thresh=None):
    """{plane: (cx_mm, cy_mm)} bounding-box centres, for sharing between overlay pairs.

    `thresh` overrides the intensity cut; pass the UNDERLAY's threshold when centring an
    overlay so both are boxed identically.
    """
    data = _plane_data(img, centroid_vox, ref_img)
    vmax = canonical(img).get_fdata().max()
    t = frac * vmax if thresh is None else thresh
    out = {}
    for plane, (arr, xs, ys, default) in data.items():
        out[plane] = _bbox_center(arr, xs, ys, t) or default
    return out


def planes_mm(img, fov=FOV_MM, centroid_vox=None, ref_img=None,
              center="bbox", centers=None):
    """Return {'sagittal','coronal','axial'} -> (2-D array, extent-in-mm).

    Slices are taken at the brain centroid (or at `centroid_vox`, in the CANONICAL frame,
    when a common slice location is wanted across panels). `ref_img`, if given, supplies
    the centroid instead -- used to hold two strata to the same slice.

    `center` chooses where the crop box sits within each slice:
      "bbox"      the brain's in-plane bounding-box centre -- equal margins on all four
                  sides. The default, and what figures should normally use.
      "centroid"  the projected 3-D centroid, which sits low and posterior because the
                  brainstem and cerebellum drag it there. Kept for reproducing older
                  output.
    `centers` overrides both with an explicit {plane: (cx, cy)} -- pass the underlay's
    `crop_centers()` when cropping a registered overlay.

    The returned extent is in mm relative to the crop centre, so imshow with
    aspect='equal' renders every panel at true physical size.
    """
    data = _plane_data(img, centroid_vox, ref_img)
    if centers is None and center == "bbox":
        vmax = canonical(img).get_fdata().max()
        centers = {p: _bbox_center(a, xs, ys, BRAIN_FRAC * vmax) or d
                   for p, (a, xs, ys, d) in data.items()}
    out = {}
    for plane, (arr, xs, ys, default) in data.items():
        cx, cy = (centers or {}).get(plane, default)
        out[plane] = _crop(arr, xs, ys, cx, cy, fov)
    return out


def window(vol, lo=0.0, hi=99.5):
    """Display window from in-brain intensities; each volume is windowed on its own
    scale because the pipeline variants differ in intensity convention by construction."""
    nz = vol[vol > 0]
    return (np.percentile(nz, lo) if lo else 0.0), np.percentile(nz, hi)
