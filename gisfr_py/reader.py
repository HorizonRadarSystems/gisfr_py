"""Pure-Python, dependency-light (numpy only) reader for GISFR files.

Mirrors GisfrReader in ../../src/GisfrFormat.h/.cpp field-for-field and
byte-for-byte - see that header's own comment for the full binary layout.
Kept as an independent implementation (not a wrapper around the C++ code)
so this package has no build step: `pip install numpy matplotlib` and a
plain `import gisfr_py` is enough, no compiler or Qt required.
"""
from __future__ import annotations

import dataclasses
import struct
import zlib
from typing import BinaryIO, List, Optional, Tuple

import numpy as np

MAGIC = b"HORIZONSYSTEMS"

# See GisfrFormat.h's ProductType enum - REF/VEL/RAWREF/WIDTH are this
# format's own names (deliberately not ODIM's DBZH/VRADH/TH/WRADH).
PRODUCT_CODES = {0: "REF", 1: "VEL", 2: "RAWREF", 3: "WIDTH"}
PRODUCT_IDS = {v: k for k, v in PRODUCT_CODES.items()}

# The NaN bit pattern GisfrFormat.cpp's rleEncode() reserves purely as an
# "RLE run follows" marker - never a literal data value (see its own comment).
_RLE_ESCAPE_BITS = 0x7FFFFFFF


@dataclasses.dataclass
class RadarEntry:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: float
    scan_elevation_deg: float
    beam_height_m: float
    quality_weight: float


@dataclasses.dataclass
class ProductMeta:
    version: int
    product: int          # raw GisfrProduct value (0..3)
    product_code: str      # "REF"/"VEL"/"RAWREF"/"WIDTH"
    timestamp_ms: int
    width: int
    height: int
    nominal_resolution_m: float
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    tile_size: int
    tile_count_x: int
    tile_count_y: int
    radars: List[RadarEntry]


@dataclasses.dataclass
class _TileEntry:
    offset: int
    compressed_size: int
    quality_compressed_size: int
    w: int
    h: int
    flags: int


def _rle_decode(buf: bytes, expected_count: int) -> np.ndarray:
    """Inverse of GisfrFormat.cpp's rleEncode(): a stream of little-endian
    uint32s, where the escape bit pattern is followed by a run length (that
    many NaNs), and anything else is one literal float32 value. Only NaN
    *runs* collapse to O(1) work here - real echo pixels are still one
    Python-level iteration each, which is fine for an offline plotting tool
    (not the "decode in milliseconds" bar the C++ decoder targets)."""
    out = np.empty(expected_count, dtype=np.float32)
    pos = 0
    n = len(buf)
    i = 0
    while pos + 4 <= n and i < expected_count:
        bits = struct.unpack_from("<I", buf, pos)[0]
        if bits == _RLE_ESCAPE_BITS:
            pos += 4
            run_len = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            end = min(i + run_len, expected_count)
            out[i:end] = np.nan
            i = end
        else:
            out[i] = struct.unpack_from("<f", buf, pos)[0]
            pos += 4
            i += 1
    if i < expected_count:
        out[i:] = np.nan  # truncated/corrupt tail - pad with "no data" rather than crash
    return out


class GisfrFile:
    """Random-access GISFR reader. openGISFR() in the C++ reader reads every
    section's metadata/radar directory/tile directory up front (all small,
    fixed-size data); this does the same in __init__, so product_count/
    read_metadata() are effectively free and decode_tile() seeks straight to
    one tile's bytes without touching any other tile."""

    def __init__(self, path: str):
        self._path = path
        self._fh: BinaryIO = open(path, "rb")
        # one (section_start, section_length, ProductMeta, [_TileEntry]) per product
        self._sections: List[Tuple[int, int, ProductMeta, List[_TileEntry]]] = []
        self._parse_header()

    @classmethod
    def open(cls, path: str) -> "GisfrFile":
        return cls(path)

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------- parsing

    def _read(self, fmt: str):
        size = struct.calcsize(fmt)
        buf = self._fh.read(size)
        if len(buf) != size:
            raise ValueError(f"{self._path}: truncated GISFR file (expected {size} bytes)")
        return struct.unpack(fmt, buf)

    def _parse_header(self):
        magic = self._fh.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError(f"{self._path}: not a GISFR file (missing {MAGIC!r} magic header)")

        _container_version, product_count = self._read("<HB")

        for _ in range(product_count):
            (section_len,) = self._read("<Q")
            section_start = self._fh.tell()

            (version, product, radar_count, timestamp_ms, width, height,
             grid_res, min_lat, min_lon, max_lat, max_lon,
             tile_size, tile_count_x, tile_count_y) = self._read("<HBHQHHfddddHHH")

            radars = []
            for _ in range(radar_count):
                (id_len,) = self._read("<B")
                rid = self._fh.read(id_len).decode("utf-8")
                (name_len,) = self._read("<B")
                name = self._fh.read(name_len).decode("utf-8")
                lat, lon, elev, scan_elev, beam_h, qweight = self._read("<ddffff")
                radars.append(RadarEntry(rid, name, lat, lon, elev, scan_elev, beam_h, qweight))

            tile_count = tile_count_x * tile_count_y
            tiles = []
            for _ in range(tile_count):
                offset, comp_size, qual_comp_size, aw, ah, flags = self._read("<QIIHHB")
                tiles.append(_TileEntry(offset, comp_size, qual_comp_size, aw, ah, flags))

            meta = ProductMeta(
                version=version, product=product, product_code=PRODUCT_CODES.get(product, "?"),
                timestamp_ms=timestamp_ms, width=width, height=height,
                nominal_resolution_m=grid_res,
                min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon,
                tile_size=tile_size, tile_count_x=tile_count_x, tile_count_y=tile_count_y,
                radars=radars,
            )
            self._sections.append((section_start, section_len, meta, tiles))

            # Jump straight to the next section instead of trusting our own
            # parse to have landed exactly right - the entire point of
            # SectionByteLength (see GisfrFormat.h).
            self._fh.seek(section_start + section_len)

    # --------------------------------------------------------- public API

    @property
    def product_count(self) -> int:
        return len(self._sections)

    def read_metadata(self, product_index: int) -> ProductMeta:
        return self._sections[product_index][2]

    def find_product(self, code: str) -> Optional[int]:
        """Returns the index of the first section matching a product code
        ("REF"/"VEL"/"RAWREF"/"WIDTH", case-insensitive), or None."""
        want = PRODUCT_IDS.get(code.upper())
        if want is None:
            return None
        for i, (_, _, meta, _) in enumerate(self._sections):
            if meta.product == want:
                return i
        return None

    @staticmethod
    def _tile_dims(meta: ProductMeta, tx: int, ty: int) -> Tuple[int, int]:
        w = min(meta.tile_size, meta.width - tx * meta.tile_size)
        h = min(meta.tile_size, meta.height - ty * meta.tile_size)
        return w, h

    def decode_tile(self, product_index: int, tx: int, ty: int
                     ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Returns (data, quality) for one tile - data is float32 (h, w)
        with NaN for no-coverage cells; quality is uint8 (h, w) or None if
        this tile carries no quality mask."""
        section_start, _section_len, meta, tiles = self._sections[product_index]
        if not (0 <= tx < meta.tile_count_x and 0 <= ty < meta.tile_count_y):
            raise IndexError(f"tile ({tx},{ty}) out of range for a {meta.tile_count_x}x"
                              f"{meta.tile_count_y}-tile grid")
        tile = tiles[ty * meta.tile_count_x + tx]
        w, h = self._tile_dims(meta, tx, ty)

        if tile.offset == 0 and tile.compressed_size == 0:
            return np.full((h, w), np.nan, dtype=np.float32), None

        self._fh.seek(section_start + tile.offset)
        _stored_tx, _stored_ty, compression_type = self._read("<HHB")
        compressed = self._fh.read(tile.compressed_size)
        raw = zlib.decompressobj(wbits=-15).decompress(compressed)

        if compression_type == 1:
            flat = _rle_decode(raw, w * h)
        else:
            flat = np.frombuffer(raw[: w * h * 4], dtype="<f4").astype(np.float32)
        data = flat.reshape((h, w))

        quality = None
        if tile.flags & 0x1:
            q_compressed = self._fh.read(tile.quality_compressed_size)
            q_raw = zlib.decompressobj(wbits=-15).decompress(q_compressed)
            quality = np.frombuffer(q_raw[: w * h], dtype=np.uint8).reshape((h, w)).copy()

        return data, quality

    def decode_full_mosaic(self, product_index: int
                            ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Assembles every tile into one (height, width) float32 array (NaN
        = no data) plus a matching uint8 quality array (or None if no tile
        in the file carried a quality mask) - the numpy equivalent of
        GisfrReader::decodeFullMosaic()."""
        meta = self.read_metadata(product_index)
        data = np.full((meta.height, meta.width), np.nan, dtype=np.float32)
        quality = None
        for ty in range(meta.tile_count_y):
            for tx in range(meta.tile_count_x):
                tile_data, tile_quality = self.decode_tile(product_index, tx, ty)
                r0 = ty * meta.tile_size
                c0 = tx * meta.tile_size
                th, tw = tile_data.shape
                data[r0:r0 + th, c0:c0 + tw] = tile_data
                if tile_quality is not None:
                    if quality is None:
                        quality = np.zeros((meta.height, meta.width), dtype=np.uint8)
                    quality[r0:r0 + th, c0:c0 + tw] = tile_quality
        return data, quality
