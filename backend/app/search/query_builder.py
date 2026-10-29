"""Generator puli zapytań (szablony × słowa kluczowe × TLD × miasta × wykluczenia)."""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_EXCLUDED_JOBBOARDS = [
    "linkedin.com",
    "pracuj.pl",
    "justjoin.it",
    "rocketjobs.pl",
    "nofluffjobs.com",
    "theprotocol.it",
    "bulldogjob.pl",
    "praca.pl",
    "4programmers.net",
    "indeed.com",
    "glassdoor.com",
    # agregatory rynków "job-aggregator" — nie to firma, nie oferta pracodawcy:
    "upwork.com",
    "toptal.com",
    "turing.com",
    "simplyhired.com",
    "jooble.org",
    "geeksforgeeks.org",
    "pythonjobshq.com",
    "remotepython.com",
    "remote.co",
    "wehireanywhere.com",
    "arc.dev",
    "builtin.com",
]

CAREER_PHRASES = '"dołącz do nas" OR "pracuj z nami" OR "otwieramy rekrutację"'
HIRING_PL = '"zatrudnimy" OR "poszukujemy do zespołu" OR "szukamy do zespołu" OR "wzmacniamy zespół"'
HIRING_EN = '"join our team" OR "we are hiring" OR "open positions" OR "open roles"'


@dataclass(frozen=True)
class TemplateSpec:
    """Szablon zapytania + warunki użycia.

    needs_tld/needs_city — szablon wymaga filtra TLD / nazwy miasta,
    google_only — operator `inurl:`/`intitle:` rozumie tylko Google
    (DuckDuckGo/Bing/Yahoo je ignorują i psują trafność).
    """

    text: str
    needs_tld: bool = False
    needs_city: bool = False
    google_only: bool = False


# Kolejność ma znaczenie: kolejka rotuje round-robin po szablonach, więc
# pula zapytań jest mieszana pod względem typu operatorów.
TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec("site:{tld} (kariera OR careers OR jobs) {kw}", needs_tld=True),  # t0
    TemplateSpec("(inurl:kariera OR inurl:career OR inurl:careers OR inurl:jobs) {kw}", google_only=True),
    TemplateSpec("intitle:(kariera OR careers OR jobs OR praca) {kw}", google_only=True),
    TemplateSpec(f"({CAREER_PHRASES}) {{kw}}"),
    TemplateSpec(f"({HIRING_PL}) {{kw}}"),
    TemplateSpec(f"({HIRING_EN}) {{kw}}"),
    TemplateSpec("inurl:(oferty-pracy OR oferty_pracy OR vacancies OR vacancy OR openings OR join-us) {kw}", google_only=True),
    TemplateSpec('inurl:kariera "{city}" {kw}', needs_city=True, google_only=True),
    # warianty "basic" dla silników ddgs (site + frazy, bez operatorów Google):
    TemplateSpec("kariera {kw} site:{tld}", needs_tld=True),
    TemplateSpec("(careers OR kariera) {kw} site:{tld}", needs_tld=True),
    TemplateSpec(f"({HIRING_PL}) {{kw}} site:{{tld}}", needs_tld=True),
    TemplateSpec('"we are hiring" {kw} site:{tld}', needs_tld=True),
    TemplateSpec("(careers OR jobs) {kw}"),
    TemplateSpec('kariera "{city}" {kw}', needs_city=True),
)


def collect_excluded(extra: list[str] | None = None) -> list[str]:
    """Domyślne jobboardy + nadpisania użytkownika, bez duplikatów, w kolejności."""
    extra = [d.strip().lower() for d in (extra or []) if d and d.strip()]
    return list(dict.fromkeys(DEFAULT_EXCLUDED_JOBBOARDS + extra))


def build_exclusions(extra: list[str] | None = None) -> str:
    return " ".join(f"-site:{domain}" for domain in collect_excluded(extra))


def _join(base_text: str, suffix: str) -> str:
    text = f"{base_text.strip()} {suffix.strip()}".replace("  ", " ")
    return text.strip()


def _clean_keywords(keywords: list[str]) -> list[str]:
    cleaned = [k.strip() for k in (keywords or []) if k and str(k).strip()]
    seen: set[str] = set()
    unique = []
    for keyword in cleaned:
        key = keyword.lower()
        if key not in seen:
            seen.add(key)
            unique.append(keyword)
    return unique


def build_queries(
    keywords: list[str],
    *,
    tld: str | None = "pl",
    cities: list[str] | None = None,
    excluded: list[str] | None = None,
    max_queries: int = 8,
    google_style: bool = True,
) -> list[str]:
    """Buduje pulę zapytań. Szablony rotują round-robin, żeby kolejne zapytania
    pokrywały różne typy operatorów, a nie wiele wariantów jednej techniki.

    google_style=True  → pełne operatory (inurl:/intitle:) — tylko Google,
    google_style=False → wyłącznie site: + frazy — dla DuckDuckGo/Bing/Yahoo/Brave.
    """
    prepared = _clean_keywords(keywords)
    if not prepared:
        return []
    max_queries = max(int(max_queries), 1)
    exclusions = build_exclusions(excluded)
    city_list = [c.strip() for c in (cities or []) if c and c.strip()]
    excluded = list(dict.fromkeys([(d.strip().lower()) for d in (excluded or [])]))

    buckets: list[list[str]] = []
    for spec in TEMPLATES:
        if spec.google_only and not google_style:
            continue
        if spec.needs_tld and not tld:
            continue
        if spec.needs_city and not city_list:
            continue
        bucket: list[str] = []
        for kw in prepared:
            if spec.needs_city:
                for city in city_list:
                    bucket.append(_join(spec.text.format(tld=tld, city=city, kw=kw), exclusions))
            else:
                bucket.append(_join(spec.text.format(tld=tld, kw=kw), exclusions))
        buckets.append(bucket)

    queries: list[str] = []
    template_index = 0
    while len(queries) < max_queries and any(buckets):
        bucket = buckets[template_index % len(buckets)]
        if bucket:
            queries.append(bucket.pop(0))
        template_index += 1
    return queries[:max_queries]