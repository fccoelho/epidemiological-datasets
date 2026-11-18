"""Tests for the SRAG (Sivep-Gripe / e-SUS Notifica) accessor.

Network-free tests mock the OpenData SUS portal metadata and the S3
downloads using the ``responses`` library.  Live tests are gated behind
``@pytest.mark.external_api``.
"""

from pathlib import Path
from unittest import mock

import pandas as pd
import pytest
import responses

from epidatasets.sources.srag_opendata_sus import (
    SRAGDataError,
    SRAGOpenDataSUSAccessor,
)

FIXTURES = Path(__file__).parent / "fixtures" / "srag"

S3_2024_CSV = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2024/INFLUD24-23-03-2026.csv"
S3_2023_CSV = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2023/INFLUD23-23-03-2026.csv"
IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def portal_resources():
    """Fake OpenData SUS resource list for the SRAG dataset."""
    rows = []
    for year, suffix in [
        (2023, "23-03-2026"),
        (2024, "23-03-2026"),
        (2026, "28-09-2026"),
    ]:
        yy = year % 100
        for fmt, ext in [("CSV", "csv"), ("PARQUET", "parquet")]:
            rows.append(
                {
                    "name": f"{year}- Banco vivo  {suffix} - {fmt}",
                    "format": fmt,
                    "url": f"https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/{year}/INFLUD{yy}-{suffix}.{ext}",
                }
            )
    rows.append(
        {
            "name": "2019 a 2025- Dicionário de Dados",
            "format": "PDF",
            "url": "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/dic.pdf",
        }
    )
    return pd.DataFrame(
        rows,
        columns=[
            "resource_id",
            "name",
            "description",
            "format",
            "url",
            "size",
            "mimetype",
            "last_modified",
            "position",
        ],
    )


@pytest.fixture
def accessor(tmp_path, monkeypatch):
    acc = SRAGOpenDataSUSAccessor(cache_dir=str(tmp_path / "srag"))
    monkeypatch.setattr(
        acc._sus, "get_resources", lambda slug, use_cache=True: portal_resources()
    )
    return acc


# ---------------------------------------------------------------------------
# Metadata discovery
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_initialization(self, accessor):
        assert accessor.source_name == "srag"
        assert "Sivep-Gripe" in accessor.source_description
        assert accessor.source_url.endswith("srag-2019-a-2026")
        assert accessor.cache_dir.exists()

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert list(countries.iloc[0]) == ["BR", "Brazil"]

    def test_available_years(self, accessor):
        assert accessor.available_years() == [2023, 2024, 2026]

    def test_list_resources_excludes_docs(self, accessor):
        resources = accessor.list_resources()
        assert set(resources["format"]) == {"CSV", "PARQUET"}
        assert len(resources) == 6

    def test_resolve_url(self, accessor):
        url = accessor._resolve_url(2024)
        assert url == S3_2024_CSV
        with pytest.raises(ValueError, match="Available years"):
            accessor._resolve_url(2019)

    def test_resolve_url_parquet(self, accessor):
        url = accessor._resolve_url(2026, fmt="parquet")
        assert url.endswith(".parquet")


# ---------------------------------------------------------------------------
# Filters (unit-level, no downloads)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_df():
    df = pd.read_csv(FIXTURES / "srag_sample_2024.csv", sep=";", dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    return df


class TestFilters:
    def test_state_filter_falls_back_to_notification_state(self, accessor, sample_df):
        assert len(accessor._apply_filters(sample_df, state="rj")) == 3
        assert len(accessor._apply_filters(sample_df, state="RJ")) == 3
        assert len(accessor._apply_filters(sample_df, state="SP")) == 2

    def test_municipality_code_6_and_7_digit(self, accessor, sample_df):
        assert len(accessor._apply_filters(sample_df, municipality_code=3304557)) == 3
        assert len(accessor._apply_filters(sample_df, municipality_code="330455")) == 3
        assert len(accessor._apply_filters(sample_df, municipality_code=355030)) == 1

    def test_week_range(self, accessor, sample_df):
        assert len(accessor._apply_filters(sample_df, week_start=4, week_end=7)) == 4
        assert len(accessor._apply_filters(sample_df, week_start=9)) == 2

    @pytest.mark.parametrize(
        "pathogen,expected",
        [
            ("Influenza", 2),  # both rows with a positive flu PCR
            ("Influenza A", 1),
            ("SARS-CoV-2", 1),
            ("covid-19", 1),
            ("VSR", 2),
            ("RSV", 2),
        ],
    )
    def test_pathogen_filter(self, accessor, sample_df, pathogen, expected):
        got = accessor._apply_filters(sample_df, pathogen=pathogen)
        assert len(got) == expected

    def test_pathogen_unknown_raises(self, accessor, sample_df):
        with pytest.raises(ValueError, match="Unknown pathogen"):
            accessor._apply_filters(sample_df, pathogen="Ebola")

    def test_pathogen_missing_columns_raises(self, accessor, sample_df):
        existing = [c for c in ["PCR_SARS2", "AN_SARS2"] if c in sample_df.columns]
        trimmed = sample_df.drop(columns=existing)
        with pytest.raises(ValueError, match="No laboratory column"):
            accessor._apply_filters(trimmed, pathogen="SARS-CoV-2")

    def test_outcome_filter(self, accessor, sample_df):
        deaths = accessor._apply_filters(sample_df, outcome="death")
        cures = accessor._apply_filters(sample_df, outcome="cura")
        assert len(deaths) == 3
        assert len(cures) == 2

    def test_outcome_unknown_raises(self, accessor, sample_df):
        with pytest.raises(ValueError, match="Unknown outcome"):
            accessor._apply_filters(sample_df, outcome="teleported")

    def test_age_filters_convert_units(self, accessor, sample_df):
        # 8-year-old child and an infant (1 month ~= 0.08y)
        assert len(accessor._apply_filters(sample_df, age_max=10)) == 2
        adults = accessor._apply_filters(sample_df, age_min=18, age_max=65)
        assert len(adults) == 4
        assert len(accessor._apply_filters(sample_df, age_min=65)) == 1

    def test_missing_state_column_raises(self, accessor, sample_df):
        trimmed = sample_df.drop(
            columns=[
                c
                for c in ["SG_UF", "SG_UF_NOT", "SG_UF_INTE"]
                if c in sample_df.columns
            ]
        )
        with pytest.raises(ValueError, match="No state column"):
            accessor._apply_filters(trimmed, state="RJ")

    def test_composable_filters(self, accessor, sample_df):
        got = accessor._apply_filters(
            sample_df, state="SP", week_start=5, week_end=6, age_min=5
        )
        assert len(got) == 2
        assert set(got["CO_MUN_RES"]) == {"3550308", "3509508"}

    def test_normalize_pathogen(self):
        from epidatasets.sources.srag_opendata_sus import _normalize_pathogen

        assert _normalize_pathogen("VÍrus Sincicial") == "virus sincicial"
        assert _normalize_pathogen("  COVID-19 ") == "covid-19"


# ---------------------------------------------------------------------------
# get_year: download + chunked reading + caching
# ---------------------------------------------------------------------------


class TestGetYear:
    @responses.activate
    def test_get_year_full(self, accessor):
        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        df = accessor.get_year(2024)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 7
        # chunked with small size for coverage of iterator path
        responses.calls.reset()
        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        chunks = list(accessor.get_year(2024, chunksize=3, use_cache=False))
        assert [len(c) for c in chunks] == [3, 3, 1]

    @responses.activate
    def test_get_year_with_filters(self, accessor):
        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        df = accessor.get_year(2024, state="RJ", pathogen="Influenza")
        assert len(df) == 1
        df = accessor.get_year(
            2024, columns=["DT_NOTIFIC", "SEM_NOT", "SG_UF"], state="BA"
        )
        assert list(df.columns) == ["DT_NOTIFIC", "SEM_NOT", "SG_UF"]

    @responses.activate
    def test_latin1_encoding_fallback(self, accessor):
        responses.add(
            responses.GET,
            S3_2023_CSV,
            body=(FIXTURES / "srag_sample_2023_latin1.csv").read_bytes(),
        )
        df = accessor.get_year(2023)
        assert len(df) == 7
        assert "SÃO PAULO" in df["ID_MUNICIP"].values

    @responses.activate
    def test_frozen_year_cached_forever(self, accessor, monkeypatch):
        import os

        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        accessor.get_year(2024)
        # age the file years beyond any TTL: frozen years must still hit cache
        for f in accessor.cache_dir.glob("SRAG_*"):
            os.utime(f, (0, 0))
        accessor.get_year(2024)
        download_calls = [c for c in responses.calls if c.request.url == S3_2024_CSV]
        assert len(download_calls) == 1

    @responses.activate
    def test_live_year_respects_ttl(self, tmp_path, monkeypatch):

        acc = SRAGOpenDataSUSAccessor(
            cache_dir=str(tmp_path / "srag"), live_ttl_hours=0
        )
        monkeypatch.setattr(
            acc._sus, "get_resources", lambda slug, use_cache=True: portal_resources()
        )
        live_url = (
            portal_resources()
            .query("format == 'CSV' and name.str.startswith('2026')")
            .iloc[0]["url"]
        )
        responses.add(
            responses.GET,
            live_url,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        acc.get_year(2026)  # current year -> expires under zero TTL
        responses.calls.reset()
        responses.add(
            responses.GET,
            live_url,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        acc.get_year(2026)
        assert len(responses.calls) == 1

    @responses.activate
    def test_download_failure_wrapped(self, accessor):
        responses.add(responses.GET, S3_2024_CSV, status=500)
        with pytest.raises(SRAGDataError, match="Failed to download"):
            accessor.get_year(2024, use_cache=True)
        assert not list(accessor.cache_dir.glob("*.part"))

    def test_unknown_year(self, accessor):
        with pytest.raises(ValueError, match="No CSV resource"):
            accessor.get_year(2019)


# ---------------------------------------------------------------------------
# get_weekly_counts
# ---------------------------------------------------------------------------


class TestWeeklyCounts:
    @responses.activate
    def test_counts_by_state_with_pathogens(self, accessor):
        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        counts = accessor.get_weekly_counts(
            2024, groupby="state", pathogens=["SARS-CoV-2", "Influenza"]
        )
        assert list(counts.columns) == [
            "year",
            "epi_week",
            "SG_UF",
            "total",
            "cases_sars_cov_2",
            "cases_influenza",
        ]
        rj = counts[counts["SG_UF"] == "RJ"].sort_values("epi_week")
        assert rj["total"].tolist() == [1, 1, 1]
        assert int(rj["cases_sars_cov_2"].fillna(0).sum()) == 1
        assert int(rj["cases_influenza"].fillna(0).sum()) == 1

    @responses.activate
    def test_counts_totals_only_multiple_years(self, accessor):
        responses.add(
            responses.GET,
            S3_2024_CSV,
            body=(FIXTURES / "srag_sample_2024.csv").read_bytes(),
        )
        responses.add(
            responses.GET,
            S3_2023_CSV,
            body=(FIXTURES / "srag_sample_2023_latin1.csv").read_bytes(),
        )
        counts = accessor.get_weekly_counts([2023, 2024], groupby="state")
        assert set(counts["year"]) == {2023, 2024}
        assert counts[counts["year"] == 2024]["total"].sum() == 7
        assert "cases_influenza" not in counts.columns

    def test_counts_invalid_groupby(self, accessor):
        with pytest.raises(ValueError, match="Unknown groupby"):
            accessor.get_weekly_counts(2024, groupby="galaxy")


# ---------------------------------------------------------------------------
# IBGE municipality helpers
# ---------------------------------------------------------------------------

IBGE_PAYLOAD = [
    {
        "id": 3304557,
        "nome": "Rio de Janeiro",
        "microrregiao": {
            "mesorregiao": {"UF": {"sigla": "RJ", "nome": "Rio de Janeiro"}}
        },
    },
    {
        "id": 3550308,
        "nome": "São Paulo",
        "microrregiao": {
            "mesorregiao": {"UF": {"sigla": "SP", "nome": "São Paulo"}}
        },
    },
    {
        # regression: some entries (e.g. Brasília region) have null microrregiao
        "id": 5300108,
        "nome": "Brasília",
        "microrregiao": None,
    },
]


class TestMunicipalities:
    @responses.activate
    def test_get_municipalities(self, accessor):
        responses.add(responses.GET, IBGE_URL, json=IBGE_PAYLOAD)
        table = accessor.get_municipalities()
        assert len(table) == 3
        row = table[table["municipality_code"] == "3304557"].iloc[0]
        assert row["municipality_name"] == "Rio de Janeiro"
        assert row["state"] == "RJ"

    @responses.activate
    def test_municipality_name_and_code(self, accessor):
        responses.add(responses.GET, IBGE_URL, json=IBGE_PAYLOAD)
        assert accessor.municipality_name(3304557) == "Rio de Janeiro"
        assert accessor.municipality_name("355030") == "São Paulo"
        assert accessor.municipality_code("rio de janeiro") == "3304557"
        assert accessor.municipality_code("Sao Paulo", state="SP") == "3550308"

    @responses.activate
    def test_municipality_errors(self, accessor):
        responses.add(responses.GET, IBGE_URL, json=IBGE_PAYLOAD)
        with pytest.raises(ValueError, match="Unknown IBGE"):
            accessor.municipality_name(9999999)
        with pytest.raises(ValueError, match="Unknown municipality"):
            accessor.municipality_code("Atlantis")

    @responses.activate
    def test_municipalities_cached(self, accessor):
        responses.add(responses.GET, IBGE_URL, json=IBGE_PAYLOAD)
        accessor.get_municipalities()
        accessor.get_municipalities(state="RJ")
        assert len(responses.calls) == 1

    def test_municipality_fetch_error_wrapped(self, accessor):
        import requests as requests_lib

        with (
            mock.patch.object(
                accessor._session,
                "get",
                side_effect=requests_lib.exceptions.ConnectionError("boom"),
            ),
            pytest.raises(SRAGDataError, match="IBGE"),
        ):
            accessor.get_municipalities()


# ---------------------------------------------------------------------------
# Live integration smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.skipif(
    __import__("os").getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
    reason="External API tests disabled",
)
class TestLiveSmoke:
    def test_live_available_years(self):
        accessor = SRAGOpenDataSUSAccessor()
        years = accessor.available_years(use_cache=False)
        assert 2019 in years
        assert years == sorted(years)

    def test_live_resources_have_urls(self):
        accessor = SRAGOpenDataSUSAccessor()
        resources = accessor.list_resources(use_cache=False)
        assert not resources.empty
        assert resources["url"].str.startswith("http").all()
