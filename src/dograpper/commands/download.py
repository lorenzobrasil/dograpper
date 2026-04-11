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


def _snapshot_dir(path: str) -> dict:
    """Snapshot existing files under ``path`` mapping absolute path -> mtime.

    Used to compute which files were actually (re)written by an external tool
    such as wget, so the progress report can distinguish downloaded vs. skipped
    files in incremental runs.
    """
    snapshot: dict = {}
    if not os.path.exists(path):
        return snapshot
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                snapshot[fp] = os.path.getmtime(fp)
            except OSError:
                pass
    return snapshot


def _normalize_extensions(value) -> str:
    """Accept either a CSV string or a list from config; normalize to CSV."""
    if isinstance(value, (list, tuple)):
        return ",".join(str(x).strip().lstrip('.') for x in value if str(x).strip())
    return str(value)

@click.command(
    epilog=(
        "\b\n"
        "Exemplos:\n"
        "  dograpper download https://docs.rust-lang.org -o ./rust-docs\n"
        "  dograpper download https://react.dev --headless -o ./react-docs --delay 500\n"
        "  dograpper download https://docs.python.org/3/ -o ./py -d 3 --include-extensions html,md\n"
    )
)
@click.argument('url', type=str, required=True)
@click.option('--output', '-o', required=True, type=click.Path(),
              help="Diretório de destino dos arquivos baixados")
@click.option('--depth', '-d', type=int, default=0, show_default=True,
              help="Profundidade máxima de links a seguir (0 = ilimitado)")
@click.option('--headless', is_flag=True, default=False, show_default=True,
              help="Pular wget e crawlear direto com Playwright (use para SPAs)")
@click.option('--delay', type=int, default=0, show_default=True,
              help="Intervalo entre requisições em ms (rate limiting)")
@click.option('--include-extensions', type=str, default="html,md,txt", show_default=True,
              help="Extensões permitidas, separadas por vírgula")
@click.option('--manifest', type=str, default=".dograpper-manifest.json", show_default=True,
              help="Arquivo de cache JSON para downloads incrementais")
@click.pass_context
def download(ctx: click.Context, url: str, output: str, depth: int, headless: bool, delay: int, include_extensions: str, manifest: str):
    """Espelha um site de documentação localmente para processamento offline.

    Cria um mirror completo do site usando wget. Se detectar SPA
    (shells HTML vazios), faz fallback automático para Playwright.
    Use --headless para forçar Playwright diretamente.

    Downloads são incrementais via manifest JSON.
    """
    
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
    include_extensions = _normalize_extensions(
        merged_params.get('include_extensions', include_extensions)
    )
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
            files_downloaded = max(0, len(result.files_downloaded) - files_skipped)
        except RuntimeError as e:
            raise click.ClickException(str(e))
    else:
        logger.info("Running wget mirror.")
        is_incremental = bool(manifest_data)
        pre_snapshot = _snapshot_dir(output) if is_incremental else {}
        try:
            wget_res = run_wget_mirror(url, output, depth, delay, include_extensions, incremental=is_incremental)
        except RuntimeError as e:
            raise click.ClickException(str(e))

        if is_incremental:
            # Diff against the pre-snapshot: files that are new or whose mtime
            # advanced were touched by wget; files unchanged were skipped.
            touched = 0
            unchanged = 0
            for p in wget_res.files_downloaded:
                prev_mtime = pre_snapshot.get(p)
                try:
                    curr_mtime = os.path.getmtime(p)
                except OSError:
                    continue
                if prev_mtime is None or curr_mtime > prev_mtime:
                    touched += 1
                else:
                    unchanged += 1
            files_downloaded = touched
            files_skipped = unchanged
        else:
            files_downloaded = len(wget_res.files_downloaded)
            files_skipped = 0

        if wget_res.success and is_spa(output):
            logger.info("SPA detected, falling back to playwright")
            try:
                result = run_playwright_crawl(url, output, depth, delay, include_extensions, manifest_data)
                if not result.success:
                    raise click.ClickException("Playwright fallback crawl failed.")
                files_skipped = result.files_skipped
                files_downloaded = max(0, len(result.files_downloaded) - files_skipped)
            except RuntimeError as e:
                raise click.ClickException(str(e))

    # Build and save manifest
    new_manifest = build_manifest(url, output)
    final_manifest = merge_manifests(manifest_data, new_manifest)
    save_manifest(final_manifest, manifest_path)

    total_size = sum(f.size_bytes for f in final_manifest.files.values())

    click.echo("Download complete:")
    click.echo(f"  URL:              {url}")
    click.echo(f"  Output:           {output}")
    click.echo(f"  Files downloaded: {files_downloaded}")
    click.echo(f"  Files skipped:    {files_skipped} (cached)")
    click.echo(f"  Total size:       {total_size / 1024 / 1024:.1f} MB")
    click.echo(f"  Manifest:         {manifest_path}")
