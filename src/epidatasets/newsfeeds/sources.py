"""
Registry of public-health news feeds and disease keyword definitions.

All endpoints were verified reachable at integration time. Each entry
carries a licensing/ToS note surfaced in the documentation.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import re

from epidatasets.newsfeeds.models import FeedSource

#: Google News RSS topic-search template (dynamic per-query feed).
#: Intended for low-volume research use, subject to Google's ToS.
GOOGLE_NEWS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}"
    "&hl={hl}&gl={gl}&ceid={ceid}"
)

#: Default Google News topic query used when no custom queries are given.
DEFAULT_GOOGLE_NEWS_QUERY = (
    '(dengue OR influenza OR cholera OR measles OR mpox OR ebola '
    'OR "outbreak" OR "epidemic") when:30d'
)

#: Curated registry of verified open news feeds.
FEED_SOURCES: dict[str, FeedSource] = {
    "who_news": FeedSource(
        name="who_news",
        url="https://www.who.int/rss-feeds/news-english.xml",
        kind="rss",
        title="WHO News (English)",
        language="en",
        homepage="https://www.who.int/news",
        notes="WHO web content; reuse for research with attribution.",
    ),
    "who_don": FeedSource(
        name="who_don",
        url=(
            "https://www.who.int/api/news/diseaseoutbreaknews"
            "?$orderby=PublicationDate desc&$top={limit}"
        ),
        kind="who_don",
        title="WHO Disease Outbreak News (DON)",
        language="en",
        homepage="https://www.who.int/emergencies/disease-outbreak-news",
        notes=(
            "OData JSON API (DON has no public RSS). Richer than RSS: "
            "title, summary and publication date per outbreak."
        ),
    ),
    "who_afro": FeedSource(
        name="who_afro",
        url="https://www.afro.who.int/rss.xml",
        kind="rss",
        title="WHO Regional Office for Africa",
        language="en",
        homepage="https://www.afro.who.int/",
        notes="WHO AFRO web content; research use with attribution.",
    ),
    "paho": FeedSource(
        name="paho",
        url="https://www.paho.org/en/rss.xml",
        kind="rss",
        title="PAHO/WHO Americas",
        language="en",
        homepage="https://www.paho.org/en",
        notes="PAHO web content; research use with attribution.",
    ),
    "eurosurveillance": FeedSource(
        name="eurosurveillance",
        url="https://www.eurosurveillance.org/rss/content/all/latest?fmt=rss",
        kind="rss",
        title="Eurosurveillance (journal)",
        language="en",
        homepage="https://www.eurosurveillance.org/",
        notes="Open-access journal (CC BY); article metadata via RSS.",
    ),
    "cdc_newsroom": FeedSource(
        name="cdc_newsroom",
        url="https://tools.cdc.gov/api/v2/resources/media/132608.rss",
        kind="rss",
        title="CDC Online Newsroom",
        language="en",
        homepage="https://tools.cdc.gov/medialibrary/",
        notes=(
            "Served by the CDC syndication API, which exposes more topic "
            "feeds (incl. outbreaks) at tools.cdc.gov."
        ),
    ),
    "cidrap": FeedSource(
        name="cidrap",
        url="https://www.cidrap.umn.edu/rss.xml",
        kind="rss",
        title="CIDRAP (University of Minnesota)",
        language="en",
        homepage="https://www.cidrap.umn.edu/",
        notes="News summaries; respect CIDRAP terms of use.",
    ),
    "outbreak_news_today": FeedSource(
        name="outbreak_news_today",
        url="http://outbreaknewstoday.com/feed/",
        kind="rss",
        title="Outbreak News Today",
        language="en",
        homepage="http://outbreaknewstoday.com/",
        notes="Independent outbreak news site; attribute and link back.",
    ),
}

#: Checked and **not** programmatically usable (documented for reference):
#: ProMED-mail (public RSS discontinued/paywalled), HealthMap (403/404),
#: ReliefWeb RSS (bot-protected — its REST API api.reliefweb.int is the
#: viable route, deferred), ECDC (feed listing is JS-rendered; concrete
#: feed URLs to be added in a follow-up).

#: Disease tag -> compiled regexes matched against title + summary.
DISEASE_KEYWORDS: dict[str, list[re.Pattern[str]]] = {
    name: [re.compile(pat, re.IGNORECASE) for pat in patterns]
    for name, patterns in {
        "dengue": [r"\bdengue\b", r"\bDENV[- ]?[1-4]\b"],
        "influenza": [
            r"\binfluenza\b",
            r"\bflu\b",
            r"\bH[1-9]N[1-9]\b",
            r"bird flu",
            r"avian influenza",
            r"swine flu",
        ],
        "covid19": [
            r"\bcovid[- ]?19\b",
            r"\bsars[- ]?cov[- ]?2\b",
            r"coronavirus",
        ],
        "mpox": [r"\bmpox\b", r"monkeypox"],
        "cholera": [r"\bcholera\b"],
        "measles": [r"\bmeasles\b", r"\brubeola\b"],
        "ebola": [r"\bebola\b"],
        "zika": [r"\bzika\b"],
        "yellow_fever": [r"yellow fever"],
        "malaria": [r"\bmalaria\b"],
        "tuberculosis": [r"tuberculosis", r"\bTB\b(?![a-z])"],
        "polio": [r"\bpolio\b", r"poliomyelitis"],
        "chikungunya": [r"chikungunya"],
        "rift_valley_fever": [r"rift valley fever"],
        "lassa": [r"lassa fever"],
        "marburg": [r"marburg"],
        "nipah": [r"\bnipah\b"],
        "hiv": [r"\bhiv\b", r"\baids\b"],
        "hepatitis": [r"hepatitis [a-e]"],
        "rabies": [r"\brabies\b"],
        "meningitis": [r"meningitis", r"meningococcal"],
        "avian_influenza": [r"H5N1", r"H7N9", r"H5N6", r"avian influenza"],
        "ors": [r"Oropouche", r"\bORSV\b"],
        "sftsv": [r"heat stroke with thrombocytopenia syndrome",
                  r"SFTS"],
        "whooping_cough": [r"whooping cough", r"\bpertussis\b"],
        "scarlet_fever": [r"scarlet fever"],
        "white_nose": [r"white[- ]nose syndrome"],
        "leishmaniasis": [r"leishmaniasis", r"kala-?azar"],
        "scrub_typhus": [r"scrub typhus"],
        "west_nile": [r"West Nile"],
        "eastern_equine": [r"eastern equine encephalitis", r"\bEEEV?\b"],
    }.items()
}


def tag_text(text: str) -> list[str]:
    """
    Return the disease tags whose keyword patterns match *text*.

    Args:
        text: Free text (typically title + summary), matched as-is;
            patterns are case-insensitive.

    Returns:
        Sorted list of disease tag names.
    """
    if not text:
        return []
    return sorted(
        name
        for name, patterns in DISEASE_KEYWORDS.items()
        if any(p.search(text) for p in patterns)
    )
