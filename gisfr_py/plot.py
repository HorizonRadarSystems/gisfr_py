"""Matplotlib plotting for GISFR mosaics - the Py-ART-`display.plot_ppi()`
equivalent for this format. Unlike a PPI (which needs a real map projection
to place a site-centered polar sweep on a map), a GISFR mosaic is already a
plain equirectangular lon/lat grid (see GisfrFormat.h) - so plotting it is
just imshow() with the right extent, no cartopy/basemap dependency required.
"""
from __future__ import annotations

import datetime
from typing import Optional

import numpy as np

from .colormaps import cmap_for_product
from .reader import GisfrFile, ProductMeta


def plot_mosaic(data: np.ndarray, meta: ProductMeta, ax=None, show_radars: bool = True,
                 show_colorbar: bool = True, title: Optional[str] = None):
    """Plots one decoded GISFR product grid (as returned by
    GisfrFile.decode_full_mosaic()) onto a matplotlib Axes in plain lon/lat
    coordinates. Returns (fig, ax) so the caller can keep customizing
    (add_feature-style boundary overlays, save, etc.) the same way a Py-ART
    RadarMapDisplay call does.
    """
    import matplotlib.pyplot as plt  # deferred: lets callers pick a backend first

    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 8))
    else:
        fig = ax.figure

    cmap, norm = cmap_for_product(meta.product_code)
    # extent=(left, right, bottom, top) with origin="upper" places row 0 at
    # `top` - correct here since row 0 is the max_lat (north) edge, the same
    # convention GisfrFormat.h documents for the whole grid.
    extent = (meta.min_lon, meta.max_lon, meta.min_lat, meta.max_lat)
    im = ax.imshow(data, cmap=cmap, norm=norm, extent=extent, origin="upper",
                    interpolation="nearest")

    if show_radars:
        for r in meta.radars:
            ax.plot(r.lon, r.lat, marker="^", color="black", markersize=6,
                    markerfacecolor="white", markeredgewidth=1.2, zorder=5)
            ax.annotate(r.id.upper(), (r.lon, r.lat), textcoords="offset points",
                        xytext=(4, 4), fontsize=7, color="black", zorder=5)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    ax.set_xlim(meta.min_lon, meta.max_lon)
    ax.set_ylim(meta.min_lat, meta.max_lat)

    if show_colorbar:
        units = {"REF": "dBZ", "RAWREF": "dBZ", "VEL": "m/s"}.get(meta.product_code, "")
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label(f"{meta.product_code} ({units})" if units else meta.product_code)

    if title is None:
        ts = datetime.datetime.utcfromtimestamp(meta.timestamp_ms / 1000.0)
        title = (f"GISFR {meta.product_code} mosaic - {ts:%Y-%m-%d %H:%M} UTC "
                 f"({len(meta.radars)} radar{'s' if len(meta.radars) != 1 else ''})")
    ax.set_title(title)

    return fig, ax


def quicklook(path: str, product: Optional[str] = None, out_path: Optional[str] = None,
              dpi: int = 150, **plot_kwargs):
    """One-call convenience: open a .gisfr file, decode one product, plot
    it, and optionally save. `product` picks a section by code ("REF",
    "VEL", ...); defaults to whichever section is first in the file.
    Returns (fig, ax) either way - pass out_path=None to keep it interactive.
    """
    with GisfrFile.open(path) as gf:
        if gf.product_count == 0:
            raise ValueError(f"{path}: no product sections")
        idx = 0
        if product is not None:
            found = gf.find_product(product)
            if found is None:
                available = [gf.read_metadata(i).product_code for i in range(gf.product_count)]
                raise ValueError(f"{path}: product {product!r} not found (available: {available})")
            idx = found
        meta = gf.read_metadata(idx)
        data, _quality = gf.decode_full_mosaic(idx)

    fig, ax = plot_mosaic(data, meta, **plot_kwargs)
    if out_path:
        fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    return fig, ax
