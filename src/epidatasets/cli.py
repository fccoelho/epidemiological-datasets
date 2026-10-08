"""Command-line interface for epidatasets."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="epidatasets",
    help="Access epidemiological datasets from the command line.",
    add_completion=False,
)
news_app = typer.Typer(
    name="news",
    help="Fetch and visualize public-health news feeds.",
    add_completion=False,
)
app.add_typer(news_app)


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


# ----------------------------------------------------------------------
# News-feed aggregator subcommands
# ----------------------------------------------------------------------


@news_app.command("fetch")
def news_fetch(
    sources: list[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Feed name(s) to fetch (default: all). See `epidatasets news feeds`.",
    ),
    days: int = typer.Option(30, help="Only keep items from the last N days."),
    limit: int = typer.Option(50, help="Maximum items parsed per feed."),
    query: list[str] = typer.Option(
        None,
        "--query",
        "-q",
        help='Add a Google News topic query feed (e.g. "dengue when:30d"). Repeatable.',
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Save items to CSV/parquet (path suffix decides)."
    ),
) -> None:
    """Fetch, normalize, deduplicate and disease-tag public-health news."""
    from epidatasets.newsfeeds import NewsAggregator

    agg = NewsAggregator()
    items = agg.fetch(
        sources=list(sources) if sources else None,
        days=days,
        limit_per_feed=limit,
        queries=list(query) if query else None,
    )
    typer.echo(f"Fetched {len(items)} items.")
    for name, status in sorted(agg.last_fetch_status.items()):
        flag = "cached" if status["cached"] else "fetched"
        err = f" ERROR: {status['error']}" if status["error"] else ""
        typer.echo(f"  {name:<28} {status['items']:>4} items ({flag}){err}")
    if out is not None:
        items.to_csv(out, index=False)
        typer.echo(f"Saved to {out}")


@news_app.command("feeds")
def news_feeds() -> None:
    """List the available news feeds."""
    from epidatasets.newsfeeds import FEED_SOURCES

    typer.echo(f"{'Name':<24} {'Kind':<12} {'Title'}")
    typer.echo("-" * 90)
    for name, src in FEED_SOURCES.items():
        typer.echo(f"{name:<24} {src.kind:<12} {src.title}")
    typer.echo(
        "\nGoogle News topic feeds are added dynamically via "
        "`epidatasets news fetch --query <query>`."
    )


@news_app.command("plot")
def news_plot(
    items_csv: Path = typer.Argument(..., help="CSV of items (from `news fetch --out`)."),
    timeline: bool = typer.Option(True, "--timeline/--no-timeline"),
    by: str = typer.Option(
        "disease_tags", help="Column to split the timeline by."
    ),
    out: Path = typer.Option("timeline.png", "--out", "-o"),
) -> None:
    """Plot a timeline of news-item counts."""
    import pandas as pd

    from epidatasets.newsfeeds import plot_timeline

    items = pd.read_csv(items_csv)
    fig = plot_timeline(items, by=by, out=str(out))
    typer.echo(f"Timeline saved to {out}")
    import matplotlib.pyplot as plt

    plt.close(fig)  # type: ignore[arg-type]


@news_app.command("map")
def news_map(
    items_csv: Path = typer.Argument(..., help="CSV of items (from `news fetch --out`)."),
    out: Path = typer.Option("news_map.html", "--out", "-o"),
) -> None:
    """Geo-tag items and render an interactive map (HTML)."""
    import pandas as pd

    from epidatasets.newsfeeds import NewsAggregator

    items = pd.read_csv(items_csv)
    agg = NewsAggregator()
    locations = agg.geotag(items)
    tagged = locations["url"].nunique() if not locations.empty else 0
    total = items["url"].nunique() if not items.empty else 0
    typer.echo(
        f"Geo-tagged {tagged}/{total} items ({len(locations)} location mentions)."
    )
    agg.plot_map(locations, out=str(out))
    typer.echo(f"Map saved to {out}")


@news_app.command("animate")
def news_animate(
    items_csv: Path = typer.Argument(..., help="CSV of items (from `news fetch --out`)."),
    out: Path = typer.Option("news_map.gif", "--out", "-o"),
    freq: str = typer.Option("W", help="Frame frequency (D, W, ME)."),
) -> None:
    """Render an animated cumulative map (GIF) of geo-tagged items."""
    import pandas as pd

    from epidatasets.newsfeeds import NewsAggregator

    items = pd.read_csv(items_csv)
    agg = NewsAggregator()
    locations = agg.geotag(items)
    agg.animate_map(locations, out=str(out), freq=freq)
    typer.echo(f"Animation saved to {out}")


def main() -> None:
    """Entry-point for the CLI."""
    app()


if __name__ == "__main__":
    main()
