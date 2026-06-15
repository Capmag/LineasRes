#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de inicialización / migración segura de la BD.
- Si la BD no existe: la crea desde cero con el schema completo.
- Si ya existe: solo aplica tablas faltantes (CREATE TABLE IF NOT EXISTS).
- Los usuarios del sistema se crean si no existen (INSERT IGNORE).
Seguro de correr múltiples veces sin pérdida de datos.
"""

import os
import sys
import uuid
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "root")
DB_NAME = os.getenv("DB_NAME", "db_lineas")


def _db_exists(cur) -> bool:
    cur.execute("SHOW DATABASES LIKE %s", (DB_NAME,))
    return cur.fetchone() is not None


def _apply_schema(cur, schema_path: str):
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    for chunk in sql_script.split(";"):
        lines = [l for l in chunk.splitlines() if not l.strip().startswith("--")]
        sql = "\n".join(lines).strip()
        if sql:
            try:
                cur.execute(sql)
            except mysql.connector.Error as e:
                # Ignorar errores esperados (tabla ya existe, FK ya existe, etc.)
                if e.errno not in (1050, 1060, 1061, 1062):
                    print(f"  [!] {str(e)[:120]}")


def _ensure_usuarios(cur, conn):
    users = [
        ("admin",     generate_password_hash("skymis01"), "Administrador"),
        ("consultas", generate_password_hash(str(uuid.uuid4())), "Consultas"),
    ]
    created = 0
    for username, pw_hash, nombre in users:
        cur.execute("SELECT id FROM usuarios WHERE username = %s", (username,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO usuarios (id, username, password_hash, nombre) VALUES (%s,%s,%s,%s)",
                (str(uuid.uuid4()), username, pw_hash, nombre),
            )
            print(f"  [+] Usuario '{username}' creado")
            created += 1
        else:
            print(f"  [=] Usuario '{username}' ya existe, sin cambios")
    if created:
        conn.commit()


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema_correcto.sql")

    # Conexión sin BD para verificar existencia
    conn = mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()

    try:
        exists = _db_exists(cur)

        if not exists:
            print(f"[+] Creando base de datos '{DB_NAME}'...")
            cur.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        else:
            print(f"[=] Base de datos '{DB_NAME}' ya existe, aplicando solo cambios pendientes...")

        cur.execute(f"USE {DB_NAME}")

        print("[*] Aplicando schema...")
        _apply_schema(cur, schema_path)
        conn.commit()
        print("[OK] Schema aplicado correctamente")

        print("[*] Verificando usuarios del sistema...")
        _ensure_usuarios(cur, conn)

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_db()
