"""SQLite 数据库管理"""
import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

from ..logger import logger

@dataclass
class Subscription:
    uid: str
    username: str
    sub_type: Literal["dynamic", "live"]
    categories: list[int]
    tags: list[str]
    target_id: str # 推送目标 (group_id)
    enabled: bool = True

class DBManager:
    def __init__(self, data_dir: str | Path):
        self.db_path = Path(data_dir) / "data.db"
        self.init_db()
        
    def init_db(self):
        """初始化表结构"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 订阅表
        # target_id: group_id
        # sub_type: dynamic, live
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                     (uid TEXT, 
                      username TEXT, 
                      sub_type TEXT, 
                      categories TEXT, 
                      tags TEXT, 
                      target_id TEXT, 
                      enabled INTEGER)''')
        
        # 确保唯一性 (uid + sub_type + target_id)
        # 允许同一个群订阅同一个UP的不同类型，或者不同群订阅同一个UP
        try:
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_sub ON subscriptions (uid, sub_type, target_id)')
        except Exception:
            pass
            
        conn.commit()
        conn.close()

    def add_subscription(self, sub: Subscription) -> bool:
        """添加订阅"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (sub.uid, sub.username, sub.sub_type, 
                       json.dumps(sub.categories), json.dumps(sub.tags), 
                       sub.target_id, 1 if sub.enabled else 0))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"订阅已存在: {sub.uid} {sub.sub_type} {sub.target_id}")
            return False
        except Exception as e:
            logger.error(f"DB Error: {e}")
            return False

    def remove_subscription(self, uid: str, sub_type: str, target_id: str) -> bool:
        """删除订阅"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM subscriptions WHERE uid=? AND sub_type=? AND target_id=?", 
                  (uid, sub_type, target_id))
        row_count = c.rowcount
        conn.commit()
        conn.close()
        return row_count > 0

    def get_subscriptions(self, target_id: str = None) -> list[Subscription]:
        """获取订阅列表，可选按群组筛选"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if target_id:
            c.execute("SELECT * FROM subscriptions WHERE target_id=?", (target_id,))
        else:
            c.execute("SELECT * FROM subscriptions")
            
        rows = c.fetchall()
        conn.close()
        
        subs = []
        for row in rows:
            subs.append(Subscription(
                uid=row[0],
                username=row[1],
                sub_type=row[2],
                categories=json.loads(row[3]),
                tags=json.loads(row[4]),
                target_id=row[5],
                enabled=bool(row[6])
            ))
        return subs
    
    def get_all_uids(self, sub_type: str) -> list[str]:
        """获取某类型所有被订阅的 UID (去重)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT DISTINCT uid FROM subscriptions WHERE sub_type=?", (sub_type,))
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
