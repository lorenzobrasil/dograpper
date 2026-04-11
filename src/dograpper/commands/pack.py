"""Pack subcommand."""

import os
import json
import click
import logging
from datetime import datetime, timezone

from ..lib.config_loader import load_config
from ..lib.ignore_parser import filter_files
from ..lib.chunker import chunk_by_size, chunk_by_semantic, write_chunks

logger = logging.getLogger(__name__)

@click.command(
    epilog=(
        "\b\n"
        "Exemplos:\n"
        "  dograpper pack ./rust-docs -o ./chunks\n"
        "  dograpper pack ./rust-docs -o ./chunks --strategy semantic --max-words-per-chunk 300000\n"
        "  dograpper pack ./docs -o ./chunks --ignore '*.png' --ignore '**/404.html'\n"
        "  dograpper pack ./docs -o ./chunks --format xml --no-index\n"
    )
)
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True)
@click.option('--output', '-o', required=True, type=click.Path(),
              help="Diretório onde os chunks serão salvos")
@click.option('--max-words-per-chunk', type=int, default=500000, show_default=True,
              help="Limite de palavras por chunk (teto por fonte do NotebookLM)")
@click.option('--max-chunks', type=int, default=50, show_default=True,
              help="Limite total de chunks (teto de fontes por notebook)")
@click.option('--strategy', type=click.Choice(['size', 'semantic']), default='size', show_default=True,
              help="size: empacota por contagem de palavras. semantic: agrupa por diretório primeiro")
@click.option('--ignore-file', type=click.Path(), default='./.docsignore', show_default=True,
              help="Arquivo de exclusão com sintaxe gitignore")
@click.option('--ignore', multiple=True, type=str, default=[],
              help="Padrão de exclusão inline (pode repetir): --ignore '*.png' --ignore '**/404.html'")
@click.option('--prefix', type=str, default="docs_chunk_", show_default=True,
              help="Prefixo dos arquivos gerados")
@click.option('--with-index/--no-index', default=True, show_default=True,
              help="Incluir sumário de arquivos no cabeçalho de cada chunk")
@click.option('--format', type=click.Choice(['txt', 'md', 'xml']), default='md', show_default=True,
              help="Formato de saída dos chunks")
@click.option('--no-extract', is_flag=True, default=False,
              help="Desativa a extração inteligente de conteúdo. Usa o HTML inteiro como no comportamento anterior.")
@click.option('--show-tokens', is_flag=True, default=False,
              help="Exibe contagem de tokens por chunk e total no summary final.")
@click.option('--token-encoding', type=str, default="cl100k", show_default=True,
              help="Encoding do tokenizer (cl100k, o200k, p50k). Requer --show-tokens.")
@click.option('--dry-run', is_flag=True, default=False,
              help="Simula o pack sem escrever arquivos. Exibe relatório de compressão e projeção de chunks.")
@click.option('--dedup', type=click.Choice(['off', 'exact', 'fuzzy', 'both'], case_sensitive=False),
              default='off', show_default=True,
              help="Deduplicação de blocos entre arquivos. "
                   "'exact' remove blocos idênticos, 'fuzzy' remove quase idênticos, "
                   "'both' aplica ambos.")
@click.option('--dedup-threshold', type=int, default=3, show_default=True,
              help="Distância de Hamming máxima para dedup fuzzy (0-10). Menor = mais conservador.")
@click.option('--context-header', is_flag=True, default=False,
              help="Injeta cabeçalho de contexto (source, breadcrumb de headings) "
                   "no topo de cada arquivo dentro do chunk para melhorar a ingestão por LLMs.")
@click.option('--cross-refs', is_flag=True, default=False,
              help="Gera cross_refs.json com referências cruzadas entre chunks "
                   "e anota o texto dos chunks com ponteiros [-> chunk_id].")
@click.option('--delta', is_flag=True, default=False,
              help="Reprocessa apenas arquivos alterados desde o último pack.")
@click.option('--manifest', type=str, default=".dograpper-manifest.json",
              show_default=True,
              help="Manifest do download para comparação delta.")
@click.option('--bundle', type=click.Choice(['notebooklm', 'rag-standard']),
              default=None,
              help="Preset de empacotamento otimizado. "
                   "'notebooklm': ≤50 chunks balanceados. "
                   "'rag-standard': sem restrições especiais.")
@click.pass_context
def pack(ctx: click.Context, input_dir: str, output: str, max_words_per_chunk: int, max_chunks: int, strategy: str, ignore_file: str, ignore: tuple, prefix: str, with_index: bool, format: str, no_extract: bool, show_tokens: bool, token_encoding: str, dry_run: bool, dedup: str, dedup_threshold: int, context_header: bool, cross_refs: bool, delta: bool, manifest: str, bundle: str):
    """Agrega arquivos baixados em chunks com contagem de palavras controlada.

    Percorre `INPUT_DIR`, aplica regras de exclusão (`.docsignore` +
    `--ignore`), e gera arquivos sequenciais `docs_chunk_NN.<fmt>` no
    diretório de saída. Cada chunk tem um cabeçalho opcional listando os
    arquivos que contém (controlado por `--with-index/--no-index`).

    \b
    Estratégias de agrupamento:
      size      Empacota por contagem de palavras pura, em ordem alfabética.
      semantic  Agrupa arquivos do mesmo diretório antes de aplicar o
                limite de palavras, preservando coesão temática. Grupos
                que excedem o limite são subdivididos automaticamente.

    Se um único arquivo exceder `--max-words-per-chunk`, ele é colocado
    sozinho em um chunk e um warning é emitido (o CLI não falha).
    """
    
    ctx.ensure_object(dict)
    config_path = ctx.obj.get('CONFIG_PATH', '.dograpper.json')
    
    cli_params = {
        'output': output,
        'max_words_per_chunk': max_words_per_chunk,
        'max_chunks': max_chunks,
        'strategy': strategy,
        'ignore_file': ignore_file,
        'ignore': ignore,
        'prefix': prefix,
        'with_index': with_index,
        'format': format,
        'no_extract': no_extract,
        'show_tokens': show_tokens,
        'token_encoding': token_encoding,
        'dry_run': dry_run,
        'dedup': dedup,
        'dedup_threshold': dedup_threshold,
        'context_header': context_header,
        'cross_refs': cross_refs,
        'delta': delta,
        'manifest': manifest,
        'bundle': bundle,
    }
    
    merged_params = load_config(config_path, 'pack', cli_params, ctx)
    
    output_dir = merged_params.get('output', output)
    max_w = merged_params.get('max_words_per_chunk', max_words_per_chunk)
    max_c = merged_params.get('max_chunks', max_chunks)
    strat = merged_params.get('strategy', strategy)
    ign_file = merged_params.get('ignore_file', ignore_file)
    ign_inline = list(merged_params.get('ignore', ignore))
    pref = merged_params.get('prefix', prefix)
    w_index = merged_params.get('with_index', with_index)
    fmt = merged_params.get('format', format)
    no_ext = merged_params.get('no_extract', no_extract)
    s_tokens = merged_params.get('show_tokens', show_tokens)
    t_encoding = merged_params.get('token_encoding', token_encoding)
    is_dry_run = merged_params.get('dry_run', dry_run)
    dedup_mode = merged_params.get('dedup', dedup)
    dedup_thresh = merged_params.get('dedup_threshold', dedup_threshold)
    ctx_header = merged_params.get('context_header', context_header)
    do_cross_refs = merged_params.get('cross_refs', cross_refs)
    is_delta = merged_params.get('delta', delta)
    manifest_path = merged_params.get('manifest', manifest)
    bundle_preset = merged_params.get('bundle', bundle)

    # 2b. Bundle overrides
    if bundle_preset == 'notebooklm':
        max_c = min(max_c, 50)
        if max_w > 500000:
            max_w = 500000
        logger.info(f"[bundle:notebooklm] max_chunks={max_c}, max_words={max_w}")

    # 3. List all files
    all_files = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            all_files.append(os.path.join(root, f))
            
    # 4. Check empty
    if not all_files:
        raise click.ClickException(f"No files found in {input_dir}. Did you run `download` first?")
        
    # 5. Filter
    filtered_paths = filter_files(all_files, ign_file, ign_inline, input_dir)
    
    # 6. Check empty after filter
    if not filtered_paths:
        raise click.ClickException("All files were excluded by ignore rules. Check your .docsignore or --ignore flags.")

    # 6b. Delta filtering (opt-in, after filter, before dedup)
    diff = None
    if is_delta:
        from ..lib.manifest import load_manifest, build_manifest, diff_manifests

        old_manifest = load_manifest(manifest_path)
        current_manifest = build_manifest(base_url="", output_dir=input_dir)
        diff = diff_manifests(old_manifest, current_manifest)

        delta_files = set(diff.added + diff.modified)
        pre_count = len(filtered_paths)

        filtered_paths = [
            f for f in filtered_paths
            if os.path.relpath(f, input_dir).replace(os.sep, '/') in delta_files
        ]

        logger.info(f"[delta] {pre_count} files → {len(filtered_paths)} changed "
                     f"({len(diff.added)} added, {len(diff.modified)} modified, "
                     f"{len(diff.removed)} removed)")

        if not filtered_paths:
            click.echo("Delta: no files changed since last pack. Nothing to do.")
            return

    # 7. Deduplication (opt-in, before chunking)
    dedup_stats = None
    dedup_word_counts = None
    dedup_text_overrides = None

    if dedup_mode != "off":
        from ..utils.html_stripper import strip_html as _strip_html
        from ..utils.content_extractor import extract_content as _extract_content
        from ..utils.dedup import deduplicate

        processed_texts = {}
        for fpath in filtered_paths:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    raw = fh.read()
            except Exception:
                continue
            rel = os.path.relpath(fpath, input_dir).replace(os.sep, '/')
            if fpath.lower().endswith(('.html', '.htm')):
                if not no_ext:
                    raw = _extract_content(raw)
                text = _strip_html(raw)
            else:
                text = raw
            processed_texts[rel] = text

        dedup_result = deduplicate(processed_texts, mode=dedup_mode, hamming_threshold=dedup_thresh)
        dedup_stats = dedup_result.stats
        dedup_word_counts = {rp: len(t.split()) for rp, t in dedup_result.texts.items()}
        dedup_text_overrides = dedup_result.texts

    # 7b. Extract headings for context-header (opt-in, before chunking)
    heading_map = None
    if ctx_header:
        from ..utils.heading_extractor import extract_with_headings
        from ..utils.content_extractor import extract_content as _extract_ctx

        heading_map = {}
        # Initialize text_overrides if not already set by dedup, so the writer
        # uses the same text from which heading offsets were calculated.
        if dedup_text_overrides is None:
            dedup_text_overrides = {}

        for fpath in filtered_paths:
            rel = os.path.relpath(fpath, input_dir).replace(os.sep, '/')
            if fpath.lower().endswith(('.html', '.htm')):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        raw = fh.read()
                    if not no_ext:
                        raw = _extract_ctx(raw)
                    doc = extract_with_headings(raw, source_path=rel)
                    heading_map[rel] = doc.headings
                    # Use doc.text for consistent offsets (only if dedup didn't override)
                    if rel not in dedup_text_overrides:
                        dedup_text_overrides[rel] = doc.text
                    logger.debug(f"[context] {rel}: {len(doc.headings)} headings extracted")
                except Exception:
                    heading_map[rel] = []
            else:
                heading_map[rel] = []

    # 8. Execute chunking
    if strat == 'semantic':
        chunks = chunk_by_semantic(filtered_paths, input_dir, max_w, no_extract=no_ext, word_counts=dedup_word_counts)
    else:
        chunks = chunk_by_size(filtered_paths, input_dir, max_w, no_extract=no_ext, word_counts=dedup_word_counts)

    # 8b. Bundle balancing (post-process)
    if bundle_preset == 'notebooklm':
        from ..lib.chunker import balance_chunks
        chunks = balance_chunks(chunks, target_chunks=max_c, max_words=max_w)

    generated_chunk_count = len(chunks)

    # 9. Validate against max
    if generated_chunk_count > max_c:
        logger.warning(f"Generated {generated_chunk_count} chunks, exceeding max-chunks limit of {max_c}. Consider increasing --max-words-per-chunk or adding --ignore rules.")

    # 9b. Dry-run: generate report and exit without writing
    if is_dry_run:
        from ..utils.html_stripper import strip_html
        from ..utils.content_extractor import extract_content
        from ..utils.dry_run_report import DryRunData, FileStats, generate_report

        file_stats = []
        for fpath in filtered_paths:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    raw = fh.read()
            except Exception:
                continue

            rel = os.path.relpath(fpath, input_dir).replace(os.sep, '/')
            is_html_file = fpath.lower().endswith(('.html', '.htm'))

            if is_html_file:
                text_before = strip_html(raw)
                if not no_ext:
                    text_after = strip_html(extract_content(raw))
                else:
                    text_after = text_before
            else:
                text_before = raw
                text_after = raw

            words_before = len(text_before.split())
            words_after = len(text_after.split())

            # Use post-dedup word count if available
            words_after_dedup = None
            if dedup_word_counts and rel in dedup_word_counts:
                words_after_dedup = dedup_word_counts[rel]

            tokens = None
            if s_tokens:
                from ..utils.token_counter import count_tokens
                token_text = dedup_text_overrides[rel] if dedup_text_overrides and rel in dedup_text_overrides else text_after
                tokens = count_tokens(token_text, encoding=t_encoding).tokens

            file_stats.append(FileStats(
                filepath=rel,
                words_before_extraction=words_before,
                words_after_extraction=words_after,
                tokens=tokens,
                words_after_dedup=words_after_dedup,
            ))

        # Use post-dedup word counts for oversize check when available
        def _effective_words(fs):
            return fs.words_after_dedup if fs.words_after_dedup is not None else fs.words_after_extraction

        oversize = sum(1 for fs in file_stats if _effective_words(fs) > max_w)

        report_data = DryRunData(
            total_files_found=len(all_files),
            total_files_excluded=len(all_files) - len(filtered_paths),
            file_stats=file_stats,
            projected_chunks=generated_chunk_count,
            max_chunks=max_c,
            max_words_per_chunk=max_w,
            strategy=strat,
            show_tokens=s_tokens,
            token_encoding=t_encoding,
            oversize_files=oversize,
            dedup_stats=dedup_stats,
        )

        click.echo(generate_report(report_data))
        return

    # 10. Write outputs
    write_chunks(chunks, input_dir, output_dir, pref, fmt, w_index, generated_chunk_count, no_extract=no_ext, text_overrides=dedup_text_overrides, heading_map=heading_map, max_words=max_w)

    # 10a. Cross-references (opt-in, after write)
    cross_ref_total = 0
    cross_ref_unresolved = 0
    if do_cross_refs:
        import json as _json
        from ..utils.link_extractor import extract_links, build_cross_ref_index, annotate_cross_refs

        # Build file_to_chunk map (with normalized variants for index.html)
        file_to_chunk = {}
        for chunk in chunks:
            chunk_id = f"{pref}{chunk.index:02d}"
            for cf in chunk.files:
                file_to_chunk[cf.relative_path] = chunk_id
                # Also register normalized path (without /index.html suffix)
                # so that links resolved by extract_links can match
                rp = cf.relative_path
                if rp.endswith("/index.html"):
                    file_to_chunk[rp[:-len("/index.html")]] = chunk_id
                elif rp == "index.html":
                    file_to_chunk[""] = chunk_id

        # Extract links from all HTML files
        all_links = []
        for fpath in filtered_paths:
            if not fpath.lower().endswith(('.html', '.htm')):
                continue
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    raw_html = fh.read()
            except Exception:
                continue
            rel = os.path.relpath(fpath, input_dir).replace(os.sep, '/')
            file_links = extract_links(raw_html, rel)
            all_links.extend(file_links)

        # Build index and write JSON
        cross_index = build_cross_ref_index(all_links, file_to_chunk)
        cross_ref_total = sum(
            len(entry.get("links", []))
            for key, entry in cross_index.items()
            if key != "unresolved"
        )
        cross_ref_unresolved = len(cross_index.get("unresolved", []))

        cross_refs_path = os.path.join(output_dir, "cross_refs.json")
        with open(cross_refs_path, 'w', encoding='utf-8') as jf:
            _json.dump(cross_index, jf, indent=2, ensure_ascii=False)

        # Annotate written chunk files
        for chunk in chunks:
            chunk_id = f"{pref}{chunk.index:02d}"
            chunk_filename = f"{chunk_id}.{fmt}"
            chunk_filepath = os.path.join(output_dir, chunk_filename)
            # Collect links whose source files are in this chunk
            chunk_links = [
                lnk for lnk in all_links
                if file_to_chunk.get(lnk.source_path) == chunk_id
            ]
            if not chunk_links:
                continue
            try:
                with open(chunk_filepath, 'r', encoding='utf-8', errors='replace') as cf:
                    chunk_text = cf.read()
                annotated = annotate_cross_refs(chunk_text, chunk_links, file_to_chunk)
                if annotated != chunk_text:
                    with open(chunk_filepath, 'w', encoding='utf-8') as cf:
                        cf.write(annotated)
            except Exception as e:
                logger.warning(f"Failed to annotate cross-refs for {chunk_filename}: {e}")

    # 10b. Delta manifest (opt-in, after write)
    if is_delta and diff is not None:
        delta_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "added": diff.added,
            "modified": diff.modified,
            "removed": diff.removed,
            "chunks_generated": [
                {
                    "chunk": f"{pref}{c.index:02d}",
                    "files": [cf.relative_path for cf in c.files]
                }
                for c in chunks
            ],
        }
        delta_path = os.path.join(output_dir, "delta_manifest.json")
        with open(delta_path, 'w', encoding='utf-8') as df:
            json.dump(delta_info, df, indent=2)

    # 10c. Import guide (opt-in, for bundle presets)
    guide_path = None
    if bundle_preset is not None:
        from ..lib.chunker import generate_import_guide
        total_words_for_guide = sum(c.total_words for c in chunks)
        guide_path = generate_import_guide(
            chunks, output_dir, bundle_preset, total_words_for_guide,
            heading_map=heading_map
        )

    # 10d. Token counting (opt-in)
    token_counts = []
    if s_tokens:
        from ..utils.token_counter import count_tokens, format_token_summary

        for chunk in chunks:
            # Read the written chunk file to count tokens on the final output
            chunk_filename = f"{pref}{chunk.index:02d}.{fmt}"
            chunk_filepath = os.path.join(output_dir, chunk_filename)
            try:
                with open(chunk_filepath, 'r', encoding='utf-8', errors='replace') as cf:
                    chunk_text = cf.read()
                tc = count_tokens(chunk_text, encoding=t_encoding)
                token_counts.append(tc)
                logger.debug(f"[tokens] {chunk_filename}: {tc.words} words → {tc.tokens} tokens ({tc.encoding})")
            except Exception as e:
                logger.warning(f"Failed to count tokens for {chunk_filename}: {e}")

    # 11. Summary footprint calculation
    files_processed = sum(len(c.files) for c in chunks)
    files_excluded = len(all_files) - len(filtered_paths)
    total_words = sum(c.total_words for c in chunks)
    
    if generated_chunk_count > 0:
        avg_w = total_words / generated_chunk_count
        min_w = min(c.total_words for c in chunks)
        max_w_actual = max(c.total_words for c in chunks)
    else:
        avg_w = min_w = max_w_actual = 0
        
    # Formatting the summary outputs
    click.echo("\nPack complete:")
    click.echo(f"  Files processed: {files_processed}")
    click.echo(f"  Files excluded:  {files_excluded}")
    click.echo(f"  Chunks generated: {generated_chunk_count} / {max_c} (max)")
    
    if generated_chunk_count > 0:
         click.echo(f"  Words per chunk:  ~{avg_w:,.0f} avg (min: {min_w:,}, max: {max_w_actual:,})".replace(',', '.'))
    else:
         click.echo("  Words per chunk:  0")
         
    click.echo(f"  Total words:     {total_words:,}".replace(',', '.'))

    if dedup_stats is not None:
        click.echo(f"  Dedup mode:        {dedup_mode}")
        click.echo(f"  Blocks analisados: {dedup_stats.total_blocks}")
        click.echo(f"  Blocks removidos:  {dedup_stats.blocks_removed} ({dedup_stats.blocks_removed_exact} exact + {dedup_stats.blocks_removed_fuzzy} fuzzy)")
        if total_words + dedup_stats.words_removed > 0:
            pct = dedup_stats.words_removed * 100 // (total_words + dedup_stats.words_removed)
        else:
            pct = 0
        click.echo(f"  Palavras removidas: {dedup_stats.words_removed:,} (~{pct}%)".replace(',', '.'))

    if is_delta and diff is not None:
        click.echo(f"  Delta:           {len(diff.added)} added, {len(diff.modified)} modified, {len(diff.removed)} removed")
        click.echo(f"  Delta manifest:  {os.path.join(output_dir, 'delta_manifest.json')}")

    if guide_path is not None:
        click.echo(f"  Import guide:    {guide_path}")

    click.echo(f"  Output:          {output_dir}/")

    if do_cross_refs:
        click.echo(f"  Cross-refs:        {output_dir}/cross_refs.json ({cross_ref_total} links, {cross_ref_unresolved} unresolved)")

    if token_counts:
        from ..utils.token_counter import format_token_summary
        click.echo(format_token_summary(token_counts))
    
    # Warnings at bottom
    oversized = [c for c in chunks if c.total_words > max_w]
    if oversized:
        plural = "s" if len(oversized) > 1 else ""
        click.echo(f"  \u26a0 {len(oversized)} chunk{plural} exceeds the word limit")
        
    if generated_chunk_count > max_c:
        click.echo(f"  \u26a0 Chunk count exceeds max-chunks limit ({generated_chunk_count} > {max_c})")
