from __future__ import annotations

import re
import sqlite3
import time


class AliasStoreMixin:
    def upsert_up_alias(
        self,
        *,
        alias: str,
        uid: str,
        username: str = "",
        face: str = "",
        target_id: str = "",
        source: str = "confirmed",
        confidence: float = 1.0,
    ) -> bool:
        normalized = normalize_alias(alias)
        uid = str(uid or "").strip()
        if not normalized or not uid:
            return False
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT hit_count, created_at
                FROM up_aliases
                WHERE normalized_alias = ? AND uid = ? AND target_id = ?
                """,
                (normalized, uid, str(target_id or "")),
            ).fetchone()
            hit_count = int((existing or [0])[0] or 0)
            created_at = int((existing or [0, now])[1] or now)
            conn.execute(
                """
                INSERT OR REPLACE INTO up_aliases (
                    alias, normalized_alias, uid, username, face, target_id,
                    source, confidence, hit_count, created_at, updated_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(alias).strip(),
                    normalized,
                    uid,
                    str(username or ""),
                    str(face or ""),
                    str(target_id or ""),
                    str(source or "confirmed"),
                    float(confidence),
                    hit_count,
                    created_at,
                    now,
                    now,
                ),
            )
            conn.commit()
            return True

    def find_up_aliases(
        self,
        alias: str,
        *,
        target_id: str = "",
        limit: int = 5,
    ) -> list[dict]:
        normalized = normalize_alias(alias)
        if not normalized:
            return []
        scopes = (str(target_id or ""), "")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT alias, normalized_alias, uid, username, face, target_id,
                       source, confidence, hit_count, created_at, updated_at, last_used_at
                FROM up_aliases
                WHERE normalized_alias = ? AND target_id IN (?, ?)
                ORDER BY CASE WHEN target_id = ? THEN 0 ELSE 1 END,
                         confidence DESC, hit_count DESC, updated_at DESC
                LIMIT ?
                """,
                (normalized, scopes[0], scopes[1], scopes[0], max(1, int(limit))),
            )
            return [self._alias_from_row(row) for row in cursor]

    def touch_up_alias(self, alias: str, uid: str, target_id: str = "") -> None:
        normalized = normalize_alias(alias)
        if not normalized or not uid:
            return
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE up_aliases
                SET hit_count = hit_count + 1, last_used_at = ?
                WHERE normalized_alias = ? AND uid = ? AND target_id = ?
                """,
                (now, normalized, str(uid), str(target_id or "")),
            )
            conn.commit()

    @staticmethod
    def _alias_from_row(row) -> dict:
        return {
            "alias": str(row[0] or ""),
            "normalized_alias": str(row[1] or ""),
            "uid": str(row[2] or ""),
            "username": str(row[3] or ""),
            "face": str(row[4] or ""),
            "target_id": str(row[5] or ""),
            "source": str(row[6] or ""),
            "confidence": float(row[7] or 0),
            "hit_count": int(row[8] or 0),
            "created_at": int(row[9] or 0),
            "updated_at": int(row[10] or 0),
            "last_used_at": int(row[11] or 0),
        }


def normalize_alias(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\s,，.。!！?？、;；:：()\[\]{}<>《》【】\"'“”‘’]+", "", text)
    return text
