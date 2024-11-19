import click

@click.command()
def hello():
    """Echo 'Hello world!'"""
    click.echo("Hello world!")
