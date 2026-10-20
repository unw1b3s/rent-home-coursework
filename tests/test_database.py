import sqlite3
import pytest
from app.db import connect, init_db
from app.seed import seed


def test_seed_is_repeatable(client):
    seed()
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==3
        assert db.execute('SELECT COUNT(*) FROM listings').fetchone()[0]==8
    seed()
    init_db()
    with connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM listings').fetchone()[0]==8
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('bad',999,'token',1))


def test_unknown_schema_rejected(client):
    with connect() as db: db.execute('PRAGMA user_version=99')
    with pytest.raises(RuntimeError): init_db()
