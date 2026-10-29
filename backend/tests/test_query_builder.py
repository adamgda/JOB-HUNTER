from app.search.query_builder import (
    DEFAULT_EXCLUDED_JOBBOARDS,
    build_exclusions,
    build_queries,
    collect_excluded,
)


def test_queries_contain_exclusions():
    queries = build_queries(["React"], tld="pl", max_queries=4)
    assert len(queries) == 4
    assert all("-site:linkedin.com" in query for query in queries)


def test_templates_rotate_in_order():
    queries = build_queries(["React"], tld="pl", max_queries=8)
    assert queries[0].startswith("site:pl ")
    assert queries[1].startswith("(inurl:kariera")
    assert queries[2].startswith("intitle:(kariera")
    assert '"dołącz do nas"' in queries[3]


def test_no_tld_skips_site_template():
    queries = build_queries(["React"], tld=None, max_queries=10)
    assert all(not query.startswith("site:pl") for query in queries)
    assert len(queries) == 7  # t1..t6 + basic t12 "(careers OR jobs)" (t0/t8-t11 wymagają TLD)


def test_new_hiring_phrase_templates():
    queries = build_queries(["React"], tld="pl", max_queries=10)
    assert any('"zatrudnimy"' in q for q in queries)          # t4 (PL)
    assert any('"we are hiring"' in q for q in queries)       # t5 (EN)
    assert any("vacancies" in q or "oferty-pracy" in q for q in queries)  # t6


def test_engine_call_timeout_is_hard(monkeypatch):
    """Zawiśnięte wywołanie silnika nie może zawiesić całego wyszukiwania."""
    import time as _time

    from app.search import service

    def slow_engine(query, *, limit, date_restrict=None):
        _time.sleep(2.0)
        return []

    monkeypatch.setattr(service, "ENGINE_CALL_TIMEOUT", 0.3)
    results, error = service._engine_call(slow_engine, "test", limit=1, date_restrict=None)
    assert results == []
    assert error is not None and "Przekroczono" in error


def test_basic_mode_for_ddgs_engines():
    """DuckDuckGo/Bing/Yahoo ignorują inurl:/intitle: — tryb basic ich nie używa."""
    queries = build_queries(
        ["React"], tld="pl", cities=["Kraków"], max_queries=30, google_style=False
    )
    assert queries
    assert not any("inurl:" in q for q in queries)
    assert not any("intitle:" in q for q in queries)
    assert any("site:pl" in q for q in queries)
    assert any('"dołącz do nas"' in q for q in queries)


def test_exclusions_separated_by_space():
    queries = build_queries(["React"], tld="pl", max_queries=4)
    assert any(" React -site:linkedin.com" in q for q in queries)


def test_cities_template():
    queries = build_queries(["QA"], tld="pl", cities=["Kraków"], max_queries=10)
    assert any('"Kraków"' in q and "inurl:kariera" in q for q in queries)


def test_keywords_deduplicated_case_insensitive():
    queries_one = build_queries(["React developer"], tld="pl", max_queries=100)
    queries_two = build_queries(["react developer", "React Developer"], tld="pl", max_queries=100)
    assert len(queries_one) == len(queries_two)


def test_exclusions_merge_defaults_without_duplicates():
    merged = collect_excluded(["linkedin.com", "mójjobboard.pl"])
    assert merged.count("linkedin.com") == 1
    assert "mójjobboard.pl" in merged
    assert DEFAULT_EXCLUDED_JOBBOARDS[0] in build_exclusions()