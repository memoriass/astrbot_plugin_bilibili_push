import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from ..core.types import Category

class Subscription:
    def __init__(self, uid: str, username: str, sub_type: str, target_id: str, 
                 categories: List[int], tags: List[str], enabled: bool = True):
        self.uid = str(uid)
        self.username = username
        self.sub_type = sub_type # 'dynamic', 'live'
        self.target_id = target_id
        self.categories = categories
        self.tags = tags
        self.enabled = enabled

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    uid TEXT,
                    username TEXT,
                    sub_type TEXT,
                    target_id TEXT,
                    categories TEXT,
                    tags TEXT,
                    enabled INTEGER DEFAULT 1,
                    PRIMARY KEY (uid, sub_type, target_id)
                )
            """)
            conn.execute("CREATE TABLE IF NOT EXISTS seen_dynamics (uid TEXT, dyn_id TEXT, PRIMARY KEY (uid, dyn_id))")
            conn.execute("CREATE TABLE IF NOT EXISTS live_status (uid TEXT PRIMARY KEY, last_status INTEGER, last_title TEXT)")
            conn.commit()

    def add_subscription(self, sub: Subscription) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO subscriptions (uid, username, sub_type, target_id, categories, tags, enabled) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sub.uid, sub.username, sub.sub_type, sub.target_id, json.dumps(sub.categories), json.dumps(sub.tags), 1 if sub.enabled else 0)
                )
                conn.commit()
                return True
        except: return False

    def remove_subscription(self, uid: str, sub_type: str, target_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM subscriptions WHERE uid = ? AND sub_type = ? AND target_id = ?", (str(uid), sub_type, target_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_subscriptions(self, target_id: Optional[str] = None) -> List[Subscription]:
        with sqlite3.connect(self.db_path) as conn:
            if target_id:
                cursor = conn.execute("SELECT uid, username, sub_type, target_id, categories, tags, enabled FROM subscriptions WHERE target_id = ?", (target_id,))
            else:
                cursor = conn.execute("SELECT uid, username, sub_type, target_id, categories, tags, enabled FROM subscriptions")
            
            subs = []
            for row in cursor:
                subs.append(Subscription(
                    uid=row[0], username=row[1], sub_type=row[2], target_id=row[3],
                    categories=json.loads(row[4]), tags=json.loads(row[5]), enabled=bool(row[6])
                ))
            return subs

    def is_seen_dynamic(self, uid: str, dyn_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM seen_dynamics WHERE uid = ? AND dyn_id = ?", (str(uid), str(dyn_id)))
            return cursor.fetchone() is not None

    def add_seen_dynamic(self, uid: str, dyn_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO seen_dynamics (uid, dyn_id) VALUES (?, ?)", (str(uid), str(dyn_id)))
            conn.commit()

    def get_live_status(self, uid: str) -> tuple:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT last_status, last_title FROM live_status WHERE uid = ?", (str(uid),))
            row = cursor.fetchone()
            return row if row else (0, "")

    def update_live_status(self, uid: str, status: int, title: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO live_status (uid, last_status, last_title) VALUES (?, ?, ?)", (str(uid), status, title))
            conn.commit()
