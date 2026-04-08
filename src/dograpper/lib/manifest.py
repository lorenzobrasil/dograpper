"""Manifest management and generation."""

import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class ManifestEntry:
    url: str
    size_bytes: int
    etag: Optional[str] = None
    last_modified: Optional[str] = None

@dataclass
class Manifest:
    base_url: str
    last_run: str
    files: Dict[str, ManifestEntry]

def load_manifest(path: str) -> Optional[Manifest]:
    """Load manifest from disk."""
    if not os.path.exists(path):
        return None
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        files = {
            k: ManifestEntry(**v) 
            for k, v in data.get('files', {}).items()
        }
        
        return Manifest(
            base_url=data.get('base_url', ''),
            last_run=data.get('last_run', ''),
            files=files
        )
    except Exception as e:
        logger.warning(f"Failed to parse manifest at {path}, treating as missing: {e}")
        return None

def save_manifest(manifest: Manifest, path: str) -> None:
    """Save manifest to disk."""
    d = asdict(manifest)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save manifest to {path}: {e}")

def build_manifest(base_url: str, output_dir: str) -> Manifest:
    """Build a manifest based on the output directory contents."""
    files = {}
    last_run = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    # Strip trailing slash from base_url for consistent appending
    clean_base = base_url.rstrip('/')
    
    for root, _, filenames in os.walk(output_dir):
        for f in filenames:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, output_dir)
            size = os.path.getsize(full_path)
            
            # Reconstruct an approximate URL
            # Note: For wget, rel_path might already include the domain folder.
            # Building a robust manifest relies on how wget or playwright stored files.
            # We assume reconstructing by just appending rel_path.
            # If rel_path starts with domain, we might need to strip it.
            # For simplicity per the prompt, we just store it.
            url_approx = f"{clean_base}/{rel_path}"
            
            # Using Unix style paths for keys
            key = rel_path.replace(os.sep, '/')
            
            files[key] = ManifestEntry(
                url=url_approx,
                size_bytes=size,
                etag=None,
                last_modified=None
            )
            
    return Manifest(
        base_url=base_url,
        last_run=last_run,
        files=files
    )
