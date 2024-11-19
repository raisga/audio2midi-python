import click
from lib.args.hello import hello
from lib.flags.help import custom_help_option

@click.group(invoke_without_command=True)
@custom_help_option
@click.pass_context
def cli(ctx):
    """A simple CLI app."""
    if ctx.invoked_subcommand is None:
        # If no subcommand is provided, print the help message
        click.echo(ctx.get_help())
        ctx.exit()

# Add commands to the cli group
cli.add_command(hello)

if __name__ == '__main__':
    cli()
