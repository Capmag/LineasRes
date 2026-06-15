import os
import time
from flask import Flask, render_template, jsonify, session, redirect, url_for, request
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

ADMIN_TIMEOUT = 5 * 60  # segundos de inactividad antes de cerrar sesión admin

load_dotenv()

from directores import directores_bp
from centros_costo import cc_bp
from areas import areas_bp
from empleados import empleados_bp
from cuentas_padre import cuentas_bp
from lineas import lineas_bp
from moviles import moviles_bp
from asignaciones import asignaciones_bp
from consultas import consultas_bp
from auth import auth_bp

csrf = CSRFProtect()


def create_app():
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static"
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    csrf.init_app(app)

    register_blueprints(app)
    register_routes(app)
    register_hooks(app)

    return app


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(directores_bp)
    app.register_blueprint(cc_bp)
    app.register_blueprint(areas_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(cuentas_bp)
    app.register_blueprint(lineas_bp)
    app.register_blueprint(moviles_bp)
    app.register_blueprint(asignaciones_bp)
    app.register_blueprint(consultas_bp)


def register_hooks(app):
    _public = {'auth.login', 'auth.logout', 'auth.login_consultas', 'static'}

    @app.before_request
    def require_login():
        if request.endpoint is None or request.endpoint in _public:
            return

        if not session.get('user_id'):
            if request.is_json or request.headers.get('X-CSRFToken'):
                return jsonify({"ok": False, "msg": "Sesión expirada. Recarga la página."}), 401
            return redirect(url_for('auth.login'))

        # Timeout de inactividad solo para admin
        if session.get('username') == 'admin':
            last = session.get('last_activity')
            now = time.time()
            if last and (now - last) > ADMIN_TIMEOUT:
                session.clear()
                if request.is_json or request.headers.get('X-CSRFToken'):
                    return jsonify({"ok": False, "msg": "Sesión cerrada por inactividad."}), 401
                return redirect(url_for('auth.login'))
            session['last_activity'] = now


def register_routes(app):
    @app.route("/")
    def index():
        from utils import fetch_all, fetch_one

        # KPIs principales
        kpis = {}

        # Líneas por estado
        lineas_stats = fetch_all("""
            SELECT estatus, COUNT(*) AS total
            FROM lineas
            GROUP BY estatus
        """)
        lineas_dict = {row["estatus"]: row["total"] for row in lineas_stats}
        kpis["lineas_total"] = sum(lineas_dict.values())
        kpis["lineas_disponibles"] = lineas_dict.get("Disponible", 0)
        kpis["lineas_asignadas"] = lineas_dict.get("Asignado", 0)
        kpis["lineas_baja"] = lineas_dict.get("Baja", 0)

        # Equipos por estado
        equipos_stats = fetch_all("""
            SELECT estatus, COUNT(*) AS total
            FROM equipos
            GROUP BY estatus
        """)
        equipos_dict = {row["estatus"]: row["total"] for row in equipos_stats}
        kpis["equipos_total"] = sum(equipos_dict.values())
        kpis["equipos_disponibles"] = equipos_dict.get("Disponible", 0)
        kpis["equipos_asignados"] = equipos_dict.get("Asignado", 0)
        kpis["equipos_baja"] = equipos_dict.get("Baja", 0)

        # Asignaciones
        asign = fetch_one("""
            SELECT
                SUM(CASE WHEN estatus = 'Vigente' THEN 1 ELSE 0 END) AS vigentes,
                SUM(CASE WHEN estatus = 'Cerrada' THEN 1 ELSE 0 END) AS cerradas
            FROM asignaciones
        """) or {}
        kpis["asignaciones_vigentes"] = int(asign.get("vigentes") or 0)
        kpis["asignaciones_cerradas"] = int(asign.get("cerradas") or 0)

        # Empleados activos / inactivos
        empleados_stats = fetch_one("""
            SELECT
                SUM(CASE WHEN estatus = 'Activo' THEN 1 ELSE 0 END) AS activos,
                SUM(CASE WHEN estatus = 'Inactivo' THEN 1 ELSE 0 END) AS inactivos
            FROM empleados
        """) or {}
        kpis["empleados_activos"] = int(empleados_stats.get("activos") or 0)
        kpis["empleados_inactivos"] = int(empleados_stats.get("inactivos") or 0)

        # Top 5 centros de costo con más líneas asignadas
        top_cc = fetch_all("""
            SELECT cc.nombre, COUNT(DISTINCT asi.id) AS total
            FROM centros_costo cc
            LEFT JOIN areas ar ON ar.centro_costo_id = cc.id
            LEFT JOIN empleados e ON e.area_id = ar.id
            LEFT JOIN asignaciones asi ON asi.empleado_id = e.id
                AND asi.estatus = 'Vigente' AND asi.fecha_fin IS NULL
            GROUP BY cc.id, cc.nombre
            ORDER BY total DESC
            LIMIT 5
        """)

        # Movimientos recientes (últimos 10 del historial)
        movimientos = fetch_all("""
            SELECT
                ha.fecha_inicio,
                ha.tipo_movimiento,
                ha.motivo,
                CONCAT(e.nombre, ' ', COALESCE(e.apellido, '')) AS empleado,
                IF(l.lada = 0, CAST(l.numero AS CHAR), CONCAT(l.lada, '-', l.numero)) AS linea
            FROM historial_asignaciones ha
            JOIN empleados e ON e.id = ha.empleado_id
            JOIN lineas l ON l.id = ha.linea_id
            ORDER BY ha.fecha_inicio DESC
            LIMIT 10
        """)

        return render_template(
            "index.html",
            kpis=kpis,
            top_cc=top_cc,
            movimientos=movimientos,
        )

    @app.route("/api/ping", methods=["POST"])
    def ping():
        if session.get('username') == 'admin':
            remaining = max(0, int(ADMIN_TIMEOUT - (time.time() - session.get('last_activity', time.time()))))
        else:
            remaining = None
        return jsonify({"ok": True, "remaining": remaining})

    @app.route("/test")
    def test():
        conn = None
        cur = None

        try:
            from utils import get_db, safe_close

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()

            return jsonify({
                "ok": True,
                "msg": "DB OK",
                "result": result[0] if result else None
            })

        except Exception as e:
            return jsonify({
                "ok": False,
                "msg": f"DB Error: {str(e)}"
            }), 500

        finally:
            try:
                safe_close(cur, conn)
            except Exception:
                pass


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
