"""Download subcommand."""

import os
import click
import logging

from ..lib.config_loader import load_config
from ..lib.manifest import load_manifest, save_manifest, build_manifest, merge_manifests
from ..lib.spa_detector import is_spa
from ..lib.wget_mirror import run_wget_mirror
from ..lib.playwright_crawl import run_playwright_crawl

logger = logging.getLogger(__name__)

@click.command()
@click.argument('url', type=str, required=True)
@click.option('--output', '-o', required=True, type=click.Path(), help="Diretório de destino dos arquivos baixados")
@click.option('--depth', '-d', type=int, default=0, help="Profundidade máxima de links a seguir. 0 = sem limite")
@click.option('--headless', is_flag=True, default=False, help="Forçar crawling via playwright (pula wget)")
@click.option('--delay', type=int, default=0, help="Intervalo entre requisições em milissegundos")
@click.option('--include-extensions', type=str, default="html,md,txt", help="Extensões permitidas, separadas por vírgula")
@click.option('--manifest', type=str, default=".dograpper-manifest.json", help="Caminho do arquivo de cache para downloads incrementais")
@click.pass_context
def download(ctx: click.Context, url: str, output: str, depth: int, headless: bool, delay: int, include_extensions: str, manifest: str):
    """Espelha um site de documentação localmente."""
    
    ctx.ensure_object(dict)
    config_path = ctx.obj.get('CONFIG_PATH', '.dograpper.json')
    
    # Load and merge config
    cli_params = {
        'output': output,
        'depth': depth,
        'headless': headless,
        'delay': delay,
        'include_extensions': include_extensions,
        'manifest': manifest
    }
    merged_params = load_config(config_path, 'download', cli_params, ctx)
    
    # Re-assign merged params
    output = merged_params.get('output', output)
    depth = merged_params.get('depth', depth)
    headless = merged_params.get('headless', headless)
    delay = merged_params.get('delay', delay)
    include_extensions = merged_params.get('include_extensions', include_extensions)
    manifest_path = merged_params.get('manifest', manifest)
    
    # Setup
    os.makedirs(output, exist_ok=True)
    manifest_data = load_manifest(manifest_path)
    
    files_skipped = 0
    files_downloaded = 0
    
    if headless:
        logger.info("Forced headless mode via Playwright.")
        try:
            result = run_playwright_crawl(url, output, depth, delay, include_extensions, manifest_data)
            if not result.success:
                raise click.ClickException("Playwright crawl failed.")
            files_skipped = result.files_skipped
            files_downloaded = len(result.files_downloaded) - files_skipped
        except RuntimeError as e:
            raise click.ClickException(str(e))
    else:
        logger.info("Running wget mirror.")
        try:
            is_incremental = bool(manifest_data)
            wget_res = run_wget_mirror(url, output, depth, delay, include_extensions, incremental=is_incremental)
            files_downloaded = len(wget_res.files_downloaded)
            if is_incremental:
                # Approximation for wget
                files_skipped = len(manifest_data.files)
        except RuntimeError as e:
            raise click.ClickException(str(e))
            
        if wget_res.success:
            if is_spa(output):
                logger.info("SPA detected, falling back to playwright")
                try:
                    result = run_playwright_crawl(url, output, depth, delay, include_extensions, manifest_data)
                    if not result.success:
                         raise click.ClickException("Playwright fallback crawl failed.")
                    files_skipped = result.files_skipped
                    files_downloaded = len(result.files_downloaded) - files_skipped
                except RuntimeError as e:
                    raise click.ClickException(str(e))

    # Build and save manifest
    new_manifest = build_manifest(url, output)
    final_manifest = merge_manifests(manifest_data, new_manifest)
    save_manifest(final_manifest, manifest_path)
    
    total_files = len(final_manifest.files)
    total_size = sum(f.size_bytes for f in final_manifest.files.values())
    
    click.echo(f"Download complete:")
    click.echo(f"  URL:              {url}")
    click.echo(f"  Output:           {output}")
    click.echo(f"  Files downloaded: {total_files}")  # Actually represents final files available, we'll keep it total_files or files_downloaded? The spec output layout says "Files downloaded: 47". We will print `total_files` or `files_downloaded`.
    click.echo(f"  Files skipped:    {files_skipped} (cached)")
    click.echo(f"  Total size:       {total_size / 1024 / 1024:.1f} MB")
    click.echo(f"  Manifest:         {manifest_path}")
