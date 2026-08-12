#!/usr/bin/env python3
"""
Script to start the video processing worker.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.worker.runner import run_worker

if __name__ == "__main__":
    run_worker()
