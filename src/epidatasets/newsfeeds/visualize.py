"""
Spatiotemporal visualization for aggregated news items.

Outputs (per issue #95):
- timeline PNG: weekly/monthly item counts per disease/source
  (matplotlib, a core dependency)
- interactive map HTML: item density by location (folium, from the
  ``geo`` extra)
- animated cumulative map GIF (matplotlib.animation + PillowWriter)

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
import math
import os

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)

#: Natural Earth 110m country outlines (public domain), used for the
#: animated map. Downloaded once and cached on disk.
_WORLD_GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)


# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------

def plot_timeline(
    items: pd.DataFrame,
    by: str = "disease_tags",
    freq: str = "W",
    out: str | None = None,
    ax=None,
):
    """
    Plot a timeline of news-item counts.

    Args:
        items: DataFrame as returned by
            :meth:`NewsAggregator.fetch` (needs ``published_utc``).
        by: Column to split the counts by. ``"disease_tags"`` (default)
            explodes the pipe-joined tags into one row per disease;
            any other column (e.g. ``"source"``) is used as-is.
        freq: Pandas offset alias for the bins (``"W"`` weekly,
            ``"D"`` daily, ``"ME"`` monthly).
        out: Optional path to save the figure (e.g. ``timeline.png``).
        ax: Optional matplotlib axes to draw on.

    Returns:
        The matplotlib Figure.
    """
    df = items.copy()
    df["published_utc"] = pd.to_datetime(df["published_utc"])
    df = df.dropna(subset=["published_utc"])

    if by == "disease_tags":
        df = df.assign(
            disease_tags=df["disease_tags"].fillna("").replace("", "untagged")
        ).assign(disease_tags=lambda d: d["disease_tags"].str.split("|")).explode(
            "disease_tags"
        )
    series_col = by if by in df.columns else "source"

    counts = (
        df.set_index("published_utc")
        .groupby([pd.Grouper(freq=freq), series_col])
        .size()
        .unstack(fill_value=0)
    )

    if ax is None:
        _, ax = plt.subplots(figsize=(11, 4))
    counts.plot(kind="bar", stacked=True, ax=ax, width=1.0)
    ax.set_ylabel("items")
    ax.set_title(f"Public-health news items per {'week' if freq.startswith('W') else freq}")
    ax.legend(title=series_col, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    labels = [ts.strftime("%Y-%m-%d") for ts in counts.index]
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    fig = ax.figure
    fig.tight_layout()
    if out:
        fig.savefig(out, dpi=150, bbox_inches="tight")
        logger.info("Timeline saved to %s", out)
    return fig


# ---------------------------------------------------------------------
# Interactive map
# ---------------------------------------------------------------------

def plot_map(locations: pd.DataFrame, out: str | None = None):
    """
    Plot an interactive folium map of geo-tagged news items.

    Args:
        locations: DataFrame as returned by
            :meth:`NewsAggregator.geotag` (needs ``lat``, ``lon``,
            ``location_name``; optional ``title``, ``published_utc``).
        out: Optional path to save the HTML map (e.g. ``news_map.html``).

    Returns:
        The ``folium.Map`` object.

    Raises:
        ImportError: If folium is not installed (``pip install
            epidatasets[geo]``).
    """
    try:
        import folium
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise ImportError(
            "folium is required for map plotting. "
            "Install with: pip install epidatasets[geo]"
        ) from exc

    if locations.empty:
        raise ValueError("No geo-tagged locations to plot")

    agg = (
        locations.groupby(["location_name", "lat", "lon"])
        .agg(count=("location_name", "size"))
        .reset_index()
    )

    center = [agg["lat"].mean(), agg["lon"].mean()]
    fmap = folium.Map(location=center, zoom_start=2, tiles="OpenStreetMap")

    max_count = max(1, int(agg["count"].max()))
    for _, row in agg.iterrows():
        count = int(row["count"])
        radius = 4 + 10 * math.sqrt(count / max_count)
        titles = locations[locations["location_name"] == row["location_name"]]
        if "title" in titles.columns and "url" in titles.columns:
            sample = [
                f'<a href="{u}">{t}</a>'
                for t, u in zip(
                    titles["title"].head(5),
                    titles["url"].head(5),
                    strict=False,
                )
            ]
        else:
            sample = []
        popup_html = f"<b>{row['location_name']}</b> ({count} item{'s' if count > 1 else ''})"
        if sample:
            popup_html += "<br>" + "<br>".join(sample)
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=360),
            color="firebrick",
            fill=True,
            fill_color="firebrick",
            fill_opacity=0.55,
        ).add_to(fmap)

    if out:
        fmap.save(out)
        logger.info("Map saved to %s", out)
    return fmap


# ---------------------------------------------------------------------
# Animated cumulative map
# ---------------------------------------------------------------------

def _load_world_geojson(cache_dir: str | None = None) -> dict | None:
    """
    Load (and cache) the Natural Earth 110m country outlines.
    Returns ``None`` when the download fails (offline use).
    """
    from epidatasets.utils.cache import CacheManager

    if cache_dir is None:
        cache_dir = os.path.join(
            os.path.expanduser("~"), ".cache", "epidatasets", "newsfeeds"
        )
    cache = CacheManager(cache_dir=cache_dir)
    key = "world_110m_geojson"
    cached = cache.get(key, max_age_hours=24 * 30)
    if cached is not None:
        return cached
    try:
        import requests

        resp = requests.get(
            _WORLD_GEOJSON_URL,
            headers={"User-Agent": "epidatasets-newsfeeds/1.0"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        cache.set(key, data)
        return data
    except Exception as exc:
        logger.warning("Could not download world outlines: %s", exc)
        return None


def _draw_world(ax, world: dict | None) -> None:
    """Draw country outlines (or a plain grid fallback) on *ax*."""
    ax.set_facecolor("white")
    if world is None:
        ax.grid(True, linewidth=0.3, alpha=0.5)
        return
    for feature in world.get("features", []):
        geom = feature["geometry"]
        polys = (
            geom["coordinates"]
            if geom["type"] == "MultiPolygon"
            else [geom["coordinates"]]
        )
        for poly in polys:
            ring = poly[0]
            lons = [c[0] for c in ring]
            lats = [c[1] for c in ring]
            ax.plot(lons, lats, color="lightgray", linewidth=0.4)


def animate_map(
    locations: pd.DataFrame,
    out: str = "news_map.gif",
    freq: str = "W",
    interval_days: int | None = None,
    dpi: int = 110,
):
    """
    Render an animated GIF of the cumulative geographic spread of
    geo-tagged news items over time.

    Args:
        locations: DataFrame as returned by
            :meth:`NewsAggregator.geotag` (needs ``lat``, ``lon``,
            ``published_utc``).
        out: Output GIF path.
        freq: Pandas offset alias for the animation frames (``"W"``
            weekly, ``"D"`` daily, ``"ME"`` monthly).
        interval_days: Deprecated alias for *freq* kept for
            compatibility; ignored when *freq* is given.
        dpi: Figure resolution.

    Returns:
        The output path.
    """
    df = locations.copy()
    if "published_utc" not in df.columns or df.empty:
        raise ValueError("No geo-tagged items with dates to animate")
    df["published_utc"] = pd.to_datetime(df["published_utc"])
    df = df.dropna(subset=["published_utc", "lat", "lon"])
    if df.empty:
        raise ValueError("No geo-tagged items with dates to animate")

    df = df.sort_values("published_utc")
    periods = sorted(df["published_utc"].dt.to_period(freq).unique())
    world = _load_world_geojson()

    from matplotlib.animation import FuncAnimation, PillowWriter

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 80)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")

    def _draw_frame(i: int):
        ax.clear()
        _draw_world(ax, world)
        end = periods[i].end_time.tz_localize(None)
        frame = df[df["published_utc"] <= end]
        ax.scatter(
            frame["lon"],
            frame["lat"],
            s=18,
            color="firebrick",
            alpha=0.7,
            edgecolors="none",
        )
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 80)
        ax.set_title(
            f"Public-health news items (cumulative) — up to {periods[i]}"
        )
        return []

    anim = FuncAnimation(
        fig, _draw_frame, frames=len(periods), interval=600, blit=False
    )
    anim.save(out, writer=PillowWriter(fps=2), dpi=dpi)
    plt.close(fig)
    logger.info("Animation saved to %s (%d frames)", out, len(periods))
    return out
