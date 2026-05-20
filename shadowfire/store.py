"""
Persistent storage for crawl results and stress test runs.
DuckDB file at data/shadowfire.db — analytical queries, no server needed.
"""
import json
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "shadowfire.db"


def _conn() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init():
    """Create tables and apply any pending migrations. Safe to call repeatedly."""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id          VARCHAR PRIMARY KEY,
                started_at  TIMESTAMP,
                ended_at    TIMESTAMP,
                config      JSON
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id                  VARCHAR PRIMARY KEY,
                run_id              VARCHAR,
                url                 VARCHAR,
                status_code         INTEGER,
                fetch_ms            INTEGER,
                html_bytes          INTEGER,
                markdown_chars      INTEGER,
                link_count          INTEGER,
                image_count         INTEGER,
                title               VARCHAR,
                error               VARCHAR,
                injection_detected  BOOLEAN,
                injection_score     FLOAT,
                invisible_text      BOOLEAN,
                scraped_at          TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                url       VARCHAR PRIMARY KEY,
                name      VARCHAR,
                category  VARCHAR,
                added_at  TIMESTAMP DEFAULT current_timestamp
            )
        """)
        # Additive migrations — safe to re-run
        for col, dtype in [
            ("circuit_id",        "VARCHAR"),
            ("exit_fingerprint",  "VARCHAR"),
            ("exit_nickname",     "VARCHAR"),
            ("content_type",      "VARCHAR"),
            ("page_type",         "VARCHAR"),
            ("language",          "VARCHAR"),
        ]:
            try:
                con.execute(f"ALTER TABLE pages ADD COLUMN {col} {dtype}")
            except Exception:
                pass  # column already exists


def upsert_source(url: str, name: str, category: str):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO sources (url, name, category) VALUES (?, ?, ?)",
            [url, name, category],
        )


def get_sources(categories: list[str] | None = None) -> list[dict]:
    with _conn() as con:
        if categories:
            placeholders = ", ".join("?" * len(categories))
            rows = con.execute(
                f"SELECT url, name, category FROM sources WHERE category IN ({placeholders})",
                categories,
            ).fetchall()
        else:
            rows = con.execute("SELECT url, name, category FROM sources").fetchall()
    return [{"url": r[0], "name": r[1], "category": r[2]} for r in rows]


def insert_run(id: str, started_at, ended_at, config: dict):
    with _conn() as con:
        con.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?)",
            [id, started_at, ended_at, json.dumps(config)],
        )


def insert_page(
    id: str, run_id: str, url: str, status_code: int,
    fetch_ms: int, html_bytes: int, markdown_chars: int,
    link_count: int, image_count: int, title: str | None,
    error: str | None, injection_detected: bool,
    injection_score: float, invisible_text: bool, scraped_at,
    circuit_id: str | None = None,
    exit_fingerprint: str | None = None,
    exit_nickname: str | None = None,
    content_type: str | None = None,
    page_type: str | None = None,
    language: str | None = None,
):
    with _conn() as con:
        con.execute(
            """INSERT INTO pages VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            [id, run_id, url, status_code, fetch_ms, html_bytes,
             markdown_chars, link_count, image_count, title, error,
             injection_detected, injection_score, invisible_text, scraped_at,
             circuit_id, exit_fingerprint, exit_nickname, content_type,
             page_type, language],
        )
