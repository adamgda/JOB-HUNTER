from app.search.normalizer import extract_domain, is_excluded, normalize_url, url_hash


def test_normalize_removes_tracking_and_fragment():
    url = "https://Www.Firma.pl/kariera/?utm_source=x&fbclid=y#top"
    assert normalize_url(url) == "https://firma.pl/kariera"


def test_normalize_keeps_meaningful_query_and_sorts_params():
    assert normalize_url("http://example.com/jobs/?id=7&b=2") == "http://example.com/jobs?b=2&id=7"


def test_normalize_keeps_root_slash():
    assert normalize_url("https://firma.pl/") == "https://firma.pl/"


def test_url_hash_ignores_tracking_and_www():
    a = "https://firma.pl/kariera/oferta"
    b = "https://www.firma.pl/kariera/oferta?utm_campaign=x&ref=y#kwoty"
    assert url_hash(a) == url_hash(b)


def test_extract_domain():
    assert extract_domain("https://jobs.Firma.pl:8080/careers") == "jobs.firma.pl"
    assert extract_domain("https://www.firma.pl/x") == "firma.pl"


def test_is_excluded_matches_subdomains_only():
    domains = ["pracuj.pl"]
    assert is_excluded("https://m.pracuj.pl/oferta", domains) is True
    assert is_excluded("https://pracuj.pl.evil.com/oferta", domains) is False
    assert is_excluded("https://firma.pl/oferta", domains) is False