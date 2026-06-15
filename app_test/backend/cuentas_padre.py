from flask import Blueprint, request, render_template, jsonify
from utils import fetch_all, fetch_one, execute_query, api_error
import uuid

cuentas_bp = Blueprint('cuentas', __name__)


@cuentas_bp.route("/api/cuentas_padre", methods=["GET"])
def api_cuentas_padre():
    cuentas = fetch_all("""
        SELECT id, operador AS label
        FROM cuentas_padre
        WHERE estatus = 'Activo'
        ORDER BY operador
    """)
    return jsonify(cuentas)


@cuentas_bp.route("/cuentas_padre", methods=["GET", "POST"])
def lista_cuentas_padre():
    if request.method == "GET":
        cuentas = fetch_all("""
            SELECT id, codigo, operador, descripcion, estatus
            FROM cuentas_padre
            ORDER BY operador
            LIMIT 100
        """)
        return render_template("lista_cuentas_padre.html", cuentas=cuentas)

    try:
        data = request.get_json(force=True)
        cuenta_id = data.get("id")

        deps = fetch_one("""
            SELECT COUNT(l.id) AS lineas_count
            FROM cuentas_padre cp
            LEFT JOIN lineas l ON l.cuenta_padre_id = cp.id
            WHERE cp.id = %s
        """, (cuenta_id,))

        if deps and deps["lineas_count"] > 0:
            return jsonify({
                "ok": False,
                "msg": f"No se puede eliminar, tiene {deps['lineas_count']} línea(s) asociada(s)"
            }), 400

        execute_query("DELETE FROM cuentas_padre WHERE id = %s", (cuenta_id,))
        return jsonify({"ok": True, "msg": "Cuenta padre eliminada correctamente"})

    except Exception as e:
        return api_error(e)


@cuentas_bp.route("/cuenta_padre/crear", methods=["GET", "POST"])
def crear_cuenta_padre():
    if request.method == "GET":
        return render_template("crear_cuenta_padre.html")

    try:
        data = request.get_json(force=True)

        cuenta_id = (data.get("id") or "").strip() or str(uuid.uuid4())
        codigo = (data.get("codigo") or "").strip()
        operador = (data.get("operador") or "").strip()
        descripcion = (data.get("descripcion") or "").strip() or None

        if not codigo:
            return jsonify({"ok": False, "msg": "El código de la cuenta es obligatorio"}), 400
        if not operador:
            return jsonify({"ok": False, "msg": "El nombre del operador es obligatorio"}), 400

        execute_query("""
            INSERT INTO cuentas_padre (id, codigo, operador, descripcion, estatus)
            VALUES (%s, %s, %s, %s, 'Activo')
        """, (cuenta_id, codigo, operador, descripcion))

        return jsonify({"ok": True, "msg": "Cuenta padre creada correctamente", "redirect": "/cuentas_padre"}), 201

    except Exception as e:
        return api_error(e)


@cuentas_bp.route("/cuenta_padre/editar/<id>", methods=["GET", "POST"])
def actualizar_cuenta_padre(id):
    if request.method == "GET":
        cuenta = fetch_one("""
            SELECT id, codigo, operador, descripcion, estatus
            FROM cuentas_padre WHERE id = %s
        """, (id,))
        if not cuenta:
            return "Cuenta padre no encontrada", 404
        return render_template("actualizar_cuenta_padre.html", cuenta=cuenta)

    try:
        data = request.get_json(force=True)

        nuevo_codigo = (data.get("nuevo_codigo") or "").strip()
        nuevo_operador = (data.get("nuevo_operador") or "").strip()
        nueva_descripcion = (data.get("nueva_descripcion") or "").strip() or None
        nuevo_estatus = (data.get("nuevo_estatus") or "").strip() or "Activo"

        actual = fetch_one(
            "SELECT id, codigo, operador, descripcion, estatus FROM cuentas_padre WHERE id = %s", (id,)
        )
        if not actual:
            return jsonify({"ok": False, "msg": "Cuenta padre no encontrada"}), 404

        if not nuevo_codigo:
            nuevo_codigo = actual["codigo"]
        if not nuevo_operador:
            nuevo_operador = actual["operador"]
        if nueva_descripcion is None:
            nueva_descripcion = actual["descripcion"]

        execute_query("""
            UPDATE cuentas_padre
            SET codigo = %s, operador = %s, descripcion = %s, estatus = %s
            WHERE id = %s
        """, (nuevo_codigo, nuevo_operador, nueva_descripcion, nuevo_estatus, id))

        return jsonify({"ok": True, "msg": "Cuenta padre actualizada correctamente"})

    except Exception as e:
        return api_error(e)
