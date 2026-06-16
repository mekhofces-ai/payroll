"""
Database adapter — provides a unified interface for SQLite (local) and PostgreSQL (production).
Uses PostgreSQL via psycopg2 when DATABASE_URL env var is set, otherwise falls back to SQLite.
"""

import os
import re
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")

# ── PostgreSQL mode ──────────────────────────────────────────────────────────

if DATABASE_URL:

    import psycopg2
    import psycopg2.extras

    class Row(dict):
        _fields: list[str] | None = None

        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)

        def __getitem__(self, key):
            if isinstance(key, (int, slice)):
                if self._fields is None:
                    raise IndexError("Row has no fields for index access")
                if isinstance(key, int):
                    return super().__getitem__(self._fields[key])
                return [super().__getitem__(f) for f in self._fields[key]]
            return super().__getitem__(key)

        def keys(self):
            return dict.keys(self)

    class _PgCursor:
        def __init__(self, conn, real_cursor):
            self._conn = conn
            self._cursor = real_cursor
            self._lastrowid = None
            self._did_insert = False
            self.description = None

        @property
        def lastrowid(self):
            if self._lastrowid is not None:
                return self._lastrowid
            try:
                c = self._conn._real_conn.cursor()
                c.execute("SELECT lastval()")
                val = c.fetchone()[0]
                self._lastrowid = val
                return val
            except Exception:
                return None

        def execute(self, sql, params=None):
            sql = _translate_sql(sql)
            if params is None:
                params = ()
            if isinstance(params, tuple):
                params = list(params)
            try:
                self._cursor.execute(sql, params)
                self.description = self._cursor.description
                self._did_insert = sql.strip().upper().startswith("INSERT")
            except Exception as e:
                self._conn._real_conn.rollback()
                raise e
            return self

        def executemany(self, sql, seq_params):
            sql = _translate_sql(sql)
            if not seq_params:
                return self
            seq_params = [list(p) if isinstance(p, tuple) else p for p in seq_params]
            try:
                self._cursor.executemany(sql, seq_params)
            except Exception as e:
                self._conn._real_conn.rollback()
                raise e

        def executescript(self, sql_script):
            for stmt in self._split_statements(sql_script):
                if stmt:
                    self.execute(stmt)

        def _make_row(self, row):
            cols = [d[0] for d in self.description]
            r = Row(zip(cols, row))
            r._fields = cols
            return r

        def _make_rows(self, rows):
            cols = [d[0] for d in self.description]
            result = []
            for row in rows:
                r = Row(zip(cols, row))
                r._fields = cols
                result.append(r)
            return result

        def fetchone(self):
            row = self._cursor.fetchone()
            if row is not None and self.description:
                return self._make_row(row)
            return None

        def fetchall(self):
            rows = self._cursor.fetchall()
            if rows and self.description:
                return self._make_rows(rows)
            return []

        def __iter__(self):
            for row in self._cursor:
                if self.description:
                    yield self._make_row(row)
                else:
                    yield row

        @staticmethod
        def _split_statements(script):
            statements = []
            current = []
            in_string = False
            string_char = None
            for ch in script:
                if in_string:
                    current.append(ch)
                    if ch == string_char:
                        in_string = False
                elif ch in ("'", '"'):
                    current.append(ch)
                    in_string = True
                    string_char = ch
                elif ch == ";":
                    stmt = "".join(current).strip()
                    if stmt:
                        statements.append(stmt)
                    current = []
                else:
                    current.append(ch)
            remaining = "".join(current).strip()
            if remaining:
                statements.append(remaining)
            return statements

    class Connection:
        def __init__(self):
            self._real_conn = psycopg2.connect(DATABASE_URL)
            self._real_conn.autocommit = False

        @property
        def _raw_conn(self):
            return self._real_conn

        def cursor(self):
            return _PgCursor(self, self._real_conn.cursor())

        def execute(self, sql, params=None):
            return self.cursor().execute(sql, params)

        def executemany(self, sql, seq_params):
            self.cursor().executemany(sql, seq_params)

        def executescript(self, sql_script):
            self.cursor().executescript(sql_script)

        def commit(self):
            self._real_conn.commit()

        def rollback(self):
            self._real_conn.rollback()

        def close(self):
            self._real_conn.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type:
                    self.rollback()
                else:
                    self.commit()
            finally:
                self.close()

    OperationalError = psycopg2.Error

    def _translate_sql(sql):
        original = sql

        # PRAGMA foreign_keys = ON  → no-op
        if re.match(r"^\s*PRAGMA\s+foreign_keys\s*=\s*ON\s*$", sql, re.IGNORECASE):
            return "SELECT 1"

        # PRAGMA table_info(name)  → information_schema
        m = re.match(r"PRAGMA\s+table_info\((\w+)\)", sql, re.IGNORECASE)
        if m:
            return (
                f"SELECT column_name AS name, data_type AS type "
                f"FROM information_schema.columns "
                f"WHERE table_name = '{m.group(1)}'"
            )

        # INTEGER PRIMARY KEY AUTOINCREMENT  → SERIAL PRIMARY KEY
        sql = re.sub(
            r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
            "SERIAL PRIMARY KEY",
            sql,
            flags=re.IGNORECASE,
        )

        # REAL  → DOUBLE PRECISION  (only in DDL)
        if (
            sql.strip().upper().startswith("CREATE")
            or sql.strip().upper().startswith("ALTER")
        ):
            sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql)

        # INSERT OR IGNORE  → INSERT … ON CONFLICT DO NOTHING
        if re.search(r"\bINSERT\s+OR\s+IGNORE\b", sql, re.IGNORECASE):
            sql = re.sub(
                r"\bINSERT\s+OR\s+IGNORE\b", "INSERT", sql, flags=re.IGNORECASE
            )
            sql += " ON CONFLICT DO NOTHING"

        # ?  → %s  (SQLite → psycopg2 parameter style)
        sql = sql.replace("?", "%s")

        # Escape literal % that are not part of %s (e.g. LIKE patterns)
        sql = re.sub(r"%(?![s(])", "%%", sql)

        return sql

    def connect():
        return Connection()

# ── SQLite mode (fallback) ───────────────────────────────────────────────────

else:

    import sqlite3 as _sqlite3

    class Row(_sqlite3.Row):
        pass

    Connection = _sqlite3.Connection
    OperationalError = _sqlite3.OperationalError

    def connect():
        db_path = Path(__file__).parent / "payroll.db"
        conn = _sqlite3.connect(str(db_path))
        conn.row_factory = Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
