"""Parser for exclusion rules."""

import os
import logging
from typing import List, Optional

import pathspec

logger = logging.getLogger(__name__)

def filter_files(file_paths: List[str], ignore_file: Optional[str], ignore_patterns: List[str], base_dir: str) -> List[str]:
    """Applies pathspec validation filtering against `.docsignore` files and inline filters."""
    patterns = []
    
    # Load from ignore_file if it exists
    if ignore_file and os.path.exists(ignore_file):
        try:
            with open(ignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except Exception as e:
            logger.warning(f"Could not read ignore file {ignore_file}: {e}")

    # Combine with inline patterns
    for pat in ignore_patterns:
        if pat.strip():
            patterns.append(pat.strip())
            
    if not patterns:
        # No patterns, everything passes
        return list(file_paths)
        
    spec = pathspec.PathSpec.from_lines('gitignore', patterns)
    
    filtered_paths = []
    for full_path in file_paths:
        try:
            rel_path = os.path.relpath(full_path, base_dir)
            
            # pathspec handles unix separators uniformly best
            unix_rel_path = rel_path.replace(os.sep, '/')
            
            if spec.match_file(unix_rel_path):
                logger.debug(f"Excluded: {unix_rel_path}")
            else:
                filtered_paths.append(full_path)
        except ValueError:
            # If path represents something outside base_dir just append it implicitly
            filtered_paths.append(full_path)
            
    return filtered_paths
