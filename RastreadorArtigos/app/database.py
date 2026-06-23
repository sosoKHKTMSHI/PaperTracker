from __future__ import annotations

from pathlib import Path
import json
import re
import sqlite3
import threading
from typing import Iterable

from .models import Article, now_iso


ARTICLE_COLUMNS = [
    "id", "authors", "authors_main", "first_author", "short_name", "year", "title", "journal",
    "doi", "pmid", "pmcid", "openalex_id", "abstract", "abstract_status", "abstract_source",
    "oa_status", "landing_url", "pdf_url", "xml_url", "json_url", "license", "source", "status",
    "downloaded", "pdf_check_status", "pdf_check_message", "pdf_checked_at", "pdf_downloaded",
    "pdf_download_error", "field_sources", "manual_fields", "conflicts", "created_at", "updated_at",
]


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._create()
        self._migrate()

    def _create(self) -> None:
        with self.lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    authors TEXT NOT NULL DEFAULT '', authors_main TEXT NOT NULL DEFAULT '',
                    first_author TEXT NOT NULL DEFAULT '', short_name TEXT NOT NULL DEFAULT '',
                    year TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', journal TEXT NOT NULL DEFAULT '',
                    doi TEXT NOT NULL DEFAULT '', pmid TEXT NOT NULL DEFAULT '', pmcid TEXT NOT NULL DEFAULT '',
                    openalex_id TEXT NOT NULL DEFAULT '', abstract TEXT NOT NULL DEFAULT '',
                    abstract_status TEXT NOT NULL DEFAULT 'Não', abstract_source TEXT NOT NULL DEFAULT '',
                    oa_status TEXT NOT NULL DEFAULT 'Não consultado', landing_url TEXT NOT NULL DEFAULT '',
                    pdf_url TEXT NOT NULL DEFAULT '', xml_url TEXT NOT NULL DEFAULT '', json_url TEXT NOT NULL DEFAULT '',
                    license TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Importado',
                    downloaded INTEGER NOT NULL DEFAULT 0,
                    pdf_check_status TEXT NOT NULL DEFAULT 'Não verificado',
                    pdf_check_message TEXT NOT NULL DEFAULT '', pdf_checked_at TEXT NOT NULL DEFAULT '',
                    pdf_downloaded INTEGER NOT NULL DEFAULT 0, pdf_download_error TEXT NOT NULL DEFAULT '',
                    field_sources TEXT NOT NULL DEFAULT '{}', manual_fields TEXT NOT NULL DEFAULT '[]',
                    conflicts TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
                CREATE INDEX IF NOT EXISTS idx_articles_pmid ON articles(pmid);
                CREATE INDEX IF NOT EXISTS idx_articles_pmcid ON articles(pmcid);
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                    article_id TEXT NOT NULL DEFAULT '', service TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT 'INFO', message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deleted_articles (
                    deleted_id INTEGER PRIMARY KEY AUTOINCREMENT, original_id TEXT NOT NULL,
                    payload TEXT NOT NULL, deleted_at TEXT NOT NULL
                );
                """
            )
            self.conn.commit()

    def _migrate(self) -> None:
        definitions = {
            "pdf_check_status": "TEXT NOT NULL DEFAULT 'Não verificado'",
            "pdf_check_message": "TEXT NOT NULL DEFAULT ''",
            "pdf_checked_at": "TEXT NOT NULL DEFAULT ''",
            "pdf_downloaded": "INTEGER NOT NULL DEFAULT 0",
            "pdf_download_error": "TEXT NOT NULL DEFAULT ''",
        }
        with self.lock:
            current = {row[1] for row in self.conn.execute("PRAGMA table_info(articles)")}
            for column, definition in definitions.items():
                if column not in current:
                    self.conn.execute(f"ALTER TABLE articles ADD COLUMN {column} {definition}")
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def list_articles(self) -> list[Article]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM articles").fetchall()
        return sorted((Article.from_db(dict(row)) for row in rows), key=lambda a: self.id_number(a.id))

    def get(self, article_id: str) -> Article | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        return Article.from_db(dict(row)) if row else None

    def save(self, article: Article) -> Article:
        article.normalize()
        data = article.to_db()
        placeholders = ",".join("?" for _ in ARTICLE_COLUMNS)
        updates = ",".join(f"{column}=excluded.{column}" for column in ARTICLE_COLUMNS if column != "id")
        values = [data[column] for column in ARTICLE_COLUMNS]
        with self.lock:
            self.conn.execute(
                f"INSERT INTO articles ({','.join(ARTICLE_COLUMNS)}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}", values,
            )
            self.conn.commit()
        return article

    def save_many(self, articles: Iterable[Article]) -> None:
        for article in articles:
            self.save(article)

    def delete(self, article_id: str) -> Article | None:
        article = self.get(article_id)
        if not article:
            return None
        with self.lock:
            self.conn.execute(
                "INSERT INTO deleted_articles(original_id,payload,deleted_at) VALUES(?,?,?)",
                (article.id, json.dumps(article.to_db(), ensure_ascii=False), now_iso()),
            )
            self.conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            self.conn.commit()
        return article

    def undo_delete(self) -> Article | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT deleted_id, original_id, payload FROM deleted_articles ORDER BY deleted_id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["field_sources"] = json.loads(payload.get("field_sources") or "{}")
        payload["manual_fields"] = set(json.loads(payload.get("manual_fields") or "[]"))
        payload["conflicts"] = json.loads(payload.get("conflicts") or "{}")
        article = Article(**{k: v for k, v in payload.items() if k in Article.__dataclass_fields__})
        if self.get(article.id):
            article.id = self.next_id()
        self.save(article)
        with self.lock:
            self.conn.execute("DELETE FROM deleted_articles WHERE deleted_id = ?", (row["deleted_id"],))
            self.conn.commit()
        return article

    @staticmethod
    def id_number(article_id: str) -> int:
        match = re.search(r"(\d+)$", article_id or "")
        return int(match.group(1)) if match else 10**9

    def next_id(self) -> str:
        with self.lock:
            rows = self.conn.execute("SELECT id FROM articles").fetchall()
        used = {self.id_number(row[0]) for row in rows}
        number = 1
        while number in used:
            number += 1
        return f"ART{number:03d}"

    def renumber(self) -> None:
        articles = self.list_articles()
        with self.lock:
            self.conn.execute("DELETE FROM articles")
            self.conn.commit()
        for index, article in enumerate(articles, 1):
            article.id = f"ART{index:03d}"
            self.save(article)

    def find_exact(self, article: Article) -> Article | None:
        with self.lock:
            for field in ("doi", "pmid", "pmcid"):
                value = getattr(article, field)
                if value:
                    row = self.conn.execute(f"SELECT * FROM articles WHERE {field} = ? LIMIT 1", (value,)).fetchone()
                    if row:
                        return Article.from_db(dict(row))
        return None

    def find_by_title_year(self, normalized_title: str, year: str) -> Article | None:
        if not normalized_title:
            return None
        from .models import normalize_title
        for article in self.list_articles():
            if normalize_title(article.title) == normalized_title and (not year or article.year == year):
                return article
        return None

    def log(self, article_id: str, service: str, message: str, level: str = "INFO") -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO logs(timestamp,article_id,service,level,message) VALUES(?,?,?,?,?)",
                (now_iso(), article_id, service, level, message),
            )
            self.conn.commit()

    def logs(self, limit: int | None = None) -> list[dict[str, str]]:
        sql = "SELECT timestamp,article_id,service,level,message FROM logs ORDER BY id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self.lock:
            return [dict(row) for row in self.conn.execute(sql)]

    def clear_logs(self) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM logs")
            self.conn.commit()

    def reset_project(self) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM articles")
            self.conn.execute("DELETE FROM logs")
            self.conn.execute("DELETE FROM deleted_articles")
            self.conn.commit()
