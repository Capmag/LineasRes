# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sistema de Control de Líneas Telefónicas** — a Flask web app for managing company phone lines, mobile devices (equipos), and employee assignments. The app is in `app_test/`.

## Running the App

```powershell
# Activate virtual environment (from repo root)
.venv\Scripts\Activate.ps1

# Run the Flask server (from backend directory)
cd app_test\backend
python app.py
```

The server starts at `http://127.0.0.1:5000` (configurable via `.env`).

## Environment Setup

Copy `.env.example` to `.env` at the repo root and fill in MySQL credentials:

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=db_lineas
DB_USER=root
DB_PASS=root
DB_POOL_SIZE=10
FLASK_DEBUG=1
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

The backend also reads `app_test/backend/.env`. Configure `SECRET_KEY` there for CSRF protection (Flask-WTF).

## Database Initialization

```powershell
cd app_test\backend
python init_db.py
```

This drops and recreates the `db_lineas` MySQL database using `schema_correcto.sql` at the repo root. **Destructive — wipes all data.**

## Architecture

### Project Structure

```
app_test/
  backend/          # Flask app (run from here)
    app.py          # App factory, root route, /test DB health check
    utils.py        # DB helpers + shared API response builders
    *.py            # One Blueprint per entity
  frontend/
    templates/      # Jinja2 HTML templates
    static/
      *.js          # Vanilla JS (app.js, selectores_dinamicos.js, toast-manager.js)
      styles/       # Per-page CSS files (naming: style_ls_*.css, style_cr_*.css, etc.)
schema_correcto.sql # Canonical MySQL schema
requirements.txt
```

### Backend Pattern

Each entity has its own Blueprint file. The pattern is uniform:
- **GET** routes render Jinja2 templates
- **POST/PUT/DELETE** routes accept JSON (`request.get_json(force=True)`) and return `{"ok": bool, "msg": str}` JSON — use `api_success()` / `api_error()` from `utils.py`
- All DB access goes through `utils.py` helpers: `fetch_all`, `fetch_one`, `execute_query`, `execute_transaction`
- Multi-step mutations (create/close/reassign assignments) use `execute_transaction([(sql, params), ...])` to stay atomic

### Database Layer (`utils.py`)

- **Connection pool** — lazy-initialized singleton `MySQLConnectionPool` (default size 10, configurable via `DB_POOL_SIZE`); each helper borrows a connection and returns it via `safe_close`
- All PKs are UUID strings (`str(uuid.uuid4())`) except `equipos` (IMEI as PK) and `historial_asignaciones` (auto-increment int)
- `execute_transaction` takes a list of `(query, params)` tuples and commits them together; rolls back on any failure
- `api_error(e)` strips MySQL SIGNAL error prefixes (`1644`) to return clean user-facing messages
- Payload helpers: `get_payload()` (JSON or form), `clean()` / `clean_or_none()`, `require_fields(data, {field: error_msg})`, `bool_to_int()`, `is_valid_email()`

### Entity Hierarchy

```
directores → centros_costo → areas → empleados
cuentas_padre → lineas
equipos (standalone, IMEI as PK)
asignaciones (links empleado + linea + equipo; tracks estatus: Vigente/Cerrada)
historial_asignaciones (append-only audit log for every assignment event)
```

### Assignment Lifecycle

Creating, closing, or reassigning an assignment always: (1) updates `asignaciones`, (2) updates `lineas.estatus` and `equipos.estatus`, (3) inserts a row into `historial_asignaciones` — all inside one `execute_transaction`.

### Frontend

- Vanilla JS — no framework
- `app.js`: CRUD modal handling and fetch calls for most entities
- `selectores_dinamicos.js`: cascading dropdowns (e.g., CC → Area → Empleado) loaded via `/api/*` endpoints
- `toast-manager.js`: toast notification system
- Templates extend `base.html`; per-page CSS files are named after the template they style

### Authentication

Two hardcoded users exist in the `usuarios` table:
- **`admin`** — password-protected; full CRUD access; session expires after 5 min of inactivity (`ADMIN_TIMEOUT`). Inactivity is tracked via `session['last_activity']` and refreshed by `POST /api/ping` (called client-side to keep the session alive).
- **`consultas`** — no password; accessed via `GET /login/consultas`; intended for read-only reporting access.

Auth is enforced via a `before_request` hook in `app.py`. The `login_required` decorator in `auth.py` is available but the hook already covers all non-public routes. Public endpoints are `auth.login`, `auth.logout`, `auth.login_consultas`, and `static`.

JSON/CSRF requests that hit an expired session get `{"ok": false, "msg": "Sesión expirada..."}` with HTTP 401 instead of a redirect.

### Key API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Dashboard with KPIs |
| `POST /api/ping` | Refreshes admin session; returns `remaining` seconds |
| `GET /test` | DB connectivity check |
| `GET /api/lineas_disponibles` | Available lines for assignment form |
| `GET /api/equipos_disponibles` | Available devices for assignment form |
| `GET /api/areas_por_cc?cc_id=` | Areas filtered by cost center |
| `GET /consultas` | Filterable report view (capped at 1000 rows) |
| `GET /consultas/excel` | Export same query to `.xlsx` |
