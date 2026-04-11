"""Entry point for the dograpper CLI."""

import click
import sys
from .utils.logger import setup_logger
from .commands.download import download
from .commands.pack import pack
from .commands.sync import sync

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--verbose', '-v', is_flag=True, default=False,
              help="Log detalhado (DEBUG) de cada operação")
@click.option('--quiet', '-q', is_flag=True, default=False,
              help="Suprimir output exceto erros críticos")
@click.option('--config', default=".dograpper.json", show_default=True,
              type=click.Path(),
              help="Arquivo JSON de configuração (seções `download` e `pack`)")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, config: str):
    """dograpper — doc + wrapper.

    Baixa documentações técnicas inteiras e empacota em chunks prontos para
    importar no Google NotebookLM, respeitando seus limites de palavras por
    fonte e de fontes por notebook.

    \b
    Pipeline típico:
      dograpper download <url> -o ./docs
      dograpper pack ./docs -o ./chunks

    Cada subcomando tem ajuda própria: `dograpper <comando> --help`.
    As flags globais `--verbose` e `--quiet` são mutuamente exclusivas.
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

def main():
    cli(obj={})

if __name__ == '__main__':
    main()
