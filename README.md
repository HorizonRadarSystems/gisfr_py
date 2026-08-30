# gisfr_py

A small, dependency-light Python package for reading and plotting **GISFR**
(Geospatial Integrated Scan Format) radar mosaic files — the kind of thing
[Py-ART](https://arm-doe.github.io/pyart/) is for NEXRAD/ODIM radar data,
but for this one specific format.

If you just want the ten-second version:

```python
from gisfr_py import GisfrFile, plot_mosaic

with GisfrFile.open("FRANCE_2026-08-30_1030_REF_VEL_RAWREF.gisfr") as gf:
    idx = gf.find_product("REF")
    meta = gf.read_metadata(idx)
    data, quality = gf.decode_full_mosaic(idx)

plot_mosaic(data, meta)
```

That opens a matplotlib window with a colored reflectivity mosaic, radar
site markers, and a colorbar — no map library, no compiler, no Qt.

## What's a GISFR file?

GISFR is a compact binary format for a *national radar mosaic* — many
individual radars' scans, already merged into one seamless grid over a
country. A single `.gisfr` file can hold more than one **product** (e.g.
reflectivity and velocity together), each stored as its own independent,
compressed section. Every value in the grid is either a real reading or
`NaN` ("no data" — outside every radar's range, or over ocean/dead zones).

The four product codes you'll see:

| Code     | Meaning                          |
|----------|-----------------------------------|
| `REF`    | Corrected reflectivity (dBZ)      |
| `VEL`    | Radial velocity (m/s)             |
| `RAWREF` | Uncorrected/total reflectivity    |
| `WIDTH`  | Spectrum width (rarely present)   |

This package is a from-scratch, independent implementation of the format's
spec — it doesn't wrap or depend on the C++ application that produces these
files. `pip install numpy matplotlib` (or just having them already) is
everything you need.

## Installation

Not published on PyPI (yet) — install straight from GitHub:

```bash
pip install git+https://github.com/HorizonRadarSystems/gisfr_py.git
```

Or clone it and install locally for development:

```bash
git clone https://github.com/HorizonRadarSystems/gisfr_py.git
cd gisfr_py
pip install -e .
```

Either way, the only real dependencies are `numpy` and `matplotlib`.

## Reading a file

`GisfrFile` opens a `.gisfr` file and parses every product section's
metadata up front (cheap — this never touches actual pixel data), so you
can inspect what's inside before deciding what to decode:

```python
from gisfr_py import GisfrFile

with GisfrFile.open("mosaic.gisfr") as gf:
    print(gf.product_count, "product section(s)")

    for i in range(gf.product_count):
        meta = gf.read_metadata(i)
        print(meta.product_code, meta.width, meta.height, len(meta.radars))
```

Use `find_product()` to look one up by code instead of guessing the index:

```python
    idx = gf.find_product("VEL")   # -> int, or None if this file has no VEL section
```

### Decoding pixel data

```python
    data, quality = gf.decode_full_mosaic(idx)
```

- `data` — a 2D `numpy.float32` array shaped `(height, width)`. Row 0 is the
  *north* edge (the grid's `max_lat`). Cells with no radar coverage are `NaN`.
- `quality` — a 2D `numpy.uint8` array (0–255, higher = more confidence) if
  the file carries a quality mask, otherwise `None`.

If you only need a small area, `decode_tile()` decodes just one tile
without touching the rest of the file:

```python
    tile_data, tile_quality = gf.decode_tile(idx, tx=0, ty=0)
```

### The metadata object

`read_metadata()` returns a `ProductMeta`:

| Field                  | Type              | Meaning                                      |
|-------------------------|-------------------|-----------------------------------------------|
| `product_code`          | `str`             | `"REF"` / `"VEL"` / `"RAWREF"` / `"WIDTH"`    |
| `timestamp_ms`          | `int`             | Unix milliseconds (UTC)                       |
| `width`, `height`       | `int`             | Grid size in pixels                           |
| `nominal_resolution_m`  | `float`           | Approx. meters/pixel at the grid's center     |
| `min_lat`/`min_lon`/`max_lat`/`max_lon` | `float` | Bounding box (plain lon/lat degrees)   |
| `tile_size`             | `int`             | Tile edge length in pixels                    |
| `tile_count_x`/`tile_count_y` | `int`       | Tile grid dimensions                          |
| `radars`                | `list[RadarEntry]`| Every radar that contributed to this mosaic   |

Each `RadarEntry` has `id`, `name`, `lat`, `lon`, `elevation_m`,
`scan_elevation_deg`, `beam_height_m`, and `quality_weight`.

## Plotting

`plot_mosaic()` takes decoded data straight from `decode_full_mosaic()` and
draws it on a matplotlib `Axes` in plain longitude/latitude coordinates —
the grid is already a flat lon/lat raster, so no map projection is needed:

```python
from gisfr_py import plot_mosaic

fig, ax = plot_mosaic(data, meta)
fig.savefig("mosaic.png", dpi=150, bbox_inches="tight")
```

It automatically picks a colormap matching the product (a classic NWS-style
reflectivity ramp for `REF`/`RAWREF`, a green/red velocity ramp for `VEL`),
plots every contributing radar as a labeled triangle, and adds a colorbar
and title. Pass `ax=` to draw into an existing figure, or
`show_radars=False`/`show_colorbar=False` to turn those off.

For the common case of "just open this file and show me one product",
`quicklook()` does the open-decode-plot dance in one call:

```python
from gisfr_py import quicklook

fig, ax = quicklook("mosaic.gisfr", product="REF", out_path="ref.png")
```

Leave `out_path` off to get the figure back without saving it.

### Using the color scales directly

If you're building your own plot and just want the matching colors:

```python
from gisfr_py import cmap_for_product

cmap, norm = cmap_for_product("REF")   # or reflectivity_cmap() / velocity_cmap() directly
ax.imshow(data, cmap=cmap, norm=norm)
```

`norm` is a `matplotlib.colors.Normalize` already set to the right value
range for that product — pass both to any matplotlib plotting call
(`imshow`, `pcolormesh`, `scatter`, ...) for a consistent look.

## Command line

No script required for a quick look:

```bash
python -m gisfr_py info mosaic.gisfr
```
```
mosaic.gisfr: 2 product section(s)
  [0] REF: 1178x1161 px (5x5 tiles @ 256px, ~1000m/px), 26 radar(s), bbox=(41.00,-5.50)-(51.50,9.80)
        - trappes (Trappes) at 48.7746,2.0083, tilt 0.4 deg
        ...
```

```bash
python -m gisfr_py plot mosaic.gisfr --product REF -o ref.png
python -m gisfr_py plot mosaic.gisfr --product VEL        # opens an interactive window instead
```

## Notes

- **NaN means "no data"**, everywhere — not zero, not missing-but-assume-clear.
  Always check for it before doing math on the raw array.
- The grid is a plain equirectangular (uniform-degree) raster, not an
  equal-area projection — fine for display and analysis at country scale,
  but keep that in mind for anything distance-sensitive near the edges of a
  large bounding box.
- This package intentionally has no dependency on the format's C++
  producer — if you find a `.gisfr` file that this package can't read
  correctly, that's a bug worth reporting here, not something to work around.

## License

MIT — see [LICENSE](LICENSE).
