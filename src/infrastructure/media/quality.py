"""Quality gate helpers (PSNR / VMAF via ffmpeg)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


def _parse_vmaf(stderr: str) -> Optional[float]:
    # lavfi libvmaf often prints: VMAF score: 92.345678
    m = re.search(r"VMAF\s+score:\s*([0-9.]+)", stderr, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"vmaf[=\s]+([0-9.]+)", stderr, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _parse_psnr(stderr: str) -> Optional[float]:
    # psnr_avg:45.12 or average:45.12
    m = re.search(r"psnr_avg:([0-9.]+)", stderr, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"average:([0-9.]+)\s+min:", stderr, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def run_psnr_or_vmaf(
    reference: Path,
    distorted: Path,
) -> Tuple[Optional[float], str]:
    """
    Compare distorted vs reference with ffmpeg.

    Prefers libvmaf when available; falls back to PSNR.
    Returns (score, metric_name) where metric_name is "vmaf" or "psnr".
    """
    ref = str(reference)
    dist = str(distorted)

    # Try VMAF first
    vmaf_cmd = [
        "ffmpeg",
        "-i",
        dist,
        "-i",
        ref,
        "-lavfi",
        "libvmaf=log_fmt=json:log_path=/dev/null",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(vmaf_cmd, capture_output=True, text=True, timeout=600)
        score = _parse_vmaf((result.stderr or "") + (result.stdout or ""))
        if score is not None:
            return score, "vmaf"
        if result.returncode == 0:
            # Sometimes score is only in stderr with different format; try again soft
            logger.debug("VMAF ran but score not parsed")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("VMAF attempt failed: %s", exc)

    psnr_cmd = [
        "ffmpeg",
        "-i",
        dist,
        "-i",
        ref,
        "-lavfi",
        "psnr",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(psnr_cmd, capture_output=True, text=True, timeout=600)
        score = _parse_psnr((result.stderr or "") + (result.stdout or ""))
        if score is not None:
            return score, "psnr"
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("PSNR attempt failed: %s", exc)

    return None, "none"


def evaluate_quality_gate(
    reference: Path,
    distorted: Path,
) -> Tuple[Optional[float], bool]:
    """
    Run quality metric and decide pass/fail against QUALITY_GATE_MIN_VMAF.

    Returns (score, passed). When gate disabled, always passes with optional score.
    """
    if not settings.QUALITY_GATE_ENABLED:
        return None, True

    score, metric = run_psnr_or_vmaf(reference, distorted)
    if score is None:
        if settings.QUALITY_GATE_STRICT:
            logger.warning("Quality gate strict: no score computed")
            return None, False
        return None, True

    # PSNR is not VMAF; treat min threshold only as VMAF-like when metric is vmaf.
    # For PSNR, map loosely: pass if psnr >= 30 (reasonable encode floor).
    if metric == "vmaf":
        passed = score >= settings.QUALITY_GATE_MIN_VMAF
    else:
        passed = score >= 30.0

    if not passed:
        logger.warning(
            "Quality gate failed: %s=%.2f (min_vmaf=%.1f)",
            metric,
            score,
            settings.QUALITY_GATE_MIN_VMAF,
        )
    return score, passed
