"""Core logical engine for chunking texts natively in Python."""

import os
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, field
from typing import List, Dict

from ..utils.word_counter import count_words_file
from ..utils.html_stripper import strip_html
from ..utils.content_extractor import extract_content

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

def chunk_by_size(files: List[str], base_dir: str, max_words: int, no_extract: bool = False, word_counts: Dict[str, int] = None) -> List[Chunk]:
    """Group incoming files in chunks keeping them under the soft limit max_words per chunk."""

    # Sort alphabetically to keep things predictable
    sorted_files = sorted(files)

    chunks = []
    current_chunk = Chunk(index=1)

    for f in sorted_files:
        rel_path = os.path.relpath(f, base_dir).replace(os.sep, '/')
        if word_counts and rel_path in word_counts:
            words = word_counts[rel_path]
        else:
            words = count_words_file(f, no_extract=no_extract)
        
        # Especial case: Single immense file
        if words > max_words:
            logger.warning(f"File '{rel_path}' has {words} words, exceeding max-words-per-chunk limit of {max_words}. Placing in its own chunk.")
            # If current chunk has something, wrap it up
            if current_chunk.files:
                chunks.append(current_chunk)

            # Form special massive chunk with a fresh, correct index
            special_chunk = Chunk(
                index=len(chunks) + 1,
                files=[ChunkFile(rel_path, words)],
                total_words=words,
            )
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

def chunk_by_semantic(files: List[str], base_dir: str, max_words: int, no_extract: bool = False, word_counts: Dict[str, int] = None) -> List[Chunk]:
    """Group files by their parent directory, keeping related content together.

    Uses the *full* relative directory path (``os.path.dirname``) as the module
    proxy so nested sections stay together instead of being flattened into the
    top-level folder bucket. Files directly in ``base_dir`` are placed in the
    ``_`` group.
    """

    groups: Dict[str, List[str]] = {}
    for f in files:
        rel = os.path.relpath(f, base_dir)
        dirname = os.path.dirname(rel).replace(os.sep, '/')
        mod = dirname if dirname else '_'
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
            rel_path = os.path.relpath(f, base_dir).replace(os.sep, '/')
            if word_counts and rel_path in word_counts:
                wc = word_counts[rel_path]
            else:
                wc = count_words_file(f, no_extract=no_extract)
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
                
            sub_chunks = chunk_by_size(mod_files, base_dir, max_words, no_extract=no_extract, word_counts=word_counts)
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

def _read_source_content(base_dir: str, cf: ChunkFile, no_extract: bool = False, text_overrides: Dict[str, str] = None) -> str:
    """Read a source file from disk, stripping HTML markup if applicable."""
    if text_overrides and cf.relative_path in text_overrides:
        return text_overrides[cf.relative_path]
    true_filepath = os.path.join(base_dir, cf.relative_path)
    try:
        with open(true_filepath, 'r', encoding='utf-8', errors='replace') as source_f:
            content = source_f.read()
        if cf.relative_path.lower().endswith(('.html', '.htm')):
            if not no_extract:
                content = extract_content(content)
            content = strip_html(content)
        return content
    except Exception as e:
        logger.error(f"Failed to copy contents of {cf.relative_path}: {e}")
        return f"[Excluded unreadable blob: {e}]"


def _format_file_header(cf: ChunkFile, heading_map: Dict = None) -> str:
    """Format per-file header with optional context from heading_map."""
    if heading_map is not None and cf.relative_path in heading_map:
        from ..utils.heading_extractor import get_active_headings, format_context_header
        headings = heading_map[cf.relative_path]
        if headings:
            # Use the last heading's offset to capture the full hierarchy
            last_offset = headings[-1].char_offset
            active = get_active_headings(headings, last_offset)
        else:
            active = []
        header = format_context_header(active_headings=active, source_path=cf.relative_path)
        if header:
            return header
    return ""


def _write_chunk_text(chunk: Chunk, base_dir: str, out_filepath: str, with_index: bool, total_chunks: int, no_extract: bool = False, text_overrides: Dict[str, str] = None, heading_map: Dict = None):
    """Write a chunk as plain text (no markdown or HTML markup)."""
    with open(out_filepath, 'w', encoding='utf-8') as f:
        if with_index:
            f.write(f"Chunk {chunk.index:02d} de {total_chunks:02d}\n")
            f.write(f"Arquivos neste chunk ({len(chunk.files)} arquivos, ~{chunk.total_words} palavras):\n")
            for cf in chunk.files:
                f.write(f"- {cf.relative_path} ({cf.word_count} palavras)\n")
            f.write("\n" + ("=" * 60) + "\n\n")

        for i, cf in enumerate(chunk.files):
            if i > 0:
                f.write("\n\n")
            ctx_header = _format_file_header(cf, heading_map)
            if ctx_header:
                f.write(ctx_header)
            else:
                f.write(f"=== SOURCE: {cf.relative_path} ===\n\n")
            f.write(_read_source_content(base_dir, cf, no_extract=no_extract, text_overrides=text_overrides))


def _write_chunk_markdown(chunk: Chunk, base_dir: str, out_filepath: str, with_index: bool, total_chunks: int, no_extract: bool = False, text_overrides: Dict[str, str] = None, heading_map: Dict = None):
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
            ctx_header = _format_file_header(cf, heading_map)
            if ctx_header:
                f.write(ctx_header)
            else:
                f.write(f"<!-- SOURCE: {cf.relative_path} -->\n\n")

            if text_overrides and cf.relative_path in text_overrides:
                f.write(text_overrides[cf.relative_path])
            else:
                # Fetch text content inside try catch
                true_filepath = os.path.join(base_dir, cf.relative_path)
                try:
                    with open(true_filepath, 'r', encoding='utf-8', errors='replace') as source_f:
                        content = source_f.read()
                        if cf.relative_path.lower().endswith('.html') or cf.relative_path.lower().endswith('.htm'):
                            if not no_extract:
                                content = extract_content(content)
                            content = strip_html(content)
                        f.write(content)
                except Exception as e:
                    logger.error(f"Failed to copy contents of {cf.relative_path}: {e}")
                    f.write(f"<!-- Excluded unreadable blob: {e} -->")

def _write_chunk_xml(chunk: Chunk, base_dir: str, out_filepath: str, with_index: bool, total_chunks: int, no_extract: bool = False, text_overrides: Dict[str, str] = None, heading_map: Dict = None):
    root = ET.Element("chunk", index=str(chunk.index), total=str(total_chunks))

    if with_index:
        meta = ET.SubElement(root, "meta")
        ET.SubElement(meta, "file_count").text = str(len(chunk.files))
        ET.SubElement(meta, "word_count").text = str(chunk.total_words)
        files_elem = ET.SubElement(meta, "files")
        for cf in chunk.files:
            ET.SubElement(files_elem, "file", path=cf.relative_path, words=str(cf.word_count))

    sources = ET.SubElement(root, "sources")
    # For CDATA handling, we'll build the base XML string and manually insert CDATA tags
    # First, let's create placeholders
    source_contents = {}
    for i, cf in enumerate(chunk.files):
        attrs = {"path": cf.relative_path}
        if heading_map is not None and cf.relative_path in heading_map:
            from ..utils.heading_extractor import get_active_headings
            headings = heading_map[cf.relative_path]
            if headings:
                last_offset = headings[-1].char_offset
                active = get_active_headings(headings, last_offset)
                if active:
                    attrs["context"] = " > ".join(h.text for h in active)
        source_elem = ET.SubElement(sources, "source", **attrs)
        placeholder = f"__CDATA_PLACEHOLDER_{i}__"
        source_elem.text = placeholder

        if text_overrides and cf.relative_path in text_overrides:
            content = text_overrides[cf.relative_path]
            content = content.replace("]]>", "]]]]><![CDATA[>")
            source_contents[placeholder] = f"\n<![CDATA[\n{content}\n]]>\n"
        else:
            true_filepath = os.path.join(base_dir, cf.relative_path)
            try:
                with open(true_filepath, 'r', encoding='utf-8', errors='replace') as source_f:
                    content = source_f.read()
                    if cf.relative_path.lower().endswith('.html') or cf.relative_path.lower().endswith('.htm'):
                        if not no_extract:
                            content = extract_content(content)
                        content = strip_html(content)
                    # Escape CDATA end marker ']]>' -> ']]]]><![CDATA[>'
                    content = content.replace("]]>", "]]]]><![CDATA[>")
                    source_contents[placeholder] = f"\n<![CDATA[\n{content}\n]]>\n"
            except Exception as e:
                logger.error(f"Failed to copy contents of {cf.relative_path}: {e}")
                source_contents[placeholder] = f"\n<!-- Excluded unreadable blob: {e} -->\n"

    # Generate XML string
    rough_string = ET.tostring(root, 'utf-8', xml_declaration=True).decode('utf-8')
    
    # Replace placeholders with manual CDATA blocks
    for placeholder, cdata_content in source_contents.items():
        rough_string = rough_string.replace(placeholder, cdata_content)
        
    with open(out_filepath, 'w', encoding='utf-8') as f:
        f.write(rough_string)


def write_chunks(chunks: List[Chunk], base_dir: str, output_dir: str, prefix: str, format: str, with_index: bool, total_chunks: int, no_extract: bool = False, text_overrides: Dict[str, str] = None, heading_map: Dict = None) -> List[str]:
    """Flush chunk classes out as disk files with or without headings."""
    os.makedirs(output_dir, exist_ok=True)
    generated_paths = []

    fmt = format.lower()
    for chunk in chunks:
        out_filename = f"{prefix}{chunk.index:02d}.{format}"
        out_filepath = os.path.join(output_dir, out_filename)
        generated_paths.append(out_filepath)

        if fmt == "xml":
            _write_chunk_xml(chunk, base_dir, out_filepath, with_index, total_chunks, no_extract=no_extract, text_overrides=text_overrides, heading_map=heading_map)
        elif fmt == "txt":
            _write_chunk_text(chunk, base_dir, out_filepath, with_index, total_chunks, no_extract=no_extract, text_overrides=text_overrides, heading_map=heading_map)
        else:
            _write_chunk_markdown(chunk, base_dir, out_filepath, with_index, total_chunks, no_extract=no_extract, text_overrides=text_overrides, heading_map=heading_map)

    return generated_paths
