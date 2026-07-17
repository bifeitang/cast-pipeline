"""Shared Nature-Methods figure style: Okabe-Ito colorblind-safe palette,
Arial, vector-PDF + 600-dpi raster, clean spines. Import and call set_style()."""
import matplotlib as mpl
import matplotlib.pyplot as plt

# Okabe-Ito colorblind-safe 8-colour palette
OKABE = {
    "black": "#000000", "orange": "#E69F00", "skyblue": "#56B4E9",
    "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
    "vermillion": "#D55E00", "purple": "#CC79A7",
}
UH = OKABE["blue"]        # UH-Ped (ours)
NKI = OKABE["vermillion"] # NKI reference
MALE = OKABE["blue"]
FEMALE = OKABE["orange"]
SEQ_CMAP = "viridis"      # magnitude heat maps
DIV_CMAP = "RdBu_r"       # signed maps


def set_style():
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.8, "xtick.major.width": 0.8, "ytick.major.width": 0.8,
        "lines.linewidth": 1.4, "savefig.dpi": 600, "figure.dpi": 150,
        "pdf.fonttype": 42, "ps.fonttype": 42,  # editable text in vector output
        "legend.frameon": False, "axes.grid": False,
    })


def panel_letter(ax, letter, x=-0.12, y=1.05):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom", ha="right")


def save(fig, path_noext):
    """Write both vector PDF (source of truth) and 600-dpi PNG mirror."""
    fig.savefig(f"{path_noext}.pdf")
    fig.savefig(f"{path_noext}.png", dpi=600)
    print("wrote", path_noext + ".pdf/.png")
