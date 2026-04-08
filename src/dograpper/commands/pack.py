"""Pack subcommand."""

import os
import click
import logging

from ..lib.config_loader import load_config
from ..lib.ignore_parser import filter_files
from ..lib.chunker import chunk_by_size, chunk_by_semantic, write_chunks

logger = logging.getLogger(__name__)

@click.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True)
@click.option('--output', '-o', required=True, type=click.Path(), help="Diretório onde os chunks serão salvos")
@click.option('--max-words-per-chunk', type=int, default=500000, help="Limite de palavras por chunk")
@click.option('--max-chunks', type=int, default=50, help="Limite total de chunks")
@click.option('--strategy', type=click.Choice(['size', 'semantic']), default='size', help="Estratégia de chunking")
@click.option('--ignore-file', type=click.Path(), default='./.docsignore', help="Caminho para arquivo de exclusão")
@click.option('--ignore', multiple=True, type=str, default=[], help="Padrões de exclusão inline")
@click.option('--prefix', type=str, default="docs_chunk_", help="Prefixo dos arquivos gerados")
@click.option('--with-index/--no-index', default=True, help="Incluir sumário no cabeçalho")
@click.option('--format', type=click.Choice(['txt', 'md', 'xml']), default='md', help="Formato de saída")
@click.pass_context
def pack(ctx: click.Context, input_dir: str, output: str, max_words_per_chunk: int, max_chunks: int, strategy: str, ignore_file: str, ignore: tuple, prefix: str, with_index: bool, format: str):
    """Agrega arquivos baixados em chunks."""
    
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
        'format': format
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
        
    # 7. Execute chunking
    if strat == 'semantic':
        chunks = chunk_by_semantic(filtered_paths, input_dir, max_w)
    else:
        chunks = chunk_by_size(filtered_paths, input_dir, max_w)
        
    generated_chunk_count = len(chunks)
    
    # 8. Validate against max
    if generated_chunk_count > max_c:
        logger.warning(f"Generated {generated_chunk_count} chunks, exceeding max-chunks limit of {max_c}. Consider increasing --max-words-per-chunk or adding --ignore rules.")
        
    # 9. Write outputs
    write_chunks(chunks, input_dir, output_dir, pref, fmt, w_index, generated_chunk_count)
    
    # 10. Summary footprint calculation
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
    click.echo(f"  Output:          {output_dir}/")
    
    # Warnings at bottom
    oversized = [c for c in chunks if c.total_words > max_w]
    if oversized:
        plural = "s" if len(oversized) > 1 else ""
        click.echo(f"  \u26a0 {len(oversized)} chunk{plural} exceeds the word limit")
        
    if generated_chunk_count > max_c:
        click.echo(f"  \u26a0 Chunk count exceeds max-chunks limit ({generated_chunk_count} > {max_c})")
