"""
News-feed aggregator for public-health and epidemiology news.

Fetches open news feeds (WHO, PAHO, CDC, Eurosurveillance, CIDRAP,
Outbreak News Today, Google News topic queries) concurrently, normalizes
them to a common schema, deduplicates items, tags diseases mentioned and
geo-tags location mentions, with matplotlib/folium visualization helpers
(timeline, interactive map, animated cumulative map).

Requires the ``news`` extra for fetching (``pip install epidatasets[news]``)
and the ``geo`` extra for map output (``pip install epidatasets[geo]``).

Example:
    >>> from epidatasets.newsfeeds import NewsAggregator
    >>> agg = NewsAggregator()
    >>> items = agg.fetch(days=30)                 # doctest: +SKIP
    >>> locations = agg.geotag(items)              # doctest: +SKIP
    >>> agg.plot_timeline(items, out="timeline.png")   # doctest: +SKIP
    >>> agg.plot_map(locations, out="news_map.html")   # doctest: +SKIP
    >>> agg.animate_map(locations, out="news.gif")     # doctest: +SKIP

Author: Flávio Codeço Coelho
License: MIT
"""

from epidatasets.newsfeeds.aggregator import NewsAggregator, fetch_news
from epidatasets.newsfeeds.geotag import geotag_items, geotag_text
from epidatasets.newsfeeds.models import FeedItem, FeedSource
from epidatasets.newsfeeds.sources import FEED_SOURCES, tag_text
from epidatasets.newsfeeds.visualize import (
    animate_map,
    plot_map,
    plot_timeline,
)

__all__ = [
    "FEED_SOURCES",
    "FeedItem",
    "FeedSource",
    "NewsAggregator",
    "animate_map",
    "fetch_news",
    "geotag_items",
    "geotag_text",
    "plot_map",
    "plot_timeline",
    "tag_text",
]
