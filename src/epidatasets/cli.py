"""Command-line interface for epidatasets."""

from __future__ import annotations

import sys

import typer

app = typer.Typer(
    name="epidatasets",
    help="Access epidemiological datasets from the command line.",
    add_completion=False,
)


@app.command()
def sources() -> None:
    """List all available data sources."""
    from epidatasets import list_sources

    source_list = list_sources()
    if not source_list:
        typer.echo("No data sources registered.")
        raise typer.Exit()

    typer.echo(f"{'Name':<20} {'Description':<50} {'URL'}")
    typer.echo("-" * 100)
    for name, meta in sorted(source_list.items()):
        desc = meta.get("description", "")[:48]
        url = meta.get("url", "")
        typer.echo(f"{name:<20} {desc:<50} {url}")


@app.command()
def info(
    source: str = typer.Argument(..., help="Source name to inspect."),
) -> None:
    """Show detailed information about a data source."""
    from epidatasets import get_source

    try:
        accessor = get_source(source)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    meta = accessor.info()
    typer.echo(f"Name:        {meta['name']}")
    typer.echo(f"Description: {meta['description']}")
    typer.echo(f"URL:         {meta['url']}")
    typer.echo(f"Class:       {meta['class']}")


@app.command()
def countries(
    source: str = typer.Argument(..., help="Source name to query."),
) -> None:
    """List countries covered by a data source."""
    from epidatasets import get_source

    try:
        accessor = get_source(source)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    df = accessor.list_countries()
    typer.echo(df.to_string(index=False))


def main() -> None:
    """Entry-point for the CLI."""
    app()


if __name__ == "__main__":
    main()
