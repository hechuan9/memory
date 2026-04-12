from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from codex_memory.retain import validate_retain_content


SCHEMA_VERSION = 1
ACTIVE_STATUSES = ("active",)
ACTIVE_WITH_CANDIDATES = ("active", "candidate")


@dataclass(frozen=True)
class MemoryItem:
    id: str
    bank_id: str
    repo: str | None
    kind: str
    status: str
    source_path: str | None
    source_anchor: str | None
    content: str
    evidence: str
    tags_json: str
    score: float


class MemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    bank_id TEXT NOT NULL,
                    repo TEXT,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_path TEXT,
                    source_anchor TEXT,
                    content TEXT NOT NULL,
                    evidence TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
                    content,
                    evidence,
                    tags
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    repo TEXT,
                    cwd TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert_item(
        self,
        *,
        bank_id: str,
        kind: str,
        status: str,
        content: str,
        repo: str | None = None,
        source_path: str | None = None,
        source_anchor: str | None = None,
        evidence: str = "",
        tags: Sequence[str] | None = None,
    ) -> str:
        content = content.strip()
        evidence = (evidence or "").strip()
        tags_json = json.dumps(list(tags or []), ensure_ascii=False)
        content_hash = _hash_parts(bank_id, kind, content, source_path or "", source_anchor or "")
        now = _now()
        item_id = f"mem_{content_hash[:16]}"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM memory_items WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE memory_items
                    SET status = ?, evidence = ?, tags_json = ?, updated_at = ?
                    WHERE content_hash = ?
                    """,
                    (status, evidence, tags_json, now, content_hash),
                )
                self._sync_fts(connection, existing["id"])
                return str(existing["id"])
            connection.execute(
                """
                INSERT INTO memory_items (
                    id, bank_id, repo, kind, status, source_path, source_anchor,
                    content, evidence, tags_json, content_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    bank_id,
                    repo,
                    kind,
                    status,
                    source_path,
                    source_anchor,
                    content,
                    evidence,
                    tags_json,
                    content_hash,
                    now,
                    now,
                ),
            )
            self._sync_fts(connection, item_id)
        return item_id

    def _sync_fts(self, connection: sqlite3.Connection, item_id: str) -> None:
        row = connection.execute(
            "SELECT rowid, content, evidence, tags_json FROM memory_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if not row:
            return
        connection.execute("DELETE FROM memory_items_fts WHERE rowid = ?", (row["rowid"],))
        connection.execute(
            "INSERT INTO memory_items_fts(rowid, content, evidence, tags) VALUES (?, ?, ?, ?)",
            (row["rowid"], row["content"], row["evidence"], row["tags_json"]),
        )

    def recall(
        self,
        query: str,
        *,
        repo: str | None = None,
        limit: int = 12,
        include_candidates: bool = False,
        max_chars: int = 4000,
        max_session_events: int = 3,
    ) -> list[MemoryItem]:
        statuses = ACTIVE_WITH_CANDIDATES if include_candidates else ACTIVE_STATUSES
        banks = ["global"]
        if repo:
            banks.insert(0, f"repo:{repo}")
        fts_query = _fts_query(query)
        if not fts_query:
            return []
        placeholders = ",".join("?" for _ in banks)
        status_placeholders = ",".join("?" for _ in statuses)
        params: list[object] = [fts_query, *banks, *statuses, limit * 4]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT m.*, bm25(memory_items_fts) AS rank
                FROM memory_items_fts
                JOIN memory_items m ON m.rowid = memory_items_fts.rowid
                WHERE memory_items_fts MATCH ?
                  AND m.bank_id IN ({placeholders})
                  AND m.status IN ({status_placeholders})
                ORDER BY
                  CASE WHEN m.bank_id = ? THEN 0 WHEN m.bank_id = 'global' THEN 1 ELSE 2 END,
                  CASE WHEN m.kind = 'session_event' THEN 1 WHEN m.status = 'candidate' THEN 2 ELSE 0 END,
                  rank
                LIMIT ?
                """,
                [*params[:-1], f"repo:{repo}" if repo else "global", params[-1]],
            ).fetchall()
        return _dedupe_and_trim(
            [item for item in _row_to_item_sequence(rows, max_session_events=max_session_events)],
            limit=limit,
            max_chars=max_chars,
        )

    def retain_session(
        self,
        *,
        repo: str | None,
        cwd: str | None,
        summary: str,
        events: Iterable[dict],
        candidates: Iterable[dict],
        tags: Sequence[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        session_id = session_id or f"session_{uuid.uuid4().hex}"
        now = _now()
        session_tags = list(tags or ([] if not repo else [f"repo:{repo}"]))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sessions
                    (id, repo, cwd, started_at, ended_at, summary, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, repo, cwd, now, now, summary.strip(), json.dumps(session_tags, ensure_ascii=False)),
            )
            connection.execute("DELETE FROM session_events WHERE session_id = ?", (session_id,))
            for event in events:
                content = str(event.get("content", "")).strip()
                if not content:
                    continue
                connection.execute(
                    """
                    INSERT INTO session_events(session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, str(event.get("role", "unknown")), content, now),
                )
        for event in events:
            content = str(event.get("content", "")).strip()
            if not content:
                continue
            self.upsert_item(
                bank_id=f"repo:{repo}" if repo else "global",
                repo=repo,
                kind="session_event",
                status="active",
                content=content,
                evidence=summary,
                source_anchor=session_id,
                tags=[*session_tags, f"role:{event.get('role', 'unknown')}"],
            )
        for candidate in candidates:
            content = str(candidate.get("content", "")).strip()
            validate_retain_content(content)
            candidate_tags = list(candidate.get("tags") or ([] if not repo else [f"repo:{repo}"]))
            self.upsert_item(
                bank_id=f"repo:{repo}" if repo else "global",
                repo=repo,
                kind=str(candidate.get("kind") or "candidate"),
                status="candidate",
                content=content,
                evidence=str(candidate.get("evidence") or summary),
                source_anchor=session_id,
                tags=candidate_tags,
            )
        return session_id

    def list_candidates(self, *, repo: str | None = None, limit: int = 50) -> list[MemoryItem]:
        clauses = ["status = 'candidate'"]
        params: list[object] = []
        if repo:
            clauses.append("repo = ?")
            params.append(repo)
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *, 0.0 AS rank FROM memory_items
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def count_items(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])

    def count_sessions(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])

    def count_events(self, session_id: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM session_events WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
            )

    def list_imported_session_event_items(self, *, limit: int = 500) -> list[MemoryItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *, 0.0 AS rank FROM memory_items
                WHERE kind = 'session_event'
                  AND tags_json LIKE '%"imported"%'
                  AND tags_json LIKE '%"codex-conversation"%'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def delete_items(self, item_ids: Sequence[str]) -> int:
        if not item_ids:
            return 0
        placeholders = ",".join("?" for _ in item_ids)
        with self._connect() as connection:
            rowids = [
                int(row["rowid"])
                for row in connection.execute(
                    f"SELECT rowid FROM memory_items WHERE id IN ({placeholders})",
                    list(item_ids),
                ).fetchall()
            ]
            if not rowids:
                return 0
            rowid_placeholders = ",".join("?" for _ in rowids)
            connection.execute(f"DELETE FROM memory_items_fts WHERE rowid IN ({rowid_placeholders})", rowids)
            deleted = connection.execute(
                f"DELETE FROM memory_items WHERE id IN ({placeholders})",
                list(item_ids),
            ).rowcount
        return int(deleted)

    def update_item_evidence(self, item_id: str, evidence: str) -> bool:
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE memory_items
                SET evidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (evidence.strip(), _now(), item_id),
            ).rowcount
            if updated:
                self._sync_fts(connection, item_id)
        return bool(updated)


def _hash_parts(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fts_query(query: str) -> str:
    terms = re.findall(r"[\w./:-]+", query, flags=re.UNICODE)
    terms = [term for term in terms if len(term) > 1]
    return " OR ".join(f'"{term}"' for term in terms[:12])


def _row_to_item(row: sqlite3.Row) -> MemoryItem:
    return MemoryItem(
        id=str(row["id"]),
        bank_id=str(row["bank_id"]),
        repo=row["repo"],
        kind=str(row["kind"]),
        status=str(row["status"]),
        source_path=row["source_path"],
        source_anchor=row["source_anchor"],
        content=str(row["content"]),
        evidence=str(row["evidence"] or ""),
        tags_json=str(row["tags_json"] or "[]"),
        score=float(row["rank"] if "rank" in row.keys() else 0.0),
    )


def _row_to_item_sequence(rows: Sequence[sqlite3.Row], *, max_session_events: int) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    session_events = 0
    for row in rows:
        item = _row_to_item(row)
        if item.kind == "session_event":
            if max_session_events <= session_events:
                continue
            session_events += 1
        items.append(item)
    return items


def _dedupe_and_trim(items: list[MemoryItem], *, limit: int, max_chars: int) -> list[MemoryItem]:
    seen: set[str] = set()
    output: list[MemoryItem] = []
    total = 0
    for item in items:
        key = item.content.strip()
        if key in seen:
            continue
        if total + len(item.content) > max_chars and output:
            break
        seen.add(key)
        output.append(item)
        total += len(item.content)
        if len(output) >= limit:
            break
    return output
