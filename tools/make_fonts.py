#!/usr/bin/env python3
"""Older workflow entry point. Everything now lives in build_sprites.py."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("build_sprites.py")), run_name="__main__")
