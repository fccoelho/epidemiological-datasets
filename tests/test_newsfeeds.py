"""Tests for the news-feed aggregator (offline, mocked with fixtures)."""

from pathlib import Path

import matplotlib
import pandas as pd
import pytest
import responses

matplotlib.use("Agg")

FIXTURES = Path(__file__).parent / "fixtures" / "newsfeeds"

# the RSS fixture dates are Sep 2026; freeze "now" so `days` filters match
FROZEN_NOW = "2026-09-10T12:00:00+00:00"


# ----------------------------------------------------------------------
# Feed registry
# ----------------------------------------------------------------------


class TestFeedSources:
    def test_registry_contents(self):
        from epidatasets.newsfeeds import FEED_SOURCES

        assert len(FEED_SOURCES) >= 8
        names = list(FEED_SOURCES)
        assert len(names) == len(set(names))
        for src in FEED_SOURCES.values():
            assert src.url.startswith(("http://", "https://"))
            assert src.kind in ("rss", "who_don", "google_news")
            assert src.title and src.language

    def test_disease_tagging(self):
        from epidatasets.newsfeeds import tag_text

        assert tag_text("Dengue outbreak in Brazil") == ["dengue"]
        assert "influenza" in tag_text("Avian influenza A(H5N1) update")
        assert "covid19" in tag_text("COVID-19 hospitalizations rise")
        assert tag_text("Nothing relevant here") == []

    def test_unknown_source_raises(self):
        from epidatasets.newsfeeds import NewsAggregator

        with pytest.raises(KeyError):
            NewsAggregator().fetch(sources=["nonexistent"])


# ----------------------------------------------------------------------
# Geo-tagging (gazetteer)
# ----------------------------------------------------------------------

HEADLINES = [
    ("Dengue outbreak in Brazil", {"BRA"}),
    ("Avian influenza situation in Indonesia - update 32", {"IDN"}),
    ("Cholera vaccination campaign launched in Haiti", {"HTI"}),
    ("Mpox cases confirmed in Kinshasa, DR Congo", {"COD"}),
    ("Measles surge in Nairobi county, Kenya", {"KEN"}),
    ("Yellow fever cluster reported in Angola", {"AGO"}),
    ("Influenza A(H5N1) detected in Cambodia", {"KHM"}),
    ("Nipah virus alert in Kerala, India", {"IND"}),
    ("Dengue spike in Dhaka hospitals, Bangladesh", {"BGD"}),
    ("West Nile virus cases in Italy", {"ITA"}),
    ("Ebola vaccination in Uganda expanded", {"UGA"}),
    ("Chikungunya autochthonous transmission in France", {"FRA"}),
    ("Rift Valley fever reported in Kenya and Somalia", {"KEN", "SOM"}),
    ("Oropouche fever cases rise in Brazil", {"BRA"}),
    ("Crimean-Congo hemorrhagic fever case in Spain", {"ESP"}),
    ("Lassa fever death confirmed in Nigeria", {"NGA"}),
    ("Polio environmental surveillance in Pakistan", {"PAK"}),
    ("Cholera in Sudan and South Sudan", {"SDN", "SSD"}),
    ("Whooping cough resurgence in the USA", {"USA"}),
    ("Malaria cases in the United States", {"USA"}),
    ("Scarlet fever increase in the UK", {"GBR"}),
]


class TestGeotag:
    def test_acceptance_country_level(self):
        """Issue acceptance criterion: >= 80% of items geo-tagged to a
        country mentioned in the headline."""
        from epidatasets.newsfeeds import geotag_text

        hits = 0
        for headline, expected in HEADLINES:
            found = {m.entry.iso3 for m in geotag_text(headline)}
            if expected & found:
                hits += 1
        rate = hits / len(HEADLINES)
        assert rate >= 0.8, f"country hit rate {rate:.0%} < 80%"

    def test_word_boundaries(self):
        from epidatasets.newsfeeds import geotag_text

        # "Niger" must not match inside "Nigeria" and vice versa
        assert {m.entry.iso3 for m in geotag_text("Nigeria outbreak")} == {"NGA"}
        assert {m.entry.iso3 for m in geotag_text("Niger outbreak")} == {"NER"}

    def test_city_vs_country(self):
        from epidatasets.newsfeeds import geotag_text

        matches = geotag_text("Dengue in Sao Paulo, Brazil")
        by_type = {m.entry.type: m.entry.iso3 for m in matches}
        assert by_type.get("city") == "BRA"
        assert by_type.get("country") == "BRA"

    def test_city_wins_over_country_substring(self):
        from epidatasets.newsfeeds import geotag_text

        matches = geotag_text("Yellow fever in Mexico City")
        assert [m.entry.name for m in matches] == ["Mexico City"]

    def test_no_locations(self):
        from epidatasets.newsfeeds import geotag_text

        assert geotag_text("Nothing geographic here") == []
        assert geotag_text("") == []

    def test_accent_insensitive(self):
        from epidatasets.newsfeeds import geotag_text

        assert {m.entry.iso3 for m in geotag_text("Dengue em São Paulo")} == {"BRA"}

    def test_geotag_items_frame(self):
        from epidatasets.newsfeeds import geotag_items

        items = pd.DataFrame(
            [
                {
                    "url": "https://a.example/1",
                    "source": "test",
                    "published_utc": pd.Timestamp("2026-09-07"),
                    "title": "Dengue in Brazil",
                    "summary": "cases in Sao Paulo",
                },
                {
                    "url": "https://a.example/2",
                    "source": "test",
                    "published_utc": pd.Timestamp("2026-09-08"),
                    "title": "Funding news with no places",
                    "summary": "",
                },
            ]
        )
        locs = geotag_items(items)
        assert set(locs.columns) >= {"url", "location_name", "iso3", "lat", "lon"}
        assert len(locs[locs["url"] == "https://a.example/1"]) >= 2
        assert len(locs[locs["url"] == "https://a.example/2"]) == 0


# ----------------------------------------------------------------------
# Aggregator (fetch/normalize/dedupe/tag)
# ----------------------------------------------------------------------


class TestAggregator:
    def _aggregator(self, tmp_path):
        from epidatasets.newsfeeds import NewsAggregator

        return NewsAggregator(cache_dir=str(tmp_path / "cache"))

    @responses.activate
    def test_fetch_rss_normalizes(self, tmp_path):
        from epidatasets.newsfeeds import NewsAggregator

        agg = NewsAggregator(cache_dir=str(tmp_path / "c"), requests_per_source=100)
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://www.who.int/rss-feeds/news-english.xml",
                body=(FIXTURES / "rss_sample.xml").read_bytes(),
                content_type="application/rss+xml",
            )
            items = agg.fetch(sources=["who_news"], days=36500)

        # 4 parsed - 1 fuzzy duplicate = 3
        assert len(items) == 3
        row = items[items["url"].str.contains("dengue-brazil")].iloc[0]
        assert row["source"] == "who_news"
        assert row["published_utc"] == pd.Timestamp("2026-09-07 10:00:00")
        assert "dengue" in row["disease_tags"]
        # HTML stripped from summary
        assert "<b>" not in row["summary"]
        assert "1,200 cases" in row["summary"]

    @responses.activate
    def test_fetch_who_don(self, tmp_path):
        import re

        from epidatasets.newsfeeds import NewsAggregator

        agg = NewsAggregator(cache_dir=str(tmp_path / "c"), requests_per_source=100)
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                re.compile(r".*diseaseoutbreaknews.*"),
                body=(FIXTURES / "who_don_sample.json").read_bytes(),
                content_type="application/json",
            )
            items = agg.fetch(sources=["who_don"], days=36500)

        assert len(items) == 2
        haiti = items[items["title"].str.contains("Cholera")].iloc[0]
        assert haiti["url"].startswith("https://www.who.int/")
        assert haiti["published_utc"] == pd.Timestamp("2026-09-05")
        assert "cholera" in haiti["disease_tags"]

    @responses.activate
    def test_google_news_query_feed(self, tmp_path):
        import re

        from epidatasets.newsfeeds import NewsAggregator

        agg = NewsAggregator(cache_dir=str(tmp_path / "c"), requests_per_source=100)
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                re.compile(r".*news-english\.xml"),
                body=(FIXTURES / "rss_sample.xml").read_bytes(),
                content_type="application/rss+xml",
            )
            rsps.add(
                responses.GET,
                re.compile(r".*news\.google\.com/rss/search.*"),
                body=(FIXTURES / "google_news_sample.xml").read_bytes(),
                content_type="application/rss+xml",
            )
            items = agg.fetch(
                sources=["who_news"], queries=["yellow fever"], days=36500
            )

        names = set(items["source"])
        assert any(n.startswith("google_news") for n in names)
        assert "who_news" in names
        gnews = items[items["source"].str.startswith("google_news")]
        assert "yellow_fever" in gnews.iloc[0]["disease_tags"]

    @responses.activate
    def test_cache_hit_second_fetch(self, tmp_path):
        from epidatasets.newsfeeds import NewsAggregator

        agg = NewsAggregator(cache_dir=str(tmp_path / "c"), requests_per_source=100)
        url = "https://www.who.int/rss-feeds/news-english.xml"
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                url,
                body=(FIXTURES / "rss_sample.xml").read_bytes(),
                content_type="application/rss+xml",
            )
            agg.fetch(sources=["who_news"], days=36500)
            agg.fetch(sources=["who_news"], days=36500)
            rsps.assert_call_count(url, 1)

    @responses.activate
    def test_per_source_error_tolerance(self, tmp_path):
        from epidatasets.newsfeeds import NewsAggregator

        agg = NewsAggregator(cache_dir=str(tmp_path / "c"), requests_per_source=100)
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://www.who.int/rss-feeds/news-english.xml",
                body=(FIXTURES / "error_page.html").read_bytes(),
                status=500,
            )
            rsps.add(
                responses.GET,
                "https://www.who.int/api/news/diseaseoutbreaknews"
                "?$orderby=PublicationDate%20desc&$top=50",
                body=(FIXTURES / "who_don_sample.json").read_bytes(),
                content_type="application/json",
            )
            items = agg.fetch(
                sources=["who_news", "who_don"],
                days=36500,
            )

        assert len(items) == 2  # only who_don succeeded
        status = agg.last_fetch_status
        assert status["who_news"]["error"] is not None
        assert status["who_don"]["error"] is None

    def test_canonical_url(self):
        from epidatasets.newsfeeds.aggregator import canonical_url

        a = canonical_url(
            "https://Example.org/news/x?utm_source=fb&id=2&fbclid=zz"
        )
        b = canonical_url("https://example.org/news/x?id=2")
        assert a == b
        assert canonical_url("https://example.org/x#frag") == "https://example.org/x"

    def test_dedupe_by_title_similarity(self):
        from datetime import datetime

        from epidatasets.newsfeeds.aggregator import NewsAggregator
        from epidatasets.newsfeeds.models import FeedItem

        items = [
            FeedItem("s", "Dengue outbreak sweeps Sao Paulo, Brazil",
                     "https://a.example/1",
                     datetime(2026, 9, 7, 10)),
            FeedItem("s", "Dengue outbreak sweeps Sao Paulo, Brazil!",
                     "https://b.example/2",
                     datetime(2026, 9, 7, 11)),
            FeedItem("s", "Cholera hits Haiti", "https://c.example/3",
                     datetime(2026, 9, 7, 12)),
        ]
        kept = NewsAggregator._dedupe(items)
        assert {it.url for it in kept} == {"https://a.example/1", "https://c.example/3"}


# ----------------------------------------------------------------------
# Visualization
# ----------------------------------------------------------------------


class TestVisualize:
    @pytest.fixture
    def items(self):
        return pd.DataFrame(
            [
                {"url": "https://a/1", "title": "Dengue in Brazil",
                 "published_utc": pd.Timestamp("2026-09-01"),
                 "disease_tags": "dengue", "source": "who_news"},
                {"url": "https://a/2", "title": "Mpox in DRC",
                 "published_utc": pd.Timestamp("2026-09-03"),
                 "disease_tags": "mpox", "source": "who_don"},
                {"url": "https://a/3", "title": "Cholera in Haiti",
                 "published_utc": pd.Timestamp("2026-09-08"),
                 "disease_tags": "cholera", "source": "who_don"},
            ]
        )

    @pytest.fixture
    def locations(self, items):
        return pd.DataFrame(
            [
                {"url": "https://a/1", "title": "Dengue in Brazil",
                 "published_utc": pd.Timestamp("2026-09-01"),
                 "location_name": "Brazil", "location_type": "country",
                 "iso3": "BRA", "lat": -10.8, "lon": -52.9},
                {"url": "https://a/2", "title": "Mpox in DRC",
                 "published_utc": pd.Timestamp("2026-09-03"),
                 "location_name": "Kinshasa", "location_type": "city",
                 "iso3": "COD", "lat": -4.44, "lon": 15.27},
                {"url": "https://a/3", "title": "Cholera in Haiti",
                 "published_utc": pd.Timestamp("2026-09-08"),
                 "location_name": "Haiti", "location_type": "country",
                 "iso3": "HTI", "lat": 19.0, "lon": -72.4},
            ]
        )

    def test_timeline_png(self, items, tmp_path):
        import matplotlib.pyplot as plt

        from epidatasets.newsfeeds import plot_timeline

        out = tmp_path / "timeline.png"
        fig = plot_timeline(items, by="disease_tags", out=str(out))
        assert out.exists() and out.stat().st_size > 0
        plt.close(fig)

    def test_timeline_by_source(self, items, tmp_path):
        import matplotlib.pyplot as plt

        from epidatasets.newsfeeds import plot_timeline

        fig = plot_timeline(items, by="source", freq="ME")
        plt.close(fig)

    def test_map_html(self, locations, tmp_path):
        pytest.importorskip("folium")
        from epidatasets.newsfeeds import plot_map

        out = tmp_path / "map.html"
        fmap = plot_map(locations, out=str(out))
        assert out.exists()
        html = out.read_text()
        assert "firebrick" in html or "folium" in html.lower()
        assert fmap is not None

    def test_map_empty_raises(self, tmp_path):
        pytest.importorskip("folium")
        from epidatasets.newsfeeds import plot_map

        with pytest.raises(ValueError):
            plot_map(pd.DataFrame(), out=str(tmp_path / "m.html"))

    def test_animate_gif(self, locations, tmp_path, monkeypatch):
        from epidatasets.newsfeeds import visualize

        monkeypatch.setattr(visualize, "_load_world_geojson", lambda **kw: None)
        out = tmp_path / "news.gif"
        result = visualize.animate_map(locations, out=str(out), freq="W")
        assert result == str(out)
        assert out.exists() and out.stat().st_size > 0

    def test_animate_empty_raises(self, tmp_path):
        from epidatasets.newsfeeds import visualize

        with pytest.raises(ValueError):
            visualize.animate_map(pd.DataFrame(), out=str(tmp_path / "x.gif"))
