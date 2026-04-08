"""Core logical engine for chunking texts natively in Python."""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict

from ..utils.word_counter import count_words_file

logger = logging.getLogger(__name__)

@dataclass
class ChunkFile:
    relative_path: str
    word_count: int

@dataclass
class Chunk:
    index: int
    files: List[ChunkFile] = field(default_factory=list)
    total_words: int = 0

def chunk_by_size(files: List[str], base_dir: str, max_words: int) -> List[Chunk]:
    """Group incoming files in chunks keeping them under the soft limit max_words per chunk."""
    
    # Sort alphabetically to keep things predictable
    sorted_files = sorted(files)
    
    chunks = []
    current_chunk = Chunk(index=1)
    
    for f in sorted_files:
        words = count_words_file(f)
        rel_path = os.path.relpath(f, base_dir).replace(os.sep, '/')
        
        # Especial case: Single immense file
        if words > max_words:
            logger.warning(f"File '{rel_path}' has {words} words, exceeding max-words-per-chunk limit of {max_words}. Placing in its own chunk.")
            # If current chunk has something, wrap it up
            if current_chunk.files:
                chunks.append(current_chunk)
                current_chunk = Chunk(index=len(chunks) + 1)
            
            # Form special massive chunk
            special_chunk = Chunk(index=current_chunk.index, files=[ChunkFile(rel_path, words)], total_words=words)
            chunks.append(special_chunk)
            
            # Advance ptr
            current_chunk = Chunk(index=len(chunks) + 1)
            continue
            
        if current_chunk.total_words + words > max_words:
            # Reached threshold for chunk, wrap and restart
            if current_chunk.files:
                chunks.append(current_chunk)
                current_chunk = Chunk(index=len(chunks) + 1)
                
        current_chunk.files.append(ChunkFile(rel_path, words))
        current_chunk.total_words += words
        
    if current_chunk.files:
        chunks.append(current_chunk)
        
    return chunks

def chunk_by_semantic(files: List[str], base_dir: str, max_words: int) -> List[Chunk]:
    """Groups files keeping immediate parent directories together when possible."""
    
    groups: Dict[str, List[str]] = {}
    for f in files:
        rel = os.path.relpath(f, base_dir)
        parts = rel.split(os.sep)
        # Using top-level directory as "module" proxy. If it's in root, group is '_'
        mod = parts[0] if len(parts) > 1 else '_'
        if mod not in groups:
            groups[mod] = []
        groups[mod].append(f)
    
    # Sort groups alphabetically
    sorted_mods = sorted(groups.keys())
    
    chunks = []
    current_chunk = Chunk(index=1)
    
    for mod in sorted_mods:
        mod_files = sorted(groups[mod])
        
        # Calculate group's total weight
        mod_word_counts = []
        mod_total_words = 0
        for f in mod_files:
            wc = count_words_file(f)
            rel_path = os.path.relpath(f, base_dir).replace(os.sep, '/')
            mod_word_counts.append((f, rel_path, wc))
            mod_total_words += wc
            
        if mod_total_words <= max_words:
            if current_chunk.total_words + mod_total_words > max_words:
                # Group doesn't fit here, open new
                if current_chunk.files:
                    chunks.append(current_chunk)
                    current_chunk = Chunk(index=len(chunks) + 1)
            
            # Add entire group
            for f, rel_p, wc in mod_word_counts:
                current_chunk.files.append(ChunkFile(rel_p, wc))
                current_chunk.total_words += wc
        else:
            # Group exceeds max_words, break it using internal `size` strategy for these files
            if current_chunk.files:
                chunks.append(current_chunk)
                current_chunk = Chunk(index=len(chunks) + 1)
                
            sub_chunks = chunk_by_size(mod_files, base_dir, max_words)
            for sc in sub_chunks:
                sc.index = current_chunk.index
                chunks.append(sc)
                current_chunk = Chunk(index=len(chunks) + 1)
                
    if current_chunk.files:
        chunks.append(current_chunk)
        
    # Re-index all chunks strictly sequentially
    for i, c in enumerate(chunks):
        c.index = i + 1
        
    return chunks

def write_chunks(chunks: List[Chunk], base_dir: str, output_dir: str, prefix: str, format: str, with_index: bool, total_chunks: int) -> List[str]:
    """Flush chunk classes out as disk files with or without headings."""
    os.makedirs(output_dir, exist_ok=True)
    generated_paths = []
    
    for chunk in chunks:
        out_filename = f"{prefix}{chunk.index:02d}.{format}"
        out_filepath = os.path.join(output_dir, out_filename)
        generated_paths.append(out_filepath)
        
        with open(out_filepath, 'w', encoding='utf-8') as f:
            if with_index:
                f.write(f"# Chunk {chunk.index:02d} de {total_chunks:02d}\n\n")
                f.write(f"## Arquivos neste chunk ({len(chunk.files)} arquivos, ~{chunk.total_words} palavras):\n")
                for cf in chunk.files:
                    f.write(f"- {cf.relative_path} ({cf.word_count} palavras)\n")
                f.write("\n---\n\n")
            
            for i, cf in enumerate(chunk.files):
                if i > 0:
                    f.write("\n\n")
                f.write(f"<!-- SOURCE: {cf.relative_path} -->\n\n")
                
                # Fetch text content inside try catch
                true_filepath = os.path.join(base_dir, cf.relative_path)
                try:
                    with open(true_filepath, 'r', encoding='utf-8', errors='replace') as source_f:
                        f.write(source_f.read())
                except Exception as e:
                    logger.error(f"Failed to copy contents of {cf.relative_path}: {e}")
                    f.write(f"<!-- Excluded unreadable blob: {e} -->")
                    
    return generated_paths
