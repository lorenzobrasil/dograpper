"""Sync subcommand — download + pack --delta in one step."""

import click
import logging

logger = logging.getLogger(__name__)


@click.command()
@click.argument('url', type=str, required=True)
@click.option('--output', '-o', required=True, type=click.Path(),
              help="Diretório base (download salva aqui, pack lê daqui)")
@click.option('--chunks-dir', type=str, default=None,
              help="Diretório de saída dos chunks (default: <output>/chunks)")
@click.option('--max-words-per-chunk', type=int, default=500000, show_default=True)
@click.option('--format', type=click.Choice(['txt', 'md', 'xml']), default='md', show_default=True)
@click.pass_context
def sync(ctx, url, output, chunks_dir, max_words_per_chunk, format):
    """Download incremental + pack delta em um único comando.

    Equivalente a:
      dograpper download <url> -o <output>
      dograpper pack <output> -o <chunks-dir> --delta
    """
    from .download import download
    from .pack import pack

    chunks_output = chunks_dir or f"{output}/chunks"

    # Step 1: download (incremental por padrão via manifest)
    click.echo("=== Step 1: Download ===")
    ctx.invoke(download, url=url, output=output)

    # Step 2: pack --delta
    click.echo("\n=== Step 2: Pack (delta) ===")
    ctx.invoke(pack, input_dir=output, output=chunks_output,
               max_words_per_chunk=max_words_per_chunk, format=format,
               delta=True)
