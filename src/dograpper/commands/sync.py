"""Sync subcommand — download + pack --delta in one step."""

import click
import logging

logger = logging.getLogger(__name__)


@click.command(
    epilog=(
        "\b\n"
        "Exemplos:\n"
        "  dograpper sync https://docs.example.com -o ./docs\n"
        "  dograpper sync https://docs.example.com -o ./docs --bundle notebooklm --context-header --score\n"
        "  dograpper sync https://spa.example.com -o ./docs --headless --format jsonl --cross-refs\n"
    )
)
@click.argument('url', type=str, required=True)
# --- Download pass-through ---
@click.option('--output', '-o', required=True, type=click.Path(),
              help="Diretório base (download salva aqui, pack lê daqui)")
@click.option('--depth', '-d', type=int, default=0, show_default=True,
              help="Profundidade máxima de links (0 = ilimitado)")
@click.option('--headless', is_flag=True, default=False,
              help="Pular wget e crawlear direto com Playwright (SPAs)")
@click.option('--delay', type=int, default=0, show_default=True,
              help="Intervalo entre requisições em ms")
@click.option('--include-extensions', type=str, default="html,md,txt", show_default=True,
              help="Extensões permitidas, separadas por vírgula")
# --- Pack pass-through ---
@click.option('--chunks-dir', type=str, default=None,
              help="Diretório de saída dos chunks (default: <output>/chunks)")
@click.option('--max-words-per-chunk', type=int, default=500000, show_default=True)
@click.option('--max-chunks', type=int, default=50, show_default=True)
@click.option('--strategy', type=click.Choice(['size', 'semantic']), default='size', show_default=True)
@click.option('--format', type=click.Choice(['txt', 'md', 'jsonl', 'xml']), default='md', show_default=True)
@click.option('--bundle', type=click.Choice(['notebooklm', 'rag-standard']), default=None)
@click.option('--context-header', is_flag=True, default=False,
              help="Injeta cabeçalho dograpper-context-v1 em cada arquivo do chunk")
@click.option('--cross-refs', is_flag=True, default=False,
              help="Gera cross_refs.json e anota chunks com [-> chunk_id]")
@click.option('--score', is_flag=True, default=False,
              help="Calcula LLM Readiness Score por chunk (llm-readiness.json)")
@click.option('--dedup', type=click.Choice(['off', 'exact', 'fuzzy', 'both'], case_sensitive=False),
              default='off', show_default=True)
@click.option('--show-tokens', is_flag=True, default=False,
              help="Exibe contagem de tokens por chunk e total")
@click.pass_context
def sync(ctx, url, output, depth, headless, delay, include_extensions,
         chunks_dir, max_words_per_chunk, max_chunks, strategy, format,
         bundle, context_header, cross_refs, score, dedup, show_tokens):
    """Download incremental + pack delta em um único comando.

    Equivalente a:
      dograpper download <url> -o <output> [flags de download]
      dograpper pack <output> -o <chunks-dir> --delta [flags de pack]

    Todas as flags de pack relevantes (bundle, context-header, score,
    cross-refs, dedup, etc.) são encaminhadas para a etapa de pack.
    """
    from .download import download
    from .pack import pack

    chunks_output = chunks_dir or f"{output}/chunks"

    click.echo("=== Step 1: Download ===")
    ctx.invoke(
        download,
        url=url,
        output=output,
        depth=depth,
        headless=headless,
        delay=delay,
        include_extensions=include_extensions,
    )

    click.echo("\n=== Step 2: Pack (delta) ===")
    ctx.invoke(
        pack,
        input_dir=output,
        output=chunks_output,
        max_words_per_chunk=max_words_per_chunk,
        max_chunks=max_chunks,
        strategy=strategy,
        format=format,
        bundle=bundle,
        context_header=context_header,
        cross_refs=cross_refs,
        score=score,
        dedup=dedup,
        show_tokens=show_tokens,
        delta=True,
    )
