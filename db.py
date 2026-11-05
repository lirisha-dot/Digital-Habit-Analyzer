import mysql.connector
from config import DB_CONFIG


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=None, one=False, commit=False):
    """SELECT -> list of dicts (or one dict). INSERT/UPDATE/DELETE with commit=True -> lastrowid."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return cur.lastrowid
        rows = cur.fetchall()
        if one:
            return rows[0] if rows else None
        return rows
    finally:
        cur.close()
        conn.close()


def execute_many(sql, rows):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
        conn.commit()
    finally:
        cur.close()
        conn.close()
