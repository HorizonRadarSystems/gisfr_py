"""Command-line entry point: `python -m gisfr_py <command> ...`"""
from __future__ import annotations

import argparse
import sys

from .reader import GisfrFile


def _cmd_info(args):
    with GisfrFile.open(args.path) as gf:
        print(f"{args.path}: {gf.product_count} product section(s)")
        for i in range(gf.product_count):
            m = gf.read_metadata(i)
            print(f"  [{i}] {m.product_code}: {m.width}x{m.height} px "
                  f"({m.tile_count_x}x{m.tile_count_y} tiles @ {m.tile_size}px, "
                  f"~{m.nominal_resolution_m:.0f}m/px), {len(m.radars)} radar(s), "
                  f"bbox=({m.min_lat:.2f},{m.min_lon:.2f})-({m.max_lat:.2f},{m.max_lon:.2f})")
            for r in m.radars:
                print(f"        - {r.id} ({r.name}) at {r.lat:.4f},{r.lon:.4f}, "
                      f"tilt {r.scan_elevation_deg:.1f} deg")


def _cmd_plot(args):
    import matplotlib
    if args.out:
        matplotlib.use("Agg")  # headless - no display needed when just saving a file
    import matplotlib.pyplot as plt
    from .plot import quicklook

    fig, _ax = quicklook(args.path, product=args.product, out_path=args.out, dpi=args.dpi)
    if args.out:
        print(f"Saved {args.out}")
    else:
        plt.show()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gisfr_py", description="GISFR mosaic reader/plotter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="Print the product sections/radars in a .gisfr file")
    p_info.add_argument("path")
    p_info.set_defaults(func=_cmd_info)

    p_plot = sub.add_parser("plot", help="Plot one product with matplotlib")
    p_plot.add_argument("path")
    p_plot.add_argument("--product", "-p", default=None,
                         help="REF/VEL/RAWREF/WIDTH (default: first section in the file)")
    p_plot.add_argument("--out", "-o", default=None,
                         help="Save to this file instead of opening an interactive window")
    p_plot.add_argument("--dpi", type=int, default=150)
    p_plot.set_defaults(func=_cmd_plot)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
