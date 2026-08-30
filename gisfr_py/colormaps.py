"""Radar colormaps matching the HSMAIN desktop app's own palettes exactly -
see RadarPalette::defaultReflectivity()/defaultVelocity() in
../../src/RadarPalette.cpp, whose (value, color) stops are copied verbatim
below so a mosaic plotted here looks the same as it does in the app,
instead of an arbitrary matplotlib stock colormap.

RadarPalette::colorFor() linearly interpolates between whichever two stops
bracket a value; matplotlib.colors.LinearSegmentedColormap.from_list() does
the same thing given (fraction, color) pairs, so building the fraction from
each stop's real value (not its rank/index) reproduces that exactly, even
though the stops themselves are unevenly spaced.
"""
from __future__ import annotations

from typing import List, Tuple

import matplotlib.colors as mcolors

# (value, "#RRGGBB") - straight from RadarPalette::defaultReflectivity().
REFLECTIVITY_STOPS: List[Tuple[float, str]] = [
    (-30, "#6C0000"), (-20, "#566A33"), (-10, "#228D1D"), (-5, "#00CE61"),
    (0, "#3EB273"), (3, "#69C8B8"), (6, "#7A69ED"), (9, "#0300FE"),
    (12, "#02008B"), (15, "#66238C"), (18, "#883D5B"), (21, "#AB3267"),
    (24, "#8A2352"), (27, "#A44F2F"), (31, "#D56D1D"), (35, "#D7A619"),
    (40, "#CBCF00"), (45, "#EB9679"), (50, "#FB806E"), (55, "#EF2B2B"),
    (60, "#FF1492"), (65, "#D3D3D3"), (70, "#FFFFFF"), (100, "#000000"),
]

# (value, "#RRGGBB") - straight from RadarPalette::defaultVelocity() (green/
# blue inbound -> gray at zero -> yellow/red outbound, classic NWS SRV/BV).
VELOCITY_STOPS: List[Tuple[float, str]] = [
    (-64, "#003399"), (-50, "#003399"), (-36, "#3333CC"), (-26, "#6666FF"),
    (-20, "#6699CC"), (-15, "#99CCFF"), (-10, "#33CCCC"), (-5, "#339999"),
    (-1, "#336666"), (0, "#000000"), (1, "#999900"), (5, "#999900"),
    (10, "#CCCC00"), (15, "#FFFF00"), (20, "#FFCC00"), (26, "#FF9933"),
    (36, "#FF6600"), (50, "#FF0000"), (64, "#CC0033"), (70, "#FF00CC"),
]


def _cmap_from_stops(stops: List[Tuple[float, str]]):
    values = [v for v, _ in stops]
    vmin, vmax = min(values), max(values)
    span = vmax - vmin
    positions = [(v - vmin) / span for v, _ in stops]
    colors = [c for _, c in stops]
    cmap = mcolors.LinearSegmentedColormap.from_list("gisfr", list(zip(positions, colors)))
    cmap.set_bad(alpha=0.0)  # NaN (no data) -> fully transparent, not a solid color
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    return cmap, norm


def reflectivity_cmap():
    """Returns (cmap, norm) for REF/RAWREF, in dBZ."""
    return _cmap_from_stops(REFLECTIVITY_STOPS)


def velocity_cmap():
    """Returns (cmap, norm) for VEL, in m/s."""
    return _cmap_from_stops(VELOCITY_STOPS)


def cmap_for_product(product_code: str):
    """Returns (cmap, norm) for a GISFR product code. WIDTH has no
    dedicated palette in the app (see FrenchRadarMosaicGenerator's own note
    that neither ORD nor DPRadar publish it for France) - falls back to the
    reflectivity ramp, same as RadarPalette::defaultForProduct() does for
    any code it doesn't recognize."""
    if product_code == "VEL":
        return velocity_cmap()
    return reflectivity_cmap()
