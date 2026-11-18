# Methodology & References

This page maps each methodology implemented in `epidatasets` to the
books, articles, specifications and encyclopedic references that
describe it. All links were checked to resolve at the time of writing,
and bibliographic entries were verified against the
[CrossRef](https://www.crossref.org) metadata registry (publisher sites
may serve `403` to scripted clients; the DOIs themselves are
authoritative).

## Event-based & digital disease surveillance

The news-feed aggregator
([`epidatasets.newsfeeds`](newsfeeds.md)) implements an
**event-based surveillance** workflow: it continuously harvests public
news reports about outbreaks as narrative early-warning signals,
complementing indicator-based (case-count) data sources.

- World Health Organization (2014). *Early detection, assessment and
  response to acute public health events: implementation of early
  warning and response with a focus on event-based surveillance*
  (interim version). Geneva: WHO.
  <https://iris.who.int/handle/10665/112667>
- Brownstein, J. S., Freifeld, C. C. & Madoff, L. C. (2009). Digital
  Disease Detection — Harnessing the Web for Public Health
  Surveillance. *New England Journal of Medicine*, 360(21), 2153–2157.
  <https://doi.org/10.1056/NEJMp0900702>
- Freifeld, C. C., Mandl, K. D., Reis, B. Y. & Brownstein, J. S.
  (2008). HealthMap: Global Infectious Disease Monitoring through
  Automated Classification and Visualization of Internet Media
  Reports. *Journal of the American Medical Informatics Association*,
  15(2), 150–157. <https://doi.org/10.1197/jamia.m2544>
- Brownstein, J. S., Freifeld, C. C., Reis, B. Y. & Mandl, K. D.
  (2008). Surveillance Sans Frontières: Internet-Based Emerging
  Infectious Disease Intelligence and the HealthMap Project. *PLoS
  Medicine*, 5(7), e151. <https://doi.org/10.1371/journal.pmed.0050151>
- Wikipedia: [Public health
  surveillance](https://en.wikipedia.org/wiki/Public_health_surveillance)

## News-feed aggregation (RSS / Atom)

The aggregator consumes syndication feeds with
[`feedparser`](https://feedparser.readthedocs.io/en/latest/), which
implements the RSS and Atom formats and absorbs their real-world
dialects.

- Wikipedia: [RSS](https://en.wikipedia.org/wiki/RSS) —
  [News aggregator](https://en.wikipedia.org/wiki/News_aggregator)
- RSS 2.0 Specification. RSS Advisory Board.
  <https://www.rssboard.org/rss-specification>
- Nottingham, M. & Sayre, R. (2005). *The Atom Syndication Format*.
  IETF RFC 4287. <https://datatracker.ietf.org/doc/html/rfc4287>

## Text normalization

Headlines and summaries are normalized (accent stripping via Unicode
NFKD decomposition, case folding, whitespace collapsing) before
matching, so that "São Paulo" and "Sao Paulo" compare equal.

- Unicode Consortium. *Unicode Standard Annex #15 — Unicode
  Normalization Forms*. <https://www.unicode.org/reports/tr15/>
- Wikipedia:
  [Unicode equivalence](https://en.wikipedia.org/wiki/Unicode_equivalence)

## Gazetteer-based geo-tagging (toponym recognition & resolution)

Location mentions in news text are recognized by word-boundary
matching against an embedded gazetteer and resolved to ISO 3166 codes
and coordinates — the classic **gazetteer matching** approach to
geoparsing, chosen over statistical NER for determinism, offline
operation and zero heavy dependencies. It implements the recognition
stage of the geoparsing pipeline (recognition + disambiguation/resolution).

- Wikipedia: [Gazetteer](https://en.wikipedia.org/wiki/Gazetteer) —
  [Toponym resolution](https://en.wikipedia.org/wiki/Toponym_resolution)
  — [Named-entity recognition](https://en.wikipedia.org/wiki/Named-entity_recognition)
- Gritta, M., Pilehvar, M., Limsopatham, V. & Collier, N. (2017).
  What's missing in geographical parsing? *Language Resources and
  Evaluation*, 52(2), 603–623. <https://doi.org/10.1007/s10579-017-9385-8>
- Middleton, S. E., Kordopatis-Zilos, G., Papadopoulos, S. &
  Kompatsiaris, Y. (2018). Location Extraction from Social Media.
  *ACM Transactions on Information Systems*, 36(4), 1–27.
  <https://doi.org/10.1145/3202662>
- Gazetteer source data: [Natural
  Earth](https://en.wikipedia.org/wiki/Natural_Earth) (public domain)
  and [ISO 3166-1](https://en.wikipedia.org/wiki/ISO_3166-1) country
  codes (also used by
  [`standardize_country_code`](api/utils.md)).

## Near-duplicate detection (deduplication)

Duplicate news items are removed in two stages: canonical-URL exact
matches (after
[URL normalization](https://en.wikipedia.org/wiki/URL_normalization) —
tracking parameters stripped, host lower-cased) and near-identical
headlines within one day, compared with the similarity ratio of
`difflib.SequenceMatcher`, which implements the **Gestalt pattern
matching** (Ratcliff–Obershelp) algorithm.

- Wikipedia: [URL
  normalization](https://en.wikipedia.org/wiki/URL_normalization) —
  [Gestalt pattern matching](https://en.wikipedia.org/wiki/Gestalt_pattern_matching)
  — [Levenshtein
  distance](https://en.wikipedia.org/wiki/Levenshtein_distance) (the
  related edit-distance measure)
- Python documentation:
  [`difflib.SequenceMatcher`](https://docs.python.org/3/library/difflib.html)

## Disease tagging (keyword / dictionary matching)

Disease tags are assigned by case-insensitive keyword patterns over
title + summary — dictionary matching, the rule-based variant of
entity classification described in the NER literature, expressed as
[regular
expressions](https://en.wikipedia.org/wiki/Regular_expression).

- Wikipedia:
  [Named-entity recognition](https://en.wikipedia.org/wiki/Named-entity_recognition)
  — [Regular expression](https://en.wikipedia.org/wiki/Regular_expression)

## TTL caching

Feed responses and downloaded documents are cached on disk with a
time-to-live: entries expire after a configurable age (see
[`CacheManager`](api/utils.md)).

- Wikipedia:
  [Cache (computing)](https://en.wikipedia.org/wiki/Cache_%28computing%29)
  — [Time to live](https://en.wikipedia.org/wiki/Time_to_live)

## Rate limiting & polite fetching

Requests are paced per source (fixed-interval throttling, cf. the
token/leaky-bucket formulations) with a research-purpose User-Agent —
the politeness expectations for automated web access.

- Wikipedia: [Token bucket](https://en.wikipedia.org/wiki/Token_bucket)
  — [Leaky bucket](https://en.wikipedia.org/wiki/Leaky_bucket) —
  [Web crawler](https://en.wikipedia.org/wiki/Web_crawler) (§ Politeness policy)

## Concurrent fetching

Feeds are harvested in parallel with a bounded
[thread pool](https://en.wikipedia.org/wiki/Thread_pool)
(`concurrent.futures.ThreadPoolExecutor`), one failure never blocking
the remaining sources.

- Wikipedia: [Thread pool](https://en.wikipedia.org/wiki/Thread_pool)

## PDF text & table extraction

Notifiable-disease tables are extracted from journal PDFs with
[text-layer parsing](https://github.com/jsvine/pdfplumber)
(`pypdf`) and
[table extraction](https://github.com/jsvine/pdfplumber)
(`pdfplumber`), with a text-line fallback when table detection fails
(see [`PDFParser`](api/utils.md)).

- Tool documentation: [pdfplumber](https://github.com/jsvine/pdfplumber)

## Geovisualization

Aggregated news items are rendered as spatiotemporal displays —
timeline charts, interactive point maps and cumulative map animations —
in the tradition of geovisualization for exploratory analysis.

- Wikipedia:
  [Geovisualization](https://en.wikipedia.org/wiki/Geovisualization)

## Package architecture

Accessors plug into the registry via Python packaging **entry points**
(the established plug-in pattern), and all datasets are treated as
open data under
[FAIR](https://en.wikipedia.org/wiki/FAIR_data) principles.

- Python Packaging Authority. *Entry Points* specification.
  <https://packaging.python.org/en/latest/specifications/entry-points/>
- Wikipedia:
  [Plug-in (computing)](https://en.wikipedia.org/wiki/Plug-in_%28computing%29)
  — [FAIR data](https://en.wikipedia.org/wiki/FAIR_data)
