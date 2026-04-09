"""Wrapper for wget --mirror command."""

import subprocess
import logging
import time
from dataclasses import dataclass
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class WgetResult:
    success: bool
    output_dir: str
    files_downloaded: List[str]
    errors: List[str]
    files_skipped: int = 0

def run_wget_mirror(
    url: str,
    output_dir: str,
    depth: int = 0,
    delay: int = 0,
    include_extensions: str = "html,md,txt",
    incremental: bool = False
) -> WgetResult:
    """Run wget --mirror with the specified options."""
    
    # Check if wget is installed
    try:
        subprocess.run(["wget", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError:
        raise RuntimeError("wget is required. Install with: brew install wget (macOS) or apt install wget (Linux)")

    # Build command
    cmd = ["wget"]
    
    if incremental:
        cmd.extend([
            "--timestamping",
            "--recursive",
            "--convert-links",
            "--adjust-extension",
            "--page-requisites",
            "--no-parent",
            f"--directory-prefix={output_dir}"
        ])
    else:
        cmd.extend([
            "--mirror",
            "--convert-links",
            "--adjust-extension",
            "--page-requisites",
            "--no-parent",
            f"--directory-prefix={output_dir}"
        ])

    if depth > 0:
        cmd.append(f"--level={depth}")
    
    if delay > 0:
        delay_seconds = delay / 1000.0
        cmd.append(f"--wait={delay_seconds}")
    
    if include_extensions:
        # e.g. "html,md,txt" -> "--accept=html,md,txt"
        cmd.append(f"--accept={include_extensions}")
        
    cmd.append(url)

    max_retries = 3
    attempt = 0
    success = False
    stdout_output = ""
    stderr_output = ""
    errors = []

    while attempt < max_retries and not success:
        attempt += 1
        logger.info(f"Running wget (attempt {attempt}/{max_retries}): {' '.join(cmd)}")
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_output += result.stdout
        stderr_output += result.stderr
        
        if result.returncode == 0:
            success = True
        elif result.returncode == 8:
            logger.warning("wget returned 8 (Server error). Treating as partial success.")
            success = True
            errors.append("Server error on some URLs (exit code 8)")
        else:
            logger.error(f"wget failed with exit code {result.returncode}")
            errors.append(f"Attempt {attempt} failed with exit code {result.returncode}")
            if attempt < max_retries:
                backoff_time = 2 ** attempt
                logger.info(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
            
    files_downloaded = []
    if success:
        outpath = Path(output_dir)
        if outpath.exists():
            files_downloaded = [str(p) for p in outpath.rglob('*') if p.is_file()]

    return WgetResult(
        success=success,
        output_dir=output_dir,
        files_downloaded=files_downloaded,
        errors=errors
    )
