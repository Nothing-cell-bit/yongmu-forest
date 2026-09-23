#!/usr/bin/env python3
"""Regenerate the current original Cindercoil atlases; compatibility entrypoint."""
import argparse
from pathlib import Path
try:
    from tools.build_cindercoil_v2 import build_textures
except ImportError:
    from build_cindercoil_v2 import build_textures


def build(output_dir):
    build_textures(output_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    build(parser.parse_args().output_dir)
