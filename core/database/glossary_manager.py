import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
from core.runtime.runtime_paths import RuntimePaths


@dataclass
class GlossaryEntry:
    id: int
    source_text: str
    target_text: str
    lang_pair: str = ""
    domain: str = "general"
    is_case_sensitive: bool = False
    created_at: Optional[str] = None


class GlossaryManager:
    """Manages SQLite storage and CRUD operations for glossary/termbase entries."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            self.db_path = str(RuntimePaths.get_glossary_db_file())
        else:
            self.db_path = str(db_path)

        self._is_memory = self.db_path == ":memory:"
        self._conn = None
        if self._is_memory:
            self._conn = sqlite3.connect(":memory:")
            self._init_db(self._conn)
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                self._init_db(conn)

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory and self._conn is not None:
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS glossary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                lang_pair TEXT DEFAULT '',
                domain TEXT DEFAULT 'general',
                is_case_sensitive INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_text, lang_pair, domain)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_glossary_lookup 
            ON glossary_entries(lang_pair, domain, source_text)
            """
        )
        conn.commit()

    def add_entry(
        self,
        source_text: str,
        target_text: str,
        lang_pair: str = "",
        domain: str = "general",
        is_case_sensitive: bool = False,
    ) -> int:
        source_text = source_text.strip()
        target_text = target_text.strip()
        domain = domain.strip() or "general"
        lang_pair = lang_pair.strip()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO glossary_entries (source_text, target_text, lang_pair, domain, is_case_sensitive)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_text, lang_pair, domain) DO UPDATE SET
                    target_text = excluded.target_text,
                    is_case_sensitive = excluded.is_case_sensitive
                """,
                (source_text, target_text, lang_pair, domain, int(is_case_sensitive)),
            )
            conn.commit()

            if cursor.lastrowid:
                # If ON CONFLICT DO UPDATE triggered, lastrowid might be 0 in some sqlite versions,
                # so query id if needed:
                entry_id = cursor.lastrowid
                if entry_id == 0:
                    cursor.execute(
                        "SELECT id FROM glossary_entries WHERE source_text = ? AND lang_pair = ? AND domain = ?",
                        (source_text, lang_pair, domain),
                    )
                    row = cursor.fetchone()
                    entry_id = row[0] if row else 0
                return entry_id
            return 0
        finally:
            if not self._is_memory:
                conn.close()

    def get_entry(self, entry_id: int) -> Optional[GlossaryEntry]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, source_text, target_text, lang_pair, domain, is_case_sensitive, created_at "
                "FROM glossary_entries WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return GlossaryEntry(
                id=row[0],
                source_text=row[1],
                target_text=row[2],
                lang_pair=row[3],
                domain=row[4],
                is_case_sensitive=bool(row[5]),
                created_at=row[6],
            )
        finally:
            if not self._is_memory:
                conn.close()

    def list_entries(
        self,
        domain: Optional[str] = None,
        lang_pair: Optional[str] = None,
    ) -> List[GlossaryEntry]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = (
                "SELECT id, source_text, target_text, lang_pair, domain, is_case_sensitive, created_at "
                "FROM glossary_entries WHERE 1=1"
            )
            params = []
            if domain is not None:
                query += " AND domain = ?"
                params.append(domain)
            if lang_pair is not None:
                query += " AND lang_pair = ?"
                params.append(lang_pair)

            query += " ORDER BY id ASC"
            cursor.execute(query, params)
            return [
                GlossaryEntry(
                    id=row[0],
                    source_text=row[1],
                    target_text=row[2],
                    lang_pair=row[3],
                    domain=row[4],
                    is_case_sensitive=bool(row[5]),
                    created_at=row[6],
                )
                for row in cursor.fetchall()
            ]
        finally:
            if not self._is_memory:
                conn.close()

    def delete_entry(self, entry_id: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM glossary_entries WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if not self._is_memory:
                conn.close()

    def get_term_mappings(
        self,
        domain: Optional[str] = None,
        lang_pair: Optional[str] = None,
    ) -> Dict[str, str]:
        """Returns mapping {source_text: target_text} for prompt injection."""
        entries = self.list_entries(domain=domain, lang_pair=lang_pair)
        return {e.source_text: e.target_text for e in entries}

    def import_entries(self, entries: List[dict]) -> int:
        """Batch imports a list of entry dicts."""
        count = 0
        for item in entries:
            self.add_entry(
                source_text=item["source_text"],
                target_text=item["target_text"],
                lang_pair=item.get("lang_pair", ""),
                domain=item.get("domain", "general"),
                is_case_sensitive=item.get("is_case_sensitive", False),
            )
            count += 1
        return count
