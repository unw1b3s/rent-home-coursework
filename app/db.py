import os
from contextlib import contextmanager
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@contextmanager
def connect():
    path = Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'rent.db')))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        with db:
            yield db
    finally:
        db.close()

def init_db():
    with connect() as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version == 0:
            db.executescript((ROOT / 'sql/001_initial.sql').read_text())
        elif version != 1:
            raise RuntimeError('Неизвестная версия схемы БД')
        db.executemany('INSERT OR IGNORE INTO property_types(id,name) VALUES (?,?)',
                       [(1,'Квартира'),(2,'Студия'),(3,'Дом'),(4,'Комната')])
