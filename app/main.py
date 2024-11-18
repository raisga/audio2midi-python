import click

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()

@cli.command()
def hello():
    """Prints Hello world!"""
    click.echo("Hello world!")

if __name__ == '__main__':
    cli()
