# News-Feed Aggregator

The `epidatasets.newsfeeds` module complements the numeric data accessors
with **narrative early-warning signals**: it aggregates open
public-health news feeds, normalizes them to a common schema,
deduplicates items, tags diseases and geo-tags location mentions, and
produces spatiotemporal visualizations (timeline, interactive map,
animated cumulative map).

## Installation

```bash
pip install "epidatasets[news,geo]"   # fetching + map output
```

## Quick start

```python
from epidatasets.newsfeeds import NewsAggregator

agg = NewsAggregator()                     # feeds cached on disk (TTL 6h)
items = agg.fetch(days=30)                 # -> tidy DataFrame
locations = agg.geotag(items)              # one row per (item, location)

agg.plot_timeline(items, by="disease_tags", out="timeline.png")
agg.plot_map(locations, out="news_map.html")
agg.animate_map(locations, out="news_map.gif", freq="W")
```

Or from the command line:

```bash
epidatasets news feeds                                 # list feeds
epidatasets news fetch --days 30 -o items.csv          # fetch + tag
epidatasets news fetch --query "dengue when:30d" -o dengue.csv
epidatasets news plot items.csv --timeline -o timeline.png
epidatasets news map items.csv -o news_map.html
epidatasets news animate items.csv -o news_map.gif
```

## Supported feeds

All endpoints are open (HTTP 200, valid RSS/XML or JSON, verified at
integration time). Every feed fails independently: one unavailable
source never blocks the others — check `aggregator.last_fetch_status`.

| Feed | `source` name | Kind | Licensing / ToS notes |
|---|---|---|---|
| WHO News (EN) | `who_news` | RSS | WHO web content; reuse for research with attribution. |
| WHO Disease Outbreak News | `who_don` | OData JSON | No public RSS; the JSON API is richer (title, summary, date per outbreak). |
| WHO Regional Office for Africa | `who_afro` | RSS | WHO AFRO web content; research use with attribution. |
| PAHO/WHO Americas | `paho` | RSS | PAHO web content; research use with attribution. |
| Eurosurveillance (journal) | `eurosurveillance` | RSS | Open-access journal (CC BY); article metadata via RSS. |
| CDC Online Newsroom | `cdc_newsroom` | RSS (API) | Served by the CDC syndication API; more topic feeds at tools.cdc.gov. |
| CIDRAP (U. Minnesota) | `cidrap` | RSS | Respect CIDRAP terms of use. |
| Outbreak News Today | `outbreak_news_today` | RSS | Independent outlet; attribute and link back. |
| Google News topic search | dynamic | RSS (template) | Per-query feeds via `--query`/`queries=`; **low-volume research use**, subject to Google's ToS. |

Checked and **not** programmatically usable (for reference):
ProMED-mail (public RSS discontinued / paywalled), HealthMap
(403/404), ReliefWeb RSS (bot-protected — their REST API is the viable
route, deferred), ECDC (feed listing is JS-rendered; to be added in a
follow-up).

## How it works

1. **Fetch** — feeds are downloaded concurrently (polite per-source
   rate limiting, research User-Agent, 20 s timeout) and cached as JSON
   on disk (TTL 6 h by default).
2. **Normalize** — every item becomes `source, title, url,
   published_utc (UTC), summary (HTML-stripped), language, disease_tags,
   feed_url`.
3. **Deduplicate** — canonical-URL exact matches are dropped first
   (tracking parameters stripped), then near-identical headlines within
   one day are collapsed across sources, keeping the earliest.
4. **Tag** — ~30 diseases are matched by keyword regexes over title +
   summary (`tag_text`).
5. **Geo-tag** — location mentions are matched against an embedded
   gazetteer (Natural Earth admin-0 names/aliases, ~50 US states, and
   ~200 major cities — all public-domain data, no NLP dependencies).
   Each item produces one row per mentioned location, resolved to
   `iso3 / lat / lon`. Case-sensitive `US` is recognized; the pronoun
   "us" is not.

### Geo-tagging precision

Matching is deliberately conservative (word-boundary, longest-alias,
accent-insensitive). On outbreak headlines that name a location the
gazetteer achieves well above the 80% country-level target
(see `tests/test_newsfeeds.py::TestGeotag`); on live mixed feeds the
recall is lower simply because a share of items (agency statements,
journal articles, policy news) genuinely mention no location.

## API

See the [News Feeds API reference](api/newsfeeds.md) for the full
signature documentation.
