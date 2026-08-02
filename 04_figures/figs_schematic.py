"""Shared vector-schematic primitives for the three BRAIN CAST diagram figures
(Figs 1, 2 and 4), so they read as one system.

Written 2026-08-01 to replace three hand-made raster schematics: a black-background
slide export for the preprocessing overview, a slide export for template construction
that embedded an uncredited third-party panel, and a text-dense TikZ card layout for
the container workflow.

Design rules, all Nature Methods house style:
  * white ground, Arial, 6-8 pt, thin rules (0.4 pt);
  * Okabe-Ito colour-blind-safe hues from figs_style, used only to group -- never as
    the sole carrier of meaning, so the figures survive greyscale;
  * every panel drawn in millimetres. The single axes spans the physical figure, so
    one data unit is one millimetre and nothing is scaled on inclusion.

Sizes follow Nature Methods column widths: 180 mm double column, 89 mm single.
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Polygon
from matplotlib.colors import to_rgb

from figs_style import OKABE

MM = 1 / 25.4                     # millimetres -> inches
COL2, COL1 = 180.0, 89.0          # Nature Methods double / single column width, mm

# These figures are drawn on a 180 mm canvas (Nature Methods double column) but the
# current Springer sn-jnl build includes them at \linewidth = 372 pt = 130.9 mm, so
# LaTeX scales them by 0.7285 and every point size shrinks with them. Type is therefore
# specified at the size it should PRINT at and multiplied here, so a nominal fs=7 really
# lands at 7 pt on the page. Regenerating for a 180 mm Nature Methods column at 1:1 means
# setting TYPE_SCALE = 1.0 -- and re-fitting the layouts, which were fitted at this scale.
TYPE_SCALE = 180.0 / (372.0 / 72.27 * 25.4)      # = 1 / 0.7285 = 1.372

# ---------------------------------------------------------------- uni-colour
# One accent, everywhere. Everything else is black, grey or white. Change this
# single constant to restyle all three diagram figures; nothing else is coloured,
# and no information is carried by colour alone, so the figures survive greyscale.
ACCENT = "#22609C"                # medium slate blue; 6.7:1 on white, so 5 pt text holds
GROUND = "#F1F5FA"                # ~6% accent tint: the pale workflow panel
# Alternatives, if a different temperature is wanted (change ACCENT + GROUND together).
# Contrast on white is given because the smallest figure text is 5 pt and needs >= 4.5:1.
#   deeper slate  "#1F4E79" / "#F2F5F9"   8.9:1
#   brighter      "#2171B5" / "#F0F5FA"   5.3:1
#   slate teal    "#125F63" / "#F1F6F6"
#   UH red        "#C8102E" / "#FBF2F3"

INK = "#1A1A1A"                   # body text
MUTE = "#6B7280"                  # secondary text
RULE = "#C9CDD2"                  # hairlines
CODE = "#374151"                  # monospace chips

# Phase hues -- Okabe-Ito, in a fixed order so the three figures agree
PHASE = [OKABE["blue"], OKABE["green"], OKABE["orange"], OKABE["vermillion"],
         OKABE["purple"], OKABE["skyblue"]]


def fs_(pt):
    """Nominal (printed) point size -> the size to hand matplotlib on this canvas."""
    return pt * TYPE_SCALE


def tint(color, frac):
    """Blend `color` toward white. frac=0 -> white, 1 -> the colour itself."""
    r, g, b = to_rgb(color)
    return (1 - frac + frac * r, 1 - frac + frac * g, 1 - frac + frac * b)


def canvas(width_mm, height_mm):
    """One axes spanning the whole figure, addressed in millimetres."""
    fig = plt.figure(figsize=(width_mm * MM, height_mm * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width_mm)
    ax.set_ylim(0, height_mm)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def rbox(ax, x, y, w, h, fc="white", ec=RULE, lw=0.4, r=1.2, z=2, **kw):
    """Rounded rectangle with its ORIGIN AT THE LOWER LEFT, sized exactly w x h mm."""
    p = FancyBboxPatch((x + r, y + r), w - 2 * r, h - 2 * r,
                       boxstyle=f"round,pad={r},rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z, **kw)
    ax.add_patch(p)
    return p


def band(ax, x, y, w, h, color, label, fs=6.4, z=3):
    """Filled phase header bar with white caps-label."""
    rbox(ax, x, y, w, h, fc=color, ec="none", r=0.8, z=z)
    ax.text(x + 1.8, y + h / 2, label, color="white", fontsize=fs_(fs),
            fontweight="bold", va="center", ha="left", zorder=z + 1)


def txt(ax, x, y, s, fs=7.0, color=INK, weight="normal", ha="left", va="baseline",
        z=5, mono=False, **kw):
    fam = {"family": "monospace"} if mono else {}
    return ax.text(x, y, s, fontsize=fs_(fs), color=color, fontweight=weight,
                   ha=ha, va=va, zorder=z, **fam, **kw)


def code(ax, x, y, s, fs=6.0, pad=1.0, fc="#F3F4F6", ec="#E1E4E8", z=4, ha="left"):
    """Monospace command chip. Returns the text artist (width is font-dependent,
    so callers that need exact extents should measure after a draw)."""
    t = ax.text(x + pad, y, s, fontsize=fs_(fs), color=CODE, family="monospace",
                ha=ha, va="center", zorder=z + 1,
                bbox=dict(boxstyle=f"round,pad={0.28}", facecolor=fc,
                          edgecolor=ec, linewidth=0.35))
    return t


def arrow(ax, x0, y0, x1, y1, color=INK, lw=0.9, head=2.6, z=6, style="-|>",
          connect="arc3,rad=0", ls="-"):
    a = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=f"{style},head_width={head/2.6*1.6},"
                        f"head_length={head}", mutation_scale=1.0, linewidth=lw,
                        color=color, zorder=z, connectionstyle=connect, linestyle=ls,
                        shrinkA=0, shrinkB=0, joinstyle="miter")
    ax.add_patch(a)
    return a


def flow(ax, x0, y0, x1, y1, lw=0.8, head=2.4, z=6):
    """The dashed accent connector used for every data path in Figs 1 and 2."""
    return arrow(ax, x0, y0, x1, y1, color=ACCENT, lw=lw, head=head, z=z,
                 ls=(0, (2.6, 1.6)))


def dbox(ax, x, y, w, h, title=None, tool=None, fill="white", lw=0.6,
         title_fs=6.2, tool_fs=5.5, z=3):
    """Outlined white box with a black title and, optionally, an accent-coloured
    tool name beneath it -- the unit this figure family is built from."""
    rbox(ax, x, y, w, h, fc=fill, ec=ACCENT, lw=lw, r=1.4, z=z)
    if title:
        txt(ax, x + w / 2, y + h - 4.2, title, fs=title_fs, ha="center",
            va="center", weight="bold", z=z + 2)
    if tool:
        txt(ax, x + w / 2, y + h - 8.0, tool, fs=tool_fs, ha="center", va="center",
            color=ACCENT, z=z + 2)
    return x + w / 2, y + h / 2


def badge(ax, cx, cy, n, color, r=2.0, fs=6.2, z=6):
    """Numbered step disc."""
    ax.add_patch(Circle((cx, cy), r, facecolor=color, edgecolor="none", zorder=z))
    ax.text(cx, cy, str(n), color="white", fontsize=fs_(fs), fontweight="bold",
            ha="center", va="center", zorder=z + 1)


def panel_label(ax, x, y, letter, fs=9.0):
    ax.text(x, y, letter, fontsize=fs_(fs), fontweight="bold", color=INK,
            ha="left", va="top", zorder=10)


# ----------------------------------------------------------------- glyph parts
def brain_glyph(ax, cx, cy, w, h, fc="#DDE3EA", ec=INK, lw=0.5, z=4, skull=False,
                sulci=True):
    """Schematic mid-sagittal brain outline. Illustrative, not subject data."""
    import numpy as np
    t = np.linspace(0, 2 * np.pi, 200)
    # egg-shaped lobe: wider anteriorly, flattened inferiorly
    rx, ry = w / 2, h / 2
    x = cx + rx * np.cos(t) * (1 + 0.10 * np.cos(t))
    y = cy + ry * np.sin(t) * (1 - 0.16 * np.sin(t))
    if skull:
        ax.add_patch(Polygon(list(zip(cx + (rx + w * 0.09) * np.cos(t) * (1 + 0.10 * np.cos(t)),
                                      cy + (ry + h * 0.09) * np.sin(t) * (1 - 0.16 * np.sin(t)))),
                             closed=True, facecolor="none", edgecolor=ec,
                             linewidth=lw, zorder=z, linestyle=(0, (2.2, 1.2))))
    ax.add_patch(Polygon(list(zip(x, y)), closed=True, facecolor=fc, edgecolor=ec,
                         linewidth=lw, zorder=z))
    if sulci:
        for k, frac in enumerate((0.34, 0.60, 0.82)):
            th = np.linspace(0.35 * np.pi, 1.55 * np.pi, 40)
            ax.plot(cx + rx * frac * np.cos(th), cy + ry * frac * np.sin(th) * 0.9,
                    color=ec, linewidth=lw * 0.55, zorder=z + 1, solid_capstyle="round")


def inset(fig, x, y, w, h, W, H, **kw):
    """Real axes at (x, y, w, h) millimetres inside a `canvas(W, H)` figure -- used
    where a schematic needs to embed actual image data or a real distribution."""
    ax = fig.add_axes([x / W, y / H, w / W, h / H], **kw)
    ax.set_zorder(8)
    ax.patch.set_alpha(0)
    return ax


def save(fig, path_noext):
    fig.savefig(f"{path_noext}.pdf")
    fig.savefig(f"{path_noext}.png", dpi=600)
    print("wrote", path_noext + ".pdf / .png")
