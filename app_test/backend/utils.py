import os
import csv
import io
import threading
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv
from flask import request, jsonify

load_dotenv()


# =========================================================
# BASE DE DATOS — Pool de conexiones
# =========================================================

_pool: MySQLConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> MySQLConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = MySQLConnectionPool(
                    pool_name="lineas_pool",
                    pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
                    host=os.getenv("DB_HOST", "localhost"),
                    port=int(os.getenv("DB_PORT", 3306)),
                    user=os.getenv("DB_USER", "root"),
                    password=os.getenv("DB_PASS", "root"),
                    database=os.getenv("DB_NAME", "db_lineas"),
                    charset="utf8mb4",
                    use_unicode=True,
                    autocommit=False,
                )
    return _pool


def get_db():
    return get_pool().get_connection()


def safe_close(cursor=None, conn=None):
    try:
        if cursor is not None:
            cursor.close()
    except Exception:
        pass
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def fetch_all(query, params=None):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        safe_close(cur, conn)


def fetch_one(query, params=None):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        return cur.fetchone()
    finally:
        safe_close(cur, conn)


def execute_query(query, params=None):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
        return cur.rowcount
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        safe_close(cur, conn)


def execute_transaction(statements):
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        for query, params in statements:
            cur.execute(query, params or ())
        conn.commit()
        return True
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        safe_close(cur, conn)


# =========================================================
# RESPUESTAS API
# =========================================================

def api_error(e, status=400):
    msg = str(e)
    # Limpia errores MySQL generados con SIGNAL SQLSTATE '45000'
    if "1644" in msg and ":" in msg:
        msg = msg.split(":")[-1].strip()
    return jsonify({"ok": False, "msg": msg}), status


def api_success(msg="OK", data=None, redirect=None, status=200):
    payload = {"ok": True, "msg": msg}
    if data is not None:
        payload["data"] = data
    if redirect is not None:
        payload["redirect"] = redirect
    return jsonify(payload), status


# =========================================================
# PAYLOAD / LIMPIEZA / VALIDACIONES
# =========================================================

def get_payload():
    if request.is_json:
        return request.get_json(force=True) or {}
    return request.form or {}


def clean(value):
    return (value or "").strip()


def clean_or_none(value):
    value = clean(value)
    return value if value else None


def bool_to_int(value, default=False):
    if value is None:
        return 1 if default else 0
    if isinstance(value, bool):
        return 1 if value else 0
    value = str(value).strip().lower()
    truthy = {"1", "true", "yes", "on", "si", "sí"}
    falsy = {"0", "false", "no", "off"}
    if value in truthy:
        return 1
    if value in falsy:
        return 0
    return 1 if default else 0


def is_valid_email(value):
    value = clean(value)
    if not value or "@" not in value:
        return False
    return "." in value.split("@")[-1]


def require_fields(data, fields):
    for field, message in fields.items():
        if not clean(data.get(field)):
            return message
    return None


# =========================================================
# IMPORTACIÓN CSV
# =========================================================

def leer_csv(file):
    """Lee un archivo CSV subido (FileStorage) y devuelve (filas, error).

    - Detecta la codificación (UTF-8 con/sin BOM o Latin-1).
    - Detecta el delimitador (',' ';' o tab) para soportar exports de Excel.
    - Normaliza los encabezados a minúsculas sin espacios al borde.
    - Ignora filas completamente vacías.
    """
    raw = file.read()
    if not raw:
        return None, "El archivo está vacío"

    text = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return None, "No se pudo leer el archivo (codificación no soportada)"

    try:
        delimiter = csv.Sniffer().sniff(text[:2048], delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return None, "El archivo no tiene encabezados"

    filas = []
    for row in reader:
        norm = {}
        for k, v in row.items():
            if k is None:
                continue
            norm[k.strip().lower()] = (v or "").strip()
        if any(norm.values()):  # ignora filas vacías
            filas.append(norm)

    return filas, None


def campo(row, *aliases):
    """Devuelve el primer valor no vacío de `row` para cualquiera de los alias dados."""
    for a in aliases:
        v = row.get(a.strip().lower())
        if v:
            return v
    return ""
