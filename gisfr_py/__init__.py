"""gisfr_py - a Py-ART-style reader/plotter for GISFR radar mosaics.

GISFR (Geospatial Integrated Scan Format - Horizon Systems) is the binary
mosaic format produced by the HSMAIN desktop app's French radar mosaic
generator - see ../../src/GisfrFormat.h in this repo for the authoritative
byte-for-byte spec. This package is an independent, pure-Python
implementation of that same spec (no C++ bindings, no shared code with the
app - just numpy + matplotlib), so a .gisfr file can be opened and plotted
from a plain Python/Jupyter environment the same way Py-ART opens a NEXRAD
volume:

    from gisfr_py import GisfrFile, plot_mosaic

    with GisfrFile.open("FRANCE_2026-08-30_1030_REF_VEL_RAWREF.gisfr") as gf:
        meta = gf.read_metadata(gf.find_product("REF"))
        data, quality = gf.decode_full_mosaic(gf.find_product("REF"))

    plot_mosaic(data, meta)

or from the command line:

    python -m gisfr_py info mosaic.gisfr
    python -m gisfr_py plot mosaic.gisfr --product REF -o ref.png
"""

from .reader import GisfrFile, ProductMeta, RadarEntry
from .plot import plot_mosaic, quicklook
from .colormaps import reflectivity_cmap, velocity_cmap, cmap_for_product

__all__ = [
    "GisfrFile", "ProductMeta", "RadarEntry",
    "plot_mosaic", "quicklook",
    "reflectivity_cmap", "velocity_cmap", "cmap_for_product",
]
