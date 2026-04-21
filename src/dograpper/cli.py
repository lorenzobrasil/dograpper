"""Entry point for the dograpper CLI."""

import click
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from .utils.logger import setup_logger
from .commands.download import download
from .commands.pack import pack
from .commands.sync import sync
from .commands.doctor import doctor

try:
    __version__ = _pkg_version("dograpper")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version=__version__, prog_name="dograpper")
@click.option('--verbose', '-v', is_flag=True, default=False,
              help="Log detalhado (DEBUG) de cada operação")
@click.option('--quiet', '-q', is_flag=True, default=False,
              help="Suprimir output exceto erros críticos")
@click.option('--config', default=".dograpper.json", show_default=True,
              type=click.Path(),
              help="Arquivo JSON de configuração (seções `download` e `pack`)")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, config: str):
    """dograpper — Context Engineering Pipeline for Deterministic LLM Ingestion.

    Transforma documentação HTML em contexto estruturado, dedupicado,
    pontuado e versionado para ingestão em LLMs estáticos.

    \b
    Pipeline típico:
      dograpper download <url> -o ./docs
      dograpper pack ./docs -o ./chunks --context-header --score

    Pipeline rápido:
      dograpper sync <url> -o ./docs

    Cada subcomando tem ajuda própria: `dograpper <comando> --help`.
    """
    if verbose and quiet:
        click.echo("Error: --verbose and --quiet are mutually exclusive.", err=True)
        sys.exit(1)
        
    setup_logger(verbose=verbose, quiet=quiet)
    
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose
    ctx.obj['QUIET'] = quiet
    ctx.obj['CONFIG_PATH'] = config

cli.add_command(download)
cli.add_command(pack)
cli.add_command(sync)
cli.add_command(doctor)

def main():
    cli(obj={})

if __name__ == '__main__':
    main()
