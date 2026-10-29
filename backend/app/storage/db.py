"""SQLite: schemat (companies, offers, queries) + operacje CRUD."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config import settings
from ..search.languages import detect_languages_text
from ..search.normalizer import host_matches, normalize_url, url_hash
from ..search.query_builder import DEFAULT_EXCLUDED_JOBBOARDS
from ..search.textlang import detect_text_lang

STATUSES = ("nowa", "obejrzana", "aplikowano", "odrzucona")

# tytuły-wypełniacze (np. tekst "Szczegóły" z linku), które warto nadpisać lepszym tytułem
GENERIC_OFFER_TITLES = {"szczegóły", "szczegoly", "details", "więcej", "more", ""}

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    domain       TEXT    NOT NULL UNIQUE,
    name         TEXT,
    first_seen   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_query TEXT
);

CREATE TABLE IF NOT EXISTS offers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id   INTEGER NOT NULL REFERENCES companies(id),
    title        TEXT    NOT NULL DEFAULT '',
    url          TEXT    NOT NULL,
    url_hash     TEXT    NOT NULL UNIQUE,
    location     TEXT,
    salary       TEXT,
    languages    TEXT    NOT NULL DEFAULT '',
    text_lang    TEXT    NOT NULL DEFAULT 'unknown',
    source       TEXT    NOT NULL DEFAULT '',
    source_query TEXT,
    first_seen   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       TEXT    NOT NULL DEFAULT 'nowa',
    notes        TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS queries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT    NOT NULL,
    engine        TEXT    NOT NULL,
    results_count INTEGER NOT NULL DEFAULT 0,
    http_status   INTEGER,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exclusions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    domain   TEXT    NOT NULL UNIQUE,
    added_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source   TEXT    NOT NULL DEFAULT 'user'
);

CREATE INDEX IF NOT EXISTS idx_offers_status     ON offers(status);
CREATE INDEX IF NOT EXISTS idx_offers_company    ON offers(company_id);
CREATE INDEX IF NOT EXISTS idx_offers_first_seen ON offers(first_seen);
CREATE INDEX IF NOT EXISTS idx_queries_engine    ON queries(engine, created_at);
"""

_conn: sqlite3.Connection | None = None


def init_db(path: Path | None = None) -> None:
    """Otwiera (tworząc przy okazji) bazę SQLite i zakłada schemat."""
    global _conn
    target = Path(path or settings.db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    # domyślne wykluczenia (jobboardy + agregatory) — raz zasiane do bazy,
    # dalej użytkownik może je usuwać/dodawać
    seed = [(domain,) for domain in DEFAULT_EXCLUDED_JOBBOARDS]
    conn.executemany("INSERT OR IGNORE INTO exclusions (domain, source) VALUES (?, 'default')", seed)
    _backfill_languages(conn)
    _backfill_text_lang(conn)
    conn.commit()
    _conn = conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Lekka migracja: dodaje brakujące kolumny do istniejącej bazy."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(offers)")}
    if "languages" not in columns:
        conn.execute("ALTER TABLE offers ADD COLUMN languages TEXT NOT NULL DEFAULT ''")
    if "text_lang" not in columns:
        conn.execute("ALTER TABLE offers ADD COLUMN text_lang TEXT NOT NULL DEFAULT 'unknown'")


def _backfill_languages(conn: sqlite3.Connection) -> None:
    """Retroaktywnie rozpoznaje języki w starych ofertach (z tytułu — stąd
    mniejsza pewność, ale filtr działa od razu na całej historycznej liście)."""
    rows = conn.execute("SELECT id, title FROM offers WHERE languages = ''").fetchall()
    for row in rows:
        detected = detect_languages_text(row["title"])
        if detected:
            conn.execute("UPDATE offers SET languages = ? WHERE id = ?", (detected, row["id"]))


def _backfill_text_lang(conn: sqlite3.Connection) -> None:
    """Retroaktywnie: język treści z tytułu + zapytania źródłowego (frazy PL!)."""
    rows = conn.execute(
        "SELECT id, title, source_query FROM offers WHERE text_lang = 'unknown'"
    ).fetchall()
    for row in rows:
        detected = detect_text_lang(row["title"])
        if detected == "unknown":
            detected = detect_text_lang(f"{row['title']} {row['source_query']}")
        if detected != "unknown":
            conn.execute(
                "UPDATE offers SET text_lang = ? WHERE id = ?", (detected, row["id"])
            )


def get_conn() -> sqlite3.Connection:
    if _conn is None:
        init_db()
    assert _conn is not None
    return _conn


def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def upsert_company(
    conn: sqlite3.Connection,
    domain: str,
    name: str | None = None,
    source_query: str | None = None,
) -> int:
    row = conn.execute("SELECT id FROM companies WHERE domain = ?", (domain,)).fetchone()
    if row is not None:
        conn.execute(
            "UPDATE companies SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],)
        )
        conn.commit()
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO companies (domain, name, source_query) VALUES (?, ?, ?)",
        (domain, name, source_query),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_company(conn: sqlite3.Connection, company_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    return _to_dict(row) if row else None


def upsert_offer(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    url: str,
    title: str = "",
    location: str | None = "",
    salary: str | None = "",
    languages: str = "",
    text_lang: str = "unknown",
    source: str = "",
    source_query: str | None = None,
) -> tuple[int, bool]:
    """Dodaje ofertę lub odświeża last_seen istniejącej (dedupe po url_hash).
    Zwraca (id, czy_nowa)."""
    url_n = normalize_url(url)
    h = url_hash(url_n)
    row = conn.execute("SELECT id, title FROM offers WHERE url_hash = ?", (h,)).fetchone()
    if row is not None:
        # przy okazji podbij tytuł, jeśli dotychczasowy był generycznym placeholderem
        if title.strip() and row["title"].strip().lower() in GENERIC_OFFER_TITLES:
            conn.execute(
                "UPDATE offers SET title = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (title.strip(), row["id"]),
            )
        else:
            conn.execute(
                "UPDATE offers SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],)
            )
        conn.commit()
        return int(row["id"]), False
    cur = conn.execute(
        """INSERT INTO offers
               (company_id, title, url, url_hash, location, salary, languages, text_lang,
                source, source_query, status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nowa', '')""",
        (company_id, title, url_n, h, location, salary, languages, text_lang, source, source_query),
    )
    conn.commit()
    return int(cur.lastrowid), True


_OFFER_SELECT = """SELECT o.id, o.company_id, o.title, o.url, o.location, o.salary,
       o.languages, o.text_lang, o.source, o.source_query, o.first_seen, o.last_seen,
       o.status, o.notes, c.domain AS company_domain
FROM offers o JOIN companies c ON c.id = o.company_id"""


def _offer_where(
    status: str | None,
    q: str | None,
    source: str | None,
    company: str | None,
    language: str | None = None,
    text_lang: str | None = None,
) -> tuple[str, list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    if status in STATUSES:
        where.append("o.status = ?")
        params.append(status)
    if q:
        like = f"%{q.strip()}%"
        where.append("(o.title LIKE ? OR o.url LIKE ? OR c.domain LIKE ?)")
        params += [like, like, like]
    if source:
        where.append("o.source = ?")
        params.append(source)
    if company:
        where.append("c.domain LIKE ?")
        params.append(f"%{company.strip()}%")
    if language:
        where.append("o.languages LIKE ?")
        params.append(f"%{language.strip()}%")
    if text_lang:
        where.append("o.text_lang = ?")
        params.append(text_lang.strip())
    suffix = " WHERE " + " AND ".join(where) if where else ""
    return suffix, params


def list_offers(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    q: str | None = None,
    source: str | None = None,
    company: str | None = None,
    language: str | None = None,
    text_lang: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    suffix, params = _offer_where(status, q, source, company, language, text_lang)
    total = conn.execute(
        "SELECT COUNT(*) FROM offers o JOIN companies c ON c.id = o.company_id" + suffix, params
    ).fetchone()[0]
    rows = conn.execute(
        _OFFER_SELECT + suffix + " ORDER BY o.first_seen DESC, o.id DESC LIMIT ? OFFSET ?",
        [*params, int(limit), int(offset)],
    ).fetchall()
    return [_to_dict(row) for row in rows], int(total)


def get_offer(conn: sqlite3.Connection, offer_id: int) -> dict[str, Any] | None:
    row = conn.execute(_OFFER_SELECT + " WHERE o.id = ?", (offer_id,)).fetchone()
    return _to_dict(row) if row else None


def update_offer(
    conn: sqlite3.Connection,
    offer_id: int,
    *,
    status: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    sets: list[str] = []
    params: list[Any] = []
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"Nieznany status: '{status}' (dozwolone: {', '.join(STATUSES)})")
        sets.append("status = ?")
        params.append(status)
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    if sets:
        conn.execute(f"UPDATE offers SET {', '.join(sets)} WHERE id = ?", [*params, offer_id])
        conn.commit()
    return get_offer(conn, offer_id)


def list_companies(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT c.id, c.domain, c.name, c.first_seen, c.last_seen,
                  COUNT(o.id) AS offers_count,
                  COALESCE(SUM(CASE WHEN o.status = 'nowa' THEN 1 ELSE 0 END), 0) AS new_count
           FROM companies c LEFT JOIN offers o ON o.company_id = c.id
           GROUP BY c.id
           ORDER BY c.last_seen DESC, c.domain"""
    ).fetchall()
    return [_to_dict(row) for row in rows]


def companies_missing_offers(conn: sqlite3.Connection, limit: int = 2) -> list[dict[str, Any]]:
    """Firmy, które mają mało ofert (doładowane tylko "stroną kariery" z wyszukiwania)
    — kandydaci do auto-crawl strony kariery."""
    rows = conn.execute(
        """SELECT c.id, c.domain FROM companies c
           WHERE (SELECT COUNT(*) FROM offers o WHERE o.company_id = c.id) < 3
           ORDER BY c.last_seen DESC LIMIT ?""",
        (int(limit),),
    ).fetchall()
    return [_to_dict(row) for row in rows]


def log_query(
    conn: sqlite3.Connection,
    *,
    query: str,
    engine: str,
    results_count: int,
    http_status: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO queries (query, engine, results_count, http_status) VALUES (?, ?, ?, ?)",
        (query, engine, results_count, http_status),
    )
    conn.commit()


def queries_today(
    conn: sqlite3.Connection, engine: str | None = None, success_only: bool = False
) -> int:
    sql = "SELECT COUNT(*) FROM queries WHERE date(created_at) = date('now')"
    params: list[Any] = []
    if engine:
        sql += " AND engine = ?"
        params.append(engine)
    if success_only:
        sql += " AND http_status = 200"
    return int(conn.execute(sql, params).fetchone()[0])


def recent_queries(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM queries ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [_to_dict(row) for row in rows]


def existing_url_hashes(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT url_hash FROM offers")}


def all_offers_for_export(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(_OFFER_SELECT + " ORDER BY c.domain, o.id").fetchall()
    return [_to_dict(row) for row in rows]


def prune_excluded_offers(conn: sqlite3.Connection, exclude_domains: list[str]) -> int:
    """Usuwa oferty (i firmy) z domen wpisanych na listę wykluczeń — np. gdy ktoś
    dodał nowy jobboard/agregator, a starsza sesja zdążyła już zainportować
    jego wpisy. Zwraca liczbę usuniętych ofert."""
    if not exclude_domains:
        return 0
    rows = conn.execute("SELECT id, domain FROM companies").fetchall()
    doomed = [
        int(row["id"])
        for row in rows
        if any(host_matches(row["domain"].lower(), excl) for excl in exclude_domains)
    ]
    deleted = 0
    for company_id in doomed:
        cursor = conn.execute("DELETE FROM offers WHERE company_id = ?", (company_id,))
        deleted += int(cursor.rowcount)
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    return deleted


def delete_offer(conn: sqlite3.Connection, offer_id: int) -> bool:
    """Usuwa pojedynczą ofertę; jeśli to była jej ostatnia — sprząta firmę."""
    offer = get_offer(conn, offer_id)
    if offer is None:
        return False
    conn.execute("DELETE FROM offers WHERE id = ?", (offer_id,))
    left = conn.execute(
        "SELECT COUNT(*) FROM offers WHERE company_id = ?", (offer["company_id"],)
    ).fetchone()[0]
    if int(left) == 0:
        conn.execute("DELETE FROM companies WHERE id = ?", (offer["company_id"],))
    conn.commit()
    return True


def list_exclusions(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT domain FROM exclusions ORDER BY domain")]


def add_exclusion(conn: sqlite3.Connection, domain: str, source: str = "user") -> bool:
    """Dodaje domenę (znormalizowaną); False, gdy już istniała."""
    existed = conn.execute("SELECT 1 FROM exclusions WHERE domain = ?", (domain,)).fetchone()
    if existed is not None:
        return False
    conn.execute("INSERT INTO exclusions (domain, source) VALUES (?, ?)", (domain, source))
    conn.commit()
    return True


def delete_exclusion(conn: sqlite3.Connection, domain: str) -> bool:
    cursor = conn.execute("DELETE FROM exclusions WHERE domain = ?", (domain,))
    conn.commit()
    return int(cursor.rowcount) > 0