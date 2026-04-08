"""Entry point for the dograpper CLI."""

import click
import sys
from .utils.logger import setup_logger
from .commands.download import download
from .commands.pack import pack

@click.group()
@click.option('--verbose', '-v', is_flag=True, default=False, help="Log detalhado de cada operação")
@click.option('--quiet', '-q', is_flag=True, default=False, help="Suprimir output exceto erros críticos")
@click.option('--config', default=".dograpper.json", help="Arquivo de configuração", type=click.Path())
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, config: str):
    """CLI do dograpper - doc + wrapper."""
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

def main():
    cli(obj={})

if __name__ == '__main__':
    main()
