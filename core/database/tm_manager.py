import sqlite3
import re
import difflib
from pathlib import Path
from typing import List, Optional
from enum import Enum
from dataclasses import dataclass
from core.runtime.runtime_paths import RuntimePaths

class TMMatchType(Enum):
    CONTEXT_101 = "101%"
    EXACT_100 = "100%"
    FUZZY = "Fuzzy"

@dataclass
class TMMatch:
    source_text: str
    target_text: str
    score: float
    match_type: TMMatchType
    domain: Optional[str] = None
    lang_pair: Optional[str] = None

class TranslationMemoryManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = str(RuntimePaths.get_tm_db_file())
            
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        
    def _init_db(self):
        c = self.conn.cursor()
        
        # Create core table
        c.execute("""
            CREATE TABLE IF NOT EXISTS tm_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                prev_source_text TEXT,
                next_source_text TEXT,
                lang_pair TEXT,
                domain TEXT,
                project_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 1,
                UNIQUE(source_text, target_text, prev_source_text, next_source_text, lang_pair, domain)
            )
        """)
        
        # Create FTS5 virtual table using external content
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tm_search USING fts5(
                source_text, 
                target_text, 
                content='tm_segments', 
                content_rowid='id'
            )
        """)
        
        # Create triggers to keep FTS5 table in sync with tm_segments
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS tm_segments_ai AFTER INSERT ON tm_segments BEGIN
                INSERT INTO tm_search(rowid, source_text, target_text) 
                VALUES (new.id, new.source_text, new.target_text);
            END;
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS tm_segments_ad AFTER DELETE ON tm_segments BEGIN
                INSERT INTO tm_search(tm_search, rowid, source_text, target_text) 
                VALUES ('delete', old.id, old.source_text, old.target_text);
            END;
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS tm_segments_au AFTER UPDATE ON tm_segments BEGIN
                INSERT INTO tm_search(tm_search, rowid, source_text, target_text) 
                VALUES ('delete', old.id, old.source_text, old.target_text);
                INSERT INTO tm_search(rowid, source_text, target_text) 
                VALUES (new.id, new.source_text, new.target_text);
            END;
        """)
        
        # Add index for fast exact matching
        c.execute("CREATE INDEX IF NOT EXISTS idx_tm_segments_lookup ON tm_segments(source_text, lang_pair, domain)")
        
        self.conn.commit()

    def add_segment(self, 
                   source_text: str, 
                   target_text: str, 
                   prev_source_text: Optional[str] = None,
                   next_source_text: Optional[str] = None,
                   lang_pair: Optional[str] = None,
                   domain: Optional[str] = None,
                   project_id: Optional[str] = None):
                   
        source_text = source_text.strip()
        target_text = target_text.strip()
        if not source_text or not target_text:
            return
            
        prev_source_text = prev_source_text.strip() if prev_source_text else ""
        next_source_text = next_source_text.strip() if next_source_text else ""
        lang_pair = lang_pair.strip() if lang_pair else ""
        domain = domain.strip() if domain else ""
        
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO tm_segments (source_text, target_text, prev_source_text, next_source_text, lang_pair, domain, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_text, target_text, prev_source_text, next_source_text, lang_pair, domain) DO UPDATE SET
                usage_count = usage_count + 1,
                last_used_at = CURRENT_TIMESTAMP
        """, (source_text, target_text, prev_source_text, next_source_text, lang_pair, domain, project_id))
        self.conn.commit()

    def _sanitize_for_fts(self, text: str) -> str:
        # Extract alphanumeric sequences and join with OR
        words = re.findall(r'\w+', text)
        if not words:
            return ""
        return " OR ".join(words)

    def find_matches(self, 
                    source_text: str, 
                    prev_source: Optional[str] = None, 
                    next_source: Optional[str] = None,
                    lang_pair: Optional[str] = None,
                    domain: Optional[str] = None,
                    threshold: float = 0.7,
                    max_results: int = 5) -> List[TMMatch]:
                        
        source_text = source_text.strip()
        if not source_text:
            return []
            
        c = self.conn.cursor()
        results = []
        
        # 1. Exact and Context Matches
        query_params = [source_text]
        filters = ["source_text = ?"]
        
        if lang_pair:
            filters.append("lang_pair = ?")
            query_params.append(lang_pair)
        if domain:
            filters.append("domain = ?")
            query_params.append(domain)
            
        c.execute(f"SELECT * FROM tm_segments WHERE {' AND '.join(filters)}", query_params)
        exact_rows = c.fetchall()
        
        for row in exact_rows:
            is_context_match = False
            if prev_source and next_source and row['prev_source_text'] == prev_source and row['next_source_text'] == next_source:
                is_context_match = True
                
            match_type = TMMatchType.CONTEXT_101 if is_context_match else TMMatchType.EXACT_100
            results.append(TMMatch(
                source_text=row['source_text'],
                target_text=row['target_text'],
                score=1.0,
                match_type=match_type,
                domain=row['domain'],
                lang_pair=row['lang_pair']
            ))
            
        if results:
            # Sort 101% matches to top
            results.sort(key=lambda x: 1 if x.match_type == TMMatchType.EXACT_100 else 0)
            return results[:max_results]
            
        # 2. Fuzzy Matching via FTS5 Pruning
        sanitized_query = self._sanitize_for_fts(source_text)
        if not sanitized_query:
            return []
            
        # Retrieve candidates based on FTS MATCH, limit to 50 for performance
        c.execute("""
            SELECT tm_segments.* 
            FROM tm_search 
            JOIN tm_segments ON tm_search.rowid = tm_segments.id
            WHERE tm_search MATCH ?
            LIMIT 50
        """, (sanitized_query,))
        
        candidate_rows = c.fetchall()
        
        for row in candidate_rows:
            candidate_source = row['source_text']
            # Compute exact difflib ratio
            score = difflib.SequenceMatcher(None, source_text, candidate_source).ratio()
            
            if score >= threshold:
                results.append(TMMatch(
                    source_text=candidate_source,
                    target_text=row['target_text'],
                    score=score,
                    match_type=TMMatchType.FUZZY,
                    domain=row['domain'],
                    lang_pair=row['lang_pair']
                ))
                
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:max_results]

    def close(self):
        self.conn.close()
