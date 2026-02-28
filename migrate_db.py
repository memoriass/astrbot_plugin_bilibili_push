
import sqlite3
import json
import os
from pathlib import Path

old_db = r'C:\git\AstrBot\data\plugin_data\astrbot_plugin_bilibili_push\data.db'
new_db = r'C:\git\AstrBot\data\plugin_data\astrbot_plugin_bilibili_push\data_new.db'

if not os.path.exists(old_db):
    print(f"Old database not found at {old_db}")
    exit(1)

conn_old = sqlite3.connect(old_db)
c_old = conn_old.cursor()
c_old.execute('SELECT uid, username, sub_type, categories, tags, target_id, enabled FROM subscriptions')
rows = c_old.fetchall()

conn_new = sqlite3.connect(new_db)
c_new = conn_new.cursor()
c_new.execute("""
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

for row in rows:
    uid, name, stype, cats, tags, tid, en = row
    # The new schema has target_id as 4th column, old has it as 6th
    c_new.execute('INSERT OR REPLACE INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?)', 
                 (uid, name, stype, tid, cats, tags, en))

conn_new.commit()
conn_old.close()
conn_new.close()

# Replace the old one
os.remove(old_db)
os.rename(new_db, old_db)
print("Migration and cleanup complete.")
