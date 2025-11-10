#!/usr/bin/env python3
"""
Script to start the video processing worker.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.tasks.video_worker import run_worker

if __name__ == "__main__":
    run_worker()
