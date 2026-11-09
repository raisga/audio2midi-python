import click


def custom_help_option(f):
    """Adds a -h/--help option to the command."""
    def callback(ctx, param, value):
        if value and not ctx.resilient_parsing:
            click.echo(ctx.get_help())
            ctx.exit()
    return click.option('-h', '--help',
                        is_flag=True,
                        expose_value=False,
                        is_eager=True,
                        callback=callback,
                        help='Show this help message and exit')(f)
