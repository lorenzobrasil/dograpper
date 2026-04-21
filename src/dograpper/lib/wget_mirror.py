"""Wrapper for wget --mirror command."""

import subprocess
import logging
import tempfile
import time
from dataclasses import dataclass
from typing import List
from pathlib import Path

from dograpper.utils.dep_resolver import resolve_wget

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}

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
    wget_bin = resolve_wget()
    try:
        subprocess.run([wget_bin, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError:
        raise RuntimeError("wget is required. Install with: brew install wget (macOS) or apt install wget (Linux)")

    cmd = [wget_bin]
    cmd.extend(["--timestamping", "--recursive"] if incremental else ["--mirror"])
    cmd.extend([
        "--convert-links",
        "--adjust-extension",
        "--page-requisites",
        "--no-parent",
        f"--directory-prefix={output_dir}",
        f"--user-agent={BROWSER_UA}",
    ])

    for header_name, header_value in BROWSER_HEADERS.items():
        cmd.append(f"--header={header_name}: {header_value}")

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


def run_wget_urls(
    urls: List[str],
    output_dir: str,
    delay: int = 0,
    include_extensions: str = "html,md,txt",
) -> WgetResult:
    """Download an explicit URL list via `wget -i <file>`.

    Always uses `--timestamping` so that `_compute_stats` mtime-diff semantics
    work correctly on both first-run and subsequent-run invocations.
    """
    if not urls:
        return WgetResult(success=True, output_dir=output_dir, files_downloaded=[], errors=[])

    wget_bin = resolve_wget()
    try:
        subprocess.run([wget_bin, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError:
        raise RuntimeError("wget is required. Install with: brew install wget (macOS) or apt install wget (Linux)")

    url_list_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".urls.txt", delete=False, encoding="utf-8"
    )
    try:
        for u in urls:
            url_list_file.write(u + "\n")
        url_list_file.close()

        cmd = [
            wget_bin,
            "--timestamping",
            "--convert-links",
            "--adjust-extension",
            "--page-requisites",
            "--no-parent",
            f"--directory-prefix={output_dir}",
            f"--user-agent={BROWSER_UA}",
            "-i", url_list_file.name,
        ]
        for header_name, header_value in BROWSER_HEADERS.items():
            cmd.append(f"--header={header_name}: {header_value}")

        if delay > 0:
            cmd.append(f"--wait={delay / 1000.0}")
        if include_extensions:
            cmd.append(f"--accept={include_extensions}")

        max_retries = 3
        attempt = 0
        success = False
        errors: List[str] = []

        while attempt < max_retries and not success:
            attempt += 1
            logger.info(
                f"Running wget -i (attempt {attempt}/{max_retries}) "
                f"on {len(urls)} URLs: {' '.join(cmd)}"
            )
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                success = True
            elif result.returncode == 8:
                logger.warning("wget -i returned 8 (Server error). Treating as partial success.")
                success = True
                errors.append("Server error on some URLs (exit code 8)")
            else:
                logger.error(f"wget -i failed with exit code {result.returncode}")
                errors.append(f"Attempt {attempt} failed with exit code {result.returncode}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)

        files_downloaded: List[str] = []
        if success:
            outpath = Path(output_dir)
            if outpath.exists():
                files_downloaded = [str(p) for p in outpath.rglob("*") if p.is_file()]

        return WgetResult(
            success=success,
            output_dir=output_dir,
            files_downloaded=files_downloaded,
            errors=errors,
        )
    finally:
        try:
            Path(url_list_file.name).unlink()
        except OSError:
            pass
