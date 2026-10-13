import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, kind TEXT, timestamp REAL, payload TEXT)')
        self.db.execute('CREATE INDEX IF NOT EXISTS by_kind ON records(kind,id)')
        self.db.commit()

    def add(self, kind, timestamp, payload):
        self.db.execute('INSERT INTO records(kind,timestamp,payload) VALUES(?,?,?)',(kind,timestamp,json.dumps(payload)))
        self.db.execute('DELETE FROM records WHERE id < (SELECT MAX(id)-50000 FROM records)')
        self.db.commit()

    def read(self, kind, limit=500):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM records WHERE kind=? ORDER BY id DESC LIMIT ?', (kind,limit))]

    def close(self):
        self.db.close()


def read_records(path,kind,limit=500):
    """Read agent data without creating or mutating its database."""
    if not Path(path).exists(): return []
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT payload FROM records WHERE kind=? ORDER BY id DESC LIMIT ?', (kind,limit))]
